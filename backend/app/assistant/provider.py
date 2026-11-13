"""Native provider transports with explicit retry, structured repair and failover traces."""
import math
import asyncio
import hashlib
import json
import logging
import threading
import weakref
from dataclasses import dataclass
from time import perf_counter
from typing import AsyncIterator, Protocol
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, ValidationError

from .config import AssistantSettings


from app.core.errors import DomainError as AssistantError


@dataclass(frozen=True)
class Completion:
    output: BaseModel
    model: str
    latency_ms: float
    usage: dict
    request_id: str | None = None
    finish_reason: str | None = None


class JsonLLM(Protocol):
    async def complete(self, contract: type[BaseModel], messages: list[dict]) -> Completion: ...


_GATE_LOCK = threading.Lock()
_PROVIDER_GATES: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_NVIDIA_HEALTH_LOCK = threading.Lock()
_NVIDIA_COOLDOWN_UNTIL = 0.0
_NVIDIA_PROBE_ACTIVE = False


def _provider_gate(provider: str, limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    with _GATE_LOCK:
        gates = _PROVIDER_GATES.setdefault(loop, {})
        entry = gates.get(provider)
        if entry is None or entry[0] != limit:
            entry = (limit, asyncio.Semaphore(limit))
            gates[provider] = entry
        return entry[1]


def _reserve_nvidia() -> tuple[bool, bool]:
    """Return (allowed, is_half_open_probe) for process-wide NIM cooldown."""
    global _NVIDIA_PROBE_ACTIVE
    now = perf_counter()
    with _NVIDIA_HEALTH_LOCK:
        if now < _NVIDIA_COOLDOWN_UNTIL:
            return False, False
        if _NVIDIA_COOLDOWN_UNTIL and _NVIDIA_PROBE_ACTIVE:
            return False, False
        probe = bool(_NVIDIA_COOLDOWN_UNTIL)
        if probe:
            _NVIDIA_PROBE_ACTIVE = True
        return True, probe


def _record_nvidia_failure(settings: AssistantSettings, error: AssistantError, probe: bool = False):
    global _NVIDIA_COOLDOWN_UNTIL, _NVIDIA_PROBE_ACTIVE
    with _NVIDIA_HEALTH_LOCK:
        if error.code.endswith("_RATE_LIMIT"):
            delay = getattr(error, "retry_after_seconds", None) or settings.assistant_retry_base_seconds
            _NVIDIA_COOLDOWN_UNTIL = perf_counter() + delay
        elif probe:
            _NVIDIA_COOLDOWN_UNTIL = perf_counter() + settings.assistant_retry_base_seconds
        _NVIDIA_PROBE_ACTIVE = False


def _record_nvidia_success(probe: bool = False):
    global _NVIDIA_COOLDOWN_UNTIL, _NVIDIA_PROBE_ACTIVE
    with _NVIDIA_HEALTH_LOCK:
        if probe:
            _NVIDIA_COOLDOWN_UNTIL = 0.0
        _NVIDIA_PROBE_ACTIVE = False


def _usage(raw: object) -> dict:
    """Keep only safe, numeric usage fields from an upstream response."""
    if not isinstance(raw, dict):
        return {}
    aliases = {"prompt_tokens": "prompt_tokens", "completion_tokens": "completion_tokens",
               "total_tokens": "total_tokens", "cost": "cost", "promptTokenCount": "prompt_tokens",
               "candidatesTokenCount": "completion_tokens", "totalTokenCount": "total_tokens"}
    result = {}
    for key, value in raw.items():
        target = aliases.get(key)
        if target and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[target] = value
    return result


def _http_error(provider: str, response: httpx.Response) -> AssistantError:
    status = response.status_code
    headers = response.headers
    retry_after = headers.get("retry-after")
    retry_at = None
    if retry_after:
        try:
            retry_at = max(1, int(float(retry_after)))
        except ValueError:
            try:
                retry_at = max(1, int((parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                retry_at = None
    request_id = next((headers.get(name) for name in ("x-request-id", "request-id", "x-goog-request-id") if headers.get(name)), None)
    if status == 429:
        error = AssistantError(f"{provider.upper()}_RATE_LIMIT", 429)
        error.retry_after_seconds = retry_at
        error.request_id = request_id
        error.upstream_status = status
        return error
    if status in (401, 403):
        error = AssistantError(f"{provider.upper()}_AUTH_FAILED", status)
        error.request_id = request_id
        error.upstream_status = status
        return error
    if status == 400 or status == 422:
        error = AssistantError(f"{provider.upper()}_INVALID_REQUEST", 400)
        error.request_id = request_id
        error.upstream_status = status
        return error
    if status >= 500:
        error = AssistantError(f"{provider.upper()}_UNAVAILABLE", 502)
        error.request_id = request_id
        error.upstream_status = status
        return error
    if status == 404:
        error = AssistantError(f"{provider.upper()}_MODEL_NOT_FOUND", 502)
        error.request_id = request_id
        error.upstream_status = status
        return error
    if status == 410:
        error = AssistantError(f"{provider.upper()}_ENDPOINT_GONE", 502)
        error.request_id = request_id
        error.upstream_status = status
        return error
    error = AssistantError(f"{provider.upper()}_REQUEST_FAILED", 502)
    error.request_id = request_id
    error.upstream_status = status
    return error


def _schema_prompt(contract: type[BaseModel], messages: list[dict]) -> list[dict]:
    schema = wire_schema(contract)
    guide = {"role": "system", "content": "Return one JSON object matching this schema. Do not include markdown fences. "
        "The server validates all fields and remains authoritative: " + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}
    if messages and messages[0].get("role") == "system":
        return [messages[0], guide, *messages[1:]]
    return [guide, *messages]


def _extract_openai(body: dict) -> tuple[str, str, dict]:
    choice = body["choices"][0]
    finish = choice.get("finish_reason") or ""
    message = choice.get("message") or {}
    if finish == "length":
        raise AssistantError("MODEL_OUTPUT_TRUNCATED", 502)
    if message.get("refusal"):
        raise AssistantError("MODEL_REFUSED", 502)
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
    if not isinstance(content, str) or not content.strip() or finish not in ("stop", "" ):
        raise AssistantError("MODEL_OUTPUT_INVALID", 502)
    return content, finish, _usage(body.get("usage"))


def _extract_gemini(body: dict) -> tuple[str, str, dict]:
    candidates = body.get("candidates") or []
    if not candidates:
        raise AssistantError("MODEL_OUTPUT_INVALID", 502)
    candidate = candidates[0]
    finish = candidate.get("finishReason", "")
    if finish == "MAX_TOKENS":
        raise AssistantError("MODEL_OUTPUT_TRUNCATED", 502)
    if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        raise AssistantError("MODEL_REFUSED", 502)
    parts = (candidate.get("content") or {}).get("parts") or []
    content = "".join(part.get("text", "") for part in parts
                     if isinstance(part, dict) and not part.get("thought") and isinstance(part.get("text"), str))
    if not content.strip() or finish not in ("STOP", ""):
        raise AssistantError("MODEL_OUTPUT_INVALID", 502)
    return content, finish, _usage(body.get("usageMetadata"))


async def _sse_payloads(response: httpx.Response) -> AsyncIterator[dict]:
    data = []
    async for line in response.aiter_lines():
        if not line:
            if data:
                raw = "\n".join(data)
                data.clear()
                if raw == "[DONE]":
                    return
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError as error:
                    raise AssistantError("MODEL_STREAM_INVALID", 502) from error
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        raw = "\n".join(data)
        if raw != "[DONE]":
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as error:
                raise AssistantError("MODEL_STREAM_INVALID", 502) from error


class NativeLLM:
    """Streaming JSON adapter for NVIDIA NIM or the native Gemini API."""
    def __init__(self, provider: str, settings: AssistantSettings, transport=None,
                 client: httpx.AsyncClient | None = None):
        self.provider, self.settings, self.transport, self.client = provider, settings, transport, client

    def _output_budget(self, messages: list[dict], schema: dict) -> int:
        # UTF-8 bytes are a conservative local upper bound for prompt tokenization.
        # Leave only the remainder of the model context available for generation.
        encoded = json.dumps({"messages": messages, "schema": schema}, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        context = 1_048_576
        remaining = context - len(encoded)
        if remaining < 1:
            raise AssistantError("MODEL_CONTEXT_OVERFLOW", 413)
        configured = (self.settings.nvidia_max_output_tokens if self.provider == "nvidia"
                      else self.settings.gemini_max_output_tokens)
        return min(configured, remaining)

    def _request(self, contract: type[BaseModel], messages: list[dict]) -> tuple[str, dict, dict]:
        s = self.settings
        wire = _schema_prompt(contract, messages)
        if self.provider == "nvidia":
            key = s.nvidia_api_key.get_secret_value().strip() if s.nvidia_api_key else ""
            if not key or not s.nvidia_model.strip():
                raise AssistantError("NVIDIA_NOT_CONFIGURED", 503)
            endpoint = s.nvidia_base_url.rstrip("/") + "/chat/completions"
            output_budget = self._output_budget(wire, wire_schema(contract))
            if "deepseek-v4.1-flash" in s.nvidia_model.casefold():
                reasoning_effort = "none"
                chat_template_kwargs = {"thinking": False}
            else:
                reasoning_effort = "low"
                chat_template_kwargs = {"reasoning_effort": "low", "clear_thinking": True}
            payload = {"model": s.nvidia_model, "messages": wire, "stream": s.assistant_streaming,
                      "max_tokens": output_budget, "reasoning_effort": reasoning_effort,
                      "chat_template_kwargs": chat_template_kwargs,
                      "response_format": {"type": "json_object"}}
            if s.assistant_streaming:
                payload["stream_options"]={"include_usage":True}
            return endpoint, {"Authorization": "Bearer " + key}, payload
        key = s.gemini_api_key.get_secret_value().strip() if s.gemini_api_key else ""
        if not key or not s.gemini_model.strip():
            raise AssistantError("GEMINI_NOT_CONFIGURED", 503)
        system = "\n\n".join(m["content"] for m in wire if m.get("role") == "system")
        contents = []
        for message in wire:
            if message.get("role") == "system":
                continue
            role = "model" if message.get("role") == "assistant" else "user"
            # Gemini REST requires alternating roles. Preserve the user request in its original order.
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"][0]["text"] += "\n\n" + str(message.get("content", ""))
            else:
                contents.append({"role": role, "parts": [{"text": str(message.get("content", ""))}]})
        schema = wire_schema(contract)
        endpoint_method = "streamGenerateContent?alt=sse" if s.assistant_streaming else "generateContent"
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:{endpoint_method}"
        payload = {"systemInstruction": {"parts": [{"text": system}]} if system else None,
                   "contents": contents,
                   "generationConfig": {"maxOutputTokens": self._output_budget(wire, schema),
                       "thinkingConfig": {"thinkingLevel": "MINIMAL"},
                       "responseMimeType": "application/json", "responseJsonSchema": schema}}
        if payload["systemInstruction"] is None:
            payload.pop("systemInstruction")
        return endpoint, {"x-goog-api-key": key}, payload

    async def complete(self, contract: type[BaseModel], messages: list[dict]) -> Completion:
        endpoint, headers, payload = self._request(contract, messages)
        started = perf_counter()
        timeout = httpx.Timeout(connect=self.settings.assistant_connect_timeout_seconds,
                                read=None, write=None, pool=None)
        try:
            async with _provider_gate(self.provider, self.settings.assistant_max_concurrent_per_provider):
                if self.client is None:
                    async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                        response_context = client.stream("POST", endpoint,
                            headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=timeout)
                        async with response_context as response:
                            content, usage, finish, actual_model = await self._read_response(response)
                            request_id = self._request_id(response)
                else:
                    response_context = self.client.stream("POST", endpoint,
                        headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=timeout)
                    async with response_context as response:
                        content, usage, finish, actual_model = await self._read_response(response)
                        request_id = self._request_id(response)
            output = contract.model_validate_json(content)
        except AssistantError:
            raise
        except ValidationError as error:
            fields = [(item["loc"], item["type"]) for item in error.errors(include_input=False)]
            logging.getLogger(__name__).warning("Structured output rejected: provider=%s contract=%s fields=%s",
                                                self.provider, contract.__name__, fields)
            raise AssistantError("MODEL_OUTPUT_INVALID", 502) from error
        except (httpx.ConnectError, httpx.NetworkError) as error:
            raise AssistantError(f"{self.provider.upper()}_UNAVAILABLE", 502) from error
        except (httpx.TimeoutException, TimeoutError) as error:
            # Connection establishment is bounded; a slow generation is deliberately not.
            raise AssistantError(f"{self.provider.upper()}_CONNECT_TIMEOUT", 504) from error
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as error:
            raise AssistantError("MODEL_OUTPUT_INVALID", 502) from error
        configured_model = self.settings.nvidia_model if self.provider == "nvidia" else self.settings.gemini_model
        return Completion(output, actual_model or configured_model,
                          (perf_counter() - started) * 1000, usage, request_id, finish)

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        return next((response.headers.get(name) for name in ("x-request-id", "request-id", "x-goog-request-id")
                     if response.headers.get(name)), None)

    async def _read_response(self, response: httpx.Response) -> tuple[str, dict, str, str | None]:
        if response.status_code != 200:
            raise _http_error(self.provider, response)
        if not self.settings.assistant_streaming:
            decoded = json.loads(await response.aread())
            content, finish, usage = _extract_openai(decoded) if self.provider == "nvidia" else _extract_gemini(decoded)
            model = decoded.get("model") or decoded.get("modelVersion")
            return content, usage, finish, model
        chunks, usage, finish = [], {}, ""
        actual_model = None
        async for body in _sse_payloads(response):
            actual_model = body.get("model") or body.get("modelVersion") or actual_model
            if self.provider == "nvidia":
                choices = body.get("choices") or []
                if choices:
                    choice = choices[0]
                    finish = choice.get("finish_reason") or finish
                    delta = choice.get("delta") or {}
                    chunk = delta.get("content")
                    if isinstance(chunk, str):
                        chunks.append(chunk)
                usage.update(_usage(body.get("usage")))
            else:
                candidates = body.get("candidates") or []
                if candidates:
                    candidate = candidates[0]
                    finish = candidate.get("finishReason") or finish
                    for part in (candidate.get("content") or {}).get("parts") or []:
                        if isinstance(part, dict) and not part.get("thought") and isinstance(part.get("text"), str):
                            chunks.append(part["text"])
                usage.update(_usage(body.get("usageMetadata")))
        content = "".join(chunks)
        if finish in {"length", "MAX_TOKENS"}:
            raise AssistantError("MODEL_OUTPUT_TRUNCATED", 502)
        if not content.strip() or finish not in {"stop", "STOP"}:
            raise AssistantError("MODEL_OUTPUT_INVALID", 502)
        return content, usage, finish, actual_model


class ResilientLLM:
    """Primary NIM with explicit, traceable Gemini failover and bounded repair."""
    def __init__(self, settings: AssistantSettings, transports: dict | None = None,
                 clients: dict[str, httpx.AsyncClient] | None = None, on_attempt=None):
        self.settings = settings
        transports = transports or {}
        clients = clients or {}
        self.primary = NativeLLM("nvidia", settings, transports.get("nvidia"), clients.get("nvidia"))
        self.secondary = NativeLLM("gemini", settings, transports.get("gemini"), clients.get("gemini"))
        self.events: list[dict] = []
        self.last_provider = None
        self._forced_provider: str | None = None
        self.on_attempt = on_attempt

    @staticmethod
    def _retryable(error: AssistantError) -> bool:
        return error.code.endswith(("_RATE_LIMIT", "_UNAVAILABLE", "_CONNECT_TIMEOUT", "MODEL_OUTPUT_INVALID", "MODEL_OUTPUT_TRUNCATED", "MODEL_STREAM_INVALID"))

    async def _attempt(self, adapter: NativeLLM, contract: type[BaseModel], messages: list[dict], stage: str) -> Completion:
        last = None
        attempt_messages = messages
        retry_used = repair_used = False
        for attempt in range(1, 4):
            try:
                if self.on_attempt:
                    self.on_attempt(adapter.provider, stage, attempt)
                result = await adapter.complete(contract, attempt_messages)
                self.last_provider = adapter.provider
                self.events.append({"provider": adapter.provider, "model": result.model, "stage": stage,
                                    "attempt": attempt, "outcome": "success", "latency_ms": result.latency_ms,
                                    "usage": result.usage,"request_id":result.request_id,
                                    "finish_reason":result.finish_reason,"timestamp_utc":datetime.now(timezone.utc).isoformat(),
                                    "prompt_hash":hashlib.sha256(json.dumps(messages,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                                    "schema_hash":hashlib.sha256(json.dumps(wire_schema(contract),sort_keys=True).encode()).hexdigest()})
                return result
            except AssistantError as error:
                last = error
                self.events.append({"provider": adapter.provider, "stage": stage, "attempt": attempt,
                                    "outcome": "error", "error_code": error.code,
                                    "retry_after_seconds": getattr(error, "retry_after_seconds", None),
                                    "upstream_status":getattr(error,"upstream_status",None),
                                    "request_id":getattr(error,"request_id",None),
                                    "timestamp_utc":datetime.now(timezone.utc).isoformat()})
                # A rate limit is a routing signal: switch providers immediately.
                if error.code.endswith("_RATE_LIMIT") or not self._retryable(error) or attempt == 3:
                    break
                if error.code.startswith("MODEL_OUTPUT_") or error.code == "MODEL_STREAM_INVALID":
                    if repair_used:
                        break
                    repair_used = True
                    attempt_messages = [*messages, {"role": "user", "content":
                        "Your previous response did not satisfy the required JSON contract. "
                        "Return a corrected complete JSON object matching the schema. Do not repeat invalid output."}]
                else:
                    if retry_used:
                        break
                    retry_used = True
        raise last

    async def complete(self, contract: type[BaseModel], messages: list[dict]) -> Completion:
        provider = self._forced_provider or self.settings.assistant_provider
        primary = self.primary if provider == "nvidia" else self.secondary if provider == "gemini" else None
        if primary is None:
            if not self.settings.openrouter_api_key or not self.settings.openrouter_model:
                raise AssistantError("OPENROUTER_NOT_CONFIGURED", 503)
            if self.on_attempt:
                self.on_attempt("openrouter", contract.__name__, 1)
            result = await OpenRouterLLM(self.settings).complete(contract, messages)
            self.last_provider = "openrouter"
            self.events.append({"provider":"openrouter", "model":result.model,
                                "stage":contract.__name__, "attempt":1, "outcome":"success",
                                "latency_ms":result.latency_ms, "usage":result.usage,
                                "request_id":result.request_id, "finish_reason":result.finish_reason,
                                "timestamp_utc":datetime.now(timezone.utc).isoformat()})
            return result
        secondary = self.secondary if primary is self.primary and self.settings.assistant_failover_enabled else None
        probe = False
        if primary is self.primary:
            allowed, probe = _reserve_nvidia()
            if not allowed:
                self.events.append({"provider": "nvidia", "stage": contract.__name__,
                                    "outcome": "cooldown", "error_code": "NVIDIA_COOLDOWN"})
                first = AssistantError("NVIDIA_COOLDOWN", 429)
                if secondary:
                    self.events.append({"provider": "nvidia", "stage": contract.__name__,
                                        "outcome": "failover", "error_code": first.code})
                    self._forced_provider = "gemini"
                    result = await self._attempt(secondary, contract, messages, contract.__name__)
                    self.last_provider = "gemini"
                    return result
                raise first
        try:
            result = await self._attempt(primary, contract, messages, contract.__name__)
            if primary is self.primary:
                _record_nvidia_success(probe)
            return result
        except AssistantError as first:
            if primary is self.primary:
                _record_nvidia_failure(self.settings, first, probe)
            if not secondary or not self._retryable(first):
                raise
            self.events.append({"provider": primary.provider, "stage": contract.__name__,
                                "outcome": "failover", "error_code": first.code,
                                "retry_after_seconds": getattr(first, "retry_after_seconds", None)})
            try:
                self._forced_provider = "gemini"
                result = await self._attempt(secondary, contract, messages, contract.__name__)
                self.last_provider = secondary.provider
                return result
            except AssistantError:
                raise AssistantError("ALL_LLM_PROVIDERS_FAILED", 503) from first

    def force_fallback(self, stage: str, reason: str) -> bool:
        """Pin subsequent calls in this run to Gemini after a semantic repair failed."""
        if (not self.settings.assistant_failover_enabled or self.settings.assistant_provider != "nvidia"
                or self.last_provider == "gemini" or not self.settings.gemini_api_key):
            return False
        if not self.settings.gemini_api_key.get_secret_value().strip():
            return False
        self._forced_provider = "gemini"
        self.events.append({"provider":"nvidia","stage":stage,"outcome":"failover",
                            "error_code":reason,"timestamp_utc":datetime.now(timezone.utc).isoformat()})
        return True


def wire_schema(contract: type[BaseModel]) -> dict:
    schema = contract.model_json_schema()

    def visit(node):
        if isinstance(node, dict):
            # The backend remains authoritative for constraints not portable
            # across model endpoints' supported JSON Schema subsets.
            for key in ("default", "minimum", "maximum", "exclusiveMinimum", "maxItems", "minItems", "format"):
                node.pop(key, None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)
    return schema


class OpenRouterLLM:
    def __init__(self, settings: AssistantSettings, transport=None):
        self.settings = settings
        self.transport = transport

    async def complete(self, contract: type[BaseModel], messages: list[dict]) -> Completion:
        s = self.settings
        if not s.openrouter_model.strip() or not s.openrouter_api_key or not s.openrouter_api_key.get_secret_value().strip():
            raise AssistantError("OPENROUTER_NOT_CONFIGURED", 503)
        response_format = {"type": "json_object"}
        if s.openrouter_response_format == "json_schema":
            response_format = {"type": "json_schema", "json_schema": {
                "name": contract.__name__, "strict": True, "schema": wire_schema(contract),
            }}
        schema_instruction = {"role": "system", "content": (
            "Return only the data JSON object matching this schema, not the schema itself: "
            + json.dumps(wire_schema(contract), separators=(",", ":")))}
        wire_messages = [messages[0], schema_instruction, *messages[1:]] if messages else [schema_instruction]
        payload = {
            "model": s.openrouter_model,
            "messages": wire_messages,
            "response_format": response_format,
            "provider": {"require_parameters": True, "allow_fallbacks": False},
            "stream": False,
        }
        if s.openrouter_max_tokens is not None:
            payload["max_tokens"] = s.openrouter_max_tokens
        if s.openrouter_reasoning_enabled is not None:
            payload["reasoning"] = {"enabled": s.openrouter_reasoning_enabled}
        started = perf_counter()
        try:
            timeout = httpx.Timeout(None, connect=s.assistant_connect_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": "Bearer " + s.openrouter_api_key.get_secret_value(),
                             "X-OpenRouter-Title": "HOSA LLM Pilot"},
                    json=payload,
                )
        except httpx.TimeoutException as error:
            raise AssistantError("OPENROUTER_TIMEOUT", 504) from error
        except httpx.HTTPError as error:
            raise AssistantError("OPENROUTER_UNAVAILABLE", 502) from error
        if response.status_code != 200:
            # Never forward upstream bodies: they can contain credentials or prompts.
            code = "OPENROUTER_RATE_LIMIT" if response.status_code == 429 else "OPENROUTER_REQUEST_FAILED"
            raise AssistantError(code, 502)
        try:
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise AssistantError("MODEL_OUTPUT_TRUNCATED", 502)
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise ValueError("Incomplete or refused response")
            output = contract.model_validate_json(choice["message"]["content"])
        except ValidationError as error:
            fields = [(item["loc"], item["type"]) for item in error.errors(include_input=False)]
            logging.getLogger(__name__).warning("Structured output rejected: contract=%s fields=%s", contract.__name__, fields)
            raise AssistantError("MODEL_OUTPUT_INVALID", 502) from error
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise AssistantError("MODEL_OUTPUT_INVALID", 502) from error
        usage = body.get("usage") or {}
        usage = {key: value for key, value in usage.items() if key in
                 {"prompt_tokens", "completion_tokens", "total_tokens", "cost"}
                 and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)} if isinstance(usage, dict) else {}
        return Completion(output, body.get("model") or s.openrouter_model,
                          (perf_counter() - started) * 1000, usage,
                          body.get("id"), choice.get("finish_reason"))
