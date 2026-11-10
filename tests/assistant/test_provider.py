import asyncio
import json

import httpx
import pytest

from app.assistant.config import AssistantSettings
from app.assistant.models import RequestPatch
from app.assistant.provider import AssistantError, OpenRouterLLM, wire_schema
from conftest import default_patch


def configured():
    return AssistantSettings(openrouter_api_key="unit-test-secret", openrouter_model="test/provider-model", _env_file=None)


def test_env_model_and_strict_schema_are_forwarded_once():
    requests = []
    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert payload["model"] == "test/provider-model"
        assert payload["provider"] == {"require_parameters": True, "allow_fallbacks": False}
        assert payload["response_format"]["json_schema"]["strict"]
        assert request.headers["authorization"] == "Bearer unit-test-secret"
        assert "unit-test-secret" not in request.content.decode()
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": default_patch().model_dump_json()}}]})
    result = asyncio.run(OpenRouterLLM(configured(), httpx.MockTransport(handler)).complete(RequestPatch, []))
    assert result.model == "test/provider-model" and len(requests) == 1
    assert set(wire_schema(RequestPatch)["required"]) == set(RequestPatch.model_fields)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_upstream_errors_are_sanitized_without_retry(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="sensitive upstream unit-test-secret")
    with pytest.raises(AssistantError) as error:
        asyncio.run(OpenRouterLLM(configured(), httpx.MockTransport(handler)).complete(RequestPatch, []))
    assert "unit-test-secret" not in str(error.value) and len(calls) == 1


@pytest.mark.parametrize("content,finish", [("not json", "stop"), ("{}", "stop"), ("{}", "length")])
def test_invalid_or_truncated_outputs_are_rejected(content, finish):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]})
    with pytest.raises(AssistantError, match="MODEL_OUTPUT_"):
        asyncio.run(OpenRouterLLM(configured(), httpx.MockTransport(handler)).complete(RequestPatch, []))


def test_timeout_and_missing_configuration():
    def handler(request):
        raise httpx.ReadTimeout("unit-test-secret", request=request)
    with pytest.raises(AssistantError, match="OPENROUTER_TIMEOUT"):
        asyncio.run(OpenRouterLLM(configured(), httpx.MockTransport(handler)).complete(RequestPatch, []))
    with pytest.raises(AssistantError, match="OPENROUTER_NOT_CONFIGURED"):
        asyncio.run(OpenRouterLLM(AssistantSettings(_env_file=None)).complete(RequestPatch, []))


def test_settings_read_env_file_without_exposing_secret(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ASSISTANT_ENABLED=true\nOPENROUTER_API_KEY=unit-test-secret\nOPENROUTER_MODEL=vendor/configured-model\n", encoding="utf-8")
    settings = AssistantSettings(_env_file=env)
    assert settings.assistant_enabled and settings.openrouter_model == "vendor/configured-model"
    assert settings.openrouter_api_key.get_secret_value() == "unit-test-secret"
    assert "unit-test-secret" not in repr(settings)


def test_json_object_mode_still_supplies_the_schema_and_optional_reasoning():
    settings = configured().model_copy(update={"openrouter_response_format":"json_object","openrouter_reasoning_enabled":False})
    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type":"json_object"}
        assert payload["reasoning"] == {"enabled":False}
        assert "search_from_utc" in payload["messages"][0]["content"]
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":default_patch().model_dump_json()}}]})
    result = asyncio.run(OpenRouterLLM(settings,httpx.MockTransport(handler)).complete(RequestPatch,[]))
    assert result.output.arrival_shift_days == 3


def test_truncation_is_distinct_from_schema_rejection():
    def handler(request):
        return httpx.Response(200,json={"choices":[{"finish_reason":"length","message":{"content":"{}"}}]})
    with pytest.raises(AssistantError,match="MODEL_OUTPUT_TRUNCATED"):
        asyncio.run(OpenRouterLLM(configured(),httpx.MockTransport(handler)).complete(RequestPatch,[]))


def test_total_deadline_bounds_a_slow_response():
    settings = configured().model_copy(update={"openrouter_timeout_seconds":0.01})
    async def handler(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200,json={})
    with pytest.raises(AssistantError,match="OPENROUTER_TIMEOUT"):
        asyncio.run(OpenRouterLLM(settings,httpx.MockTransport(handler)).complete(RequestPatch,[]))
