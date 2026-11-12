"""Probe configured NIM/Gemini model availability and one real structured stream."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def nim_model_info(body: object, model: str) -> dict:
    entries = body.get("data", []) if isinstance(body, dict) else []
    ids = [item.get("id") for item in entries if isinstance(item, dict) and isinstance(item.get("id"), str)]
    return {"models_visible": len(ids), "model_listed": model in ids,
            "related_model_ids": [item for item in ids if "glm" in item.casefold()]}


def gemini_model_info(body: object) -> dict:
    if not isinstance(body, dict):
        return {}
    return {key: body[key] for key in ("name", "inputTokenLimit", "outputTokenLimit", "supportedGenerationMethods")
            if key in body}


async def probe(provider: str, infer: bool = True) -> dict:
    from app.assistant.chat_models import ChatTurn
    from app.assistant.config import get_assistant_settings
    from app.assistant.provider import AssistantError, NativeLLM

    settings = get_assistant_settings()
    model = settings.nvidia_model if provider == "nvidia" else settings.gemini_model
    secret = settings.nvidia_api_key if provider == "nvidia" else settings.gemini_api_key
    profile = {"provider": provider, "model_requested": model, "checked_utc": utc_now(),
               "credential_configured": bool(secret and secret.get_secret_value().strip()),
               "inference_attempted": False, "inference_passed": False}
    if not secret or not secret.get_secret_value().strip():
        profile["failure_code"] = "CREDENTIAL_MISSING"
        return profile

    timeout = httpx.Timeout(connect=settings.assistant_connect_timeout_seconds, read=30, write=15, pool=15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if provider == "nvidia":
                response = await client.get(settings.nvidia_base_url.rstrip("/") + "/models",
                    headers={"Authorization": "Bearer " + secret.get_secret_value().strip()})
                profile["catalog_http_status"] = response.status_code
                profile["request_id"] = response.headers.get("x-request-id") or response.headers.get("request-id")
                if response.is_success:
                    profile.update(nim_model_info(response.json(), model))
                else:
                    profile["failure_code"] = "NVIDIA_MODEL_CATALOG_UNAVAILABLE"
            else:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
                response = await client.get(endpoint, headers={"x-goog-api-key": secret.get_secret_value().strip()})
                profile["catalog_http_status"] = response.status_code
                profile["request_id"] = response.headers.get("x-goog-request-id") or response.headers.get("x-request-id")
                if response.is_success:
                    profile["model_capabilities"] = gemini_model_info(response.json())
                else:
                    profile["failure_code"] = "GEMINI_MODEL_METADATA_UNAVAILABLE"
        except httpx.HTTPError as error:
            profile["failure_code"] = f"{provider.upper()}_CATALOG_NETWORK_ERROR"
            profile["failure_type"] = type(error).__name__
            return profile

        catalog_ok = response.is_success
        model_available = (profile.get("model_listed", False) if provider == "nvidia"
                           else "generateContent" in profile.get("model_capabilities", {}).get("supportedGenerationMethods", []))
        profile["model_available"] = model_available
        if not catalog_ok or not model_available:
            profile.setdefault("failure_code", "MODEL_NOT_AVAILABLE_TO_CREDENTIAL")
            return profile
        if not infer:
            profile["status"] = "catalog_only"
            return profile

        profile["inference_attempted"] = True
        adapter = NativeLLM(provider, settings, client=client)
        try:
            completion = await adapter.complete(ChatTurn, [
                {"role": "system", "content": "Reply in English. This is only a provider smoke test."},
                {"role": "user", "content": "Return intent=knowledge and say HOSA smoke check in answer."},
            ])
            profile.update({"inference_passed": completion.output.intent == "knowledge" and
                            "smoke check" in completion.output.answer.casefold(),
                            "model_reported": completion.model, "finish_reason": completion.finish_reason,
                            "usage": completion.usage, "latency_ms": round(completion.latency_ms, 1),
                            "request_id": completion.request_id})
            if not profile["inference_passed"]:
                profile["failure_code"] = "STRUCTURED_STREAM_CHECK_FAILED"
        except AssistantError as error:
            profile["failure_code"] = error.code
            profile["upstream_status"] = getattr(error, "upstream_status", None)
            profile["request_id"] = getattr(error, "request_id", None) or profile.get("request_id")
        return profile


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("nvidia", "gemini"), required=True)
    parser.add_argument("--catalog-only", action="store_true", help="Inspect model availability without generation")
    args = parser.parse_args(argv)
    import asyncio
    profile = asyncio.run(probe(args.provider, infer=not args.catalog_only))
    output = ROOT / "data/cache/assistant" / f"provider-preflight-{args.provider}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: profile.get(key) for key in ("provider", "model_requested", "catalog_http_status",
        "models_visible", "model_listed", "model_capabilities", "inference_attempted", "inference_passed",
        "model_reported", "finish_reason", "usage", "failure_code", "upstream_status") if key in profile},
        ensure_ascii=True))
    print(f"Capability profile saved: {output}")
    passed = profile.get("inference_passed") if profile.get("inference_attempted") else profile.get("model_available")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
