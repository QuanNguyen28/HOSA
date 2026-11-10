"""One HTTP request per call, no retry/repair/model fallback loop."""
import math
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from .config import AssistantSettings


class AssistantError(Exception):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True)
class Completion:
    output: BaseModel
    model: str
    latency_ms: float
    usage: dict


class JsonLLM(Protocol):
    async def complete(self, contract: type[BaseModel], messages: list[dict]) -> Completion: ...


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
        payload = {
            "model": s.openrouter_model,
            "messages": messages,
            "response_format": response_format,
            "provider": {"require_parameters": True, "allow_fallbacks": False},
            "max_tokens": s.openrouter_max_tokens,
            "stream": False,
        }
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=s.openrouter_timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": "Bearer " + s.openrouter_api_key.get_secret_value(),
                             "X-OpenRouter-Title": "LunarSight LLM Pilot"},
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
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise ValueError("Incomplete or refused response")
            output = contract.model_validate_json(choice["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as error:
            raise AssistantError("MODEL_OUTPUT_INVALID", 502) from error
        usage = body.get("usage") or {}
        usage = {key: value for key, value in usage.items() if key in
                 {"prompt_tokens", "completion_tokens", "total_tokens", "cost"}
                 and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)} if isinstance(usage, dict) else {}
        return Completion(output, s.openrouter_model, (perf_counter() - started) * 1000, usage)
