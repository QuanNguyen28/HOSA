"""OpenAI-compatible proxy contracts and semantic retrieval regressions (no live calls)."""
import asyncio
import json
import sys
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, "backend")
from app.assistant.chat_models import ChatTurn, RetrievalPlan
from app.assistant.chat_service import ChatService
from app.assistant.config import AssistantSettings
from app.assistant.knowledge import ProjectKnowledge
from app.assistant.provider import AssistantError, NativeLLM, ResilientLLM, wire_schema


def configured(**changes):
    return AssistantSettings(_env_file=None, assistant_provider="openai", llm_proxy_api_key="proxy-test-secret",
        llm_proxy_base_url="https://proxy.example/v1", llm_proxy_model="proxy/model", **changes)


def test_proxy_stream_has_only_portable_fields_and_no_read_deadline():
    answer = ChatTurn(intent="knowledge", answer="Địa hình có thể che khuất đường nhìn.").model_dump_json()
    async def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://proxy.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer proxy-test-secret"
        assert set(body) == {"model", "messages", "stream", "stream_options", "response_format"}
        assert body["model"] == "proxy/model" and body["stream"]
        assert body["response_format"]["json_schema"]["strict"]
        assert request.extensions["timeout"]["read"] is None
        # Splitting the network bytes inside UTF-8 characters is handled by httpx's line decoder.
        data = "".join("data: " + json.dumps(item, ensure_ascii=False) + "\n\n" for item in [
            {"model":"proxy/model", "choices":[{"delta":{"reasoning_content":"private thought"}}]},
            {"choices":[{"delta":{"content":answer[:43]}}]},
            {"choices":[{"delta":{"content":answer[43:]}, "finish_reason":"stop"}]},
            {"choices":[], "usage":{"prompt_tokens":20, "completion_tokens":40}},
        ]) + "data: [DONE]\n\n"
        class Bytes(httpx.AsyncByteStream):
            async def __aiter__(self):
                raw = data.encode()
                for start in range(0, len(raw), 7):
                    yield raw[start:start+7]
        return httpx.Response(200, stream=Bytes(), headers={"x-request-id":"upstream-id"})
    result = asyncio.run(NativeLLM("openai", configured(), httpx.MockTransport(handler)).complete(ChatTurn, []))
    assert result.output.answer == "Địa hình có thể che khuất đường nhìn."
    assert result.request_id == "upstream-id" and result.finish_reason == "stop"
    assert result.usage == {"prompt_tokens":20, "completion_tokens":40}
    assert "private thought" not in result.output.model_dump_json()


@pytest.mark.parametrize("status,code", [(401,"OPENAI_AUTH_FAILED"), (403,"OPENAI_AUTH_FAILED"),
    (400,"OPENAI_INVALID_REQUEST"), (404,"OPENAI_MODEL_NOT_FOUND"), (429,"OPENAI_RATE_LIMIT")])
def test_proxy_errors_are_traced_without_cross_provider_fallback(status, code):
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private proxy-test-secret", headers={"retry-after":"9"})
    llm = ResilientLLM(configured(), {"openai":httpx.MockTransport(handler)})
    with pytest.raises(AssistantError, match=code):
        asyncio.run(llm.complete(ChatTurn, []))
    assert len(calls) == 1
    assert all(e["provider"] == "openai" for e in llm.events)
    assert "proxy-test-secret" not in repr(llm.events)


def test_proxy_repairs_one_invalid_stream_then_records_actual_model():
    calls = []
    async def handler(request):
        calls.append(request)
        content = "{}" if len(calls) == 1 else ChatTurn(intent="knowledge",answer="Evidence first.").model_dump_json()
        return httpx.Response(200, text="data: " + json.dumps({"model":"served-model", "choices":[
            {"delta":{"content":content}, "finish_reason":"stop"}]}) + "\n\ndata: [DONE]\n\n")
    llm = ResilientLLM(configured(), {"openai":httpx.MockTransport(handler)})
    result = asyncio.run(llm.complete(ChatTurn, []))
    assert len(calls) == 2 and result.model == "served-model"
    assert llm.events[-1]["attempt"] == 2 and llm.last_provider == "openai"


def test_proxy_environment_is_independent_of_host_openai_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-host-secret")
    env = tmp_path / ".env"
    env.write_text("LLM_PROXY_API_KEY=worktree-secret\nLLM_PROXY_MODEL=worktree-model\n")
    s = AssistantSettings(_env_file=env)
    assert s.llm_proxy_api_key.get_secret_value() == "worktree-secret"
    assert "worktree-secret" not in repr(s)


def test_wire_schema_keeps_dynamic_tool_arguments_open_for_backend_validation():
    query = wire_schema(ChatTurn)["properties"]["query"]["anyOf"][0]
    assert query["type"] == "object" and query["additionalProperties"] is True
    assert "required" not in query


@pytest.mark.parametrize("base", ["http://proxy.example/v1", "https://user:password@proxy.example/v1",
                                  "https://proxy.example/v1?key=secret"])
def test_unsafe_proxy_base_is_rejected_before_network(base):
    s = configured().model_copy(update={"llm_proxy_base_url":base})
    with pytest.raises(AssistantError, match="OPENAI_INVALID_BASE_URL"):
        NativeLLM("openai",s)._request(ChatTurn, [])


def test_semantic_retrieval_resolves_followup_but_never_executes_model_text(monkeypatch):
    queries = []
    context = {"source_id":"orientation", "path":"current.md", "excerpt":"Project purpose"}
    def search(text, limit):
        queries.append(text)
        return [{"source_id":"contact-doc", "path":"contact.md", "excerpt":"Continuity matters."}]
    class QueryLLM:
        async def complete(self, contract, messages):
            assert contract is RetrievalPlan
            payload = json.loads(messages[-1]["content"])
            assert payload["recent_conversation"][0]["content"] == "Tôi cần liên lạc liên tục."
            assert payload["question"] == "Thế chỉ số tổng kia đủ chưa?"
            return SimpleNamespace(output=RetrievalPlan(queries=["Earth LOS continuous contact windows", "setup first contact deadline"]))
    knowledge = SimpleNamespace(search=search, context_sources=lambda:[context])
    service = ChatService(object(), knowledge, retrieval_llm=QueryLLM())
    sources = asyncio.run(service._retrieve("Thế chỉ số tổng kia đủ chưa?",
        [{"role":"user", "content":"Tôi cần liên lạc liên tục."}], {}))
    assert queries == ["Earth LOS continuous contact windows", "setup first contact deadline"]
    assert {s["source_id"] for s in sources} == {"contact-doc","orientation"}
    assert len(sources) == 2  # Duplicate retrieval hits retain their real source ID.


def test_orientation_is_indexed_with_current_source_hash_and_versioned_citations(tmp_path):
    root = tmp_path / "project"
    folder = root / "docs/assistant"
    folder.mkdir(parents=True)
    path = folder / "decision-support-guide.md"
    path.write_text("Visibility is not a radio link budget.")
    knowledge = ProjectKnowledge(tmp_path/"index.db", root)
    knowledge.rebuild()
    first = knowledge.context_sources()[0]
    assert knowledge.source(first["source_id"])["source_hash"] == first["source_hash"]
    assert first["source_status"] == "current"
    path.write_text("The current guide has changed.")
    knowledge.rebuild()
    assert knowledge.context_sources()[0]["source_id"] != first["source_id"]


@pytest.mark.parametrize("streaming", [True,False])
def test_proxy_preserves_body_completion_id_when_request_header_is_absent(streaming):
    async def handler(request):
        answer = ChatTurn(intent="knowledge", answer="Source-grounded answer.").model_dump_json()
        choice = {"finish_reason":"stop", "delta":{"content":answer}} if streaming else {
            "finish_reason":"stop", "message":{"content":answer}}
        body = {"id":"proxy-completion-id", "choices":[choice]}
        return httpx.Response(200, text="data: "+json.dumps(body)+"\n\ndata: [DONE]\n\n") if streaming else httpx.Response(200,json=body)
    result = asyncio.run(NativeLLM("openai",configured(assistant_streaming=streaming),httpx.MockTransport(handler)).complete(ChatTurn,[]))
    assert result.request_id == "proxy-completion-id"


@pytest.mark.parametrize("failure", ["ConnectError","ReadError","RemoteProtocolError","http_503"])
def test_transient_proxy_failure_retries_once_after_delay_without_schema_repair(monkeypatch, caplog, failure):
    requests, delays = [], []
    async def sleep(seconds):
        delays.append(seconds)
    monkeypatch.setattr(asyncio,"sleep",sleep)
    async def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            if failure == "http_503":
                return httpx.Response(503,text="private proxy-test-secret",headers={"x-request-id":"gateway-id"})
            raise getattr(httpx,failure)("private proxy-test-secret",request=request)
        content=ChatTurn(intent="knowledge",answer="Recovered real response contract.").model_dump_json()
        return httpx.Response(200,text="data: "+json.dumps({"choices":[
            {"delta":{"content":content},"finish_reason":"stop"}]})+"\n\ndata: [DONE]\n\n")
    llm=ResilientLLM(configured(),{"openai":httpx.MockTransport(handler)})
    result=asyncio.run(llm.complete(ChatTurn,[{"role":"user","content":"A focused question."}]))
    assert result.output.answer == "Recovered real response contract."
    assert len(requests)==2 and requests[0]["messages"]==requests[1]["messages"]
    assert delays==[1] and llm.events[-1]["attempt"]==2
    error=llm.events[0]
    assert error["error_code"]=="OPENAI_UNAVAILABLE"
    assert error["upstream_status"]==503 if failure=="http_503" else error["transport_error"]==failure
    assert "proxy-test-secret" not in caplog.text and "proxy-test-secret" not in repr(llm.events)


def test_persistent_proxy_outage_stops_after_one_retry(monkeypatch):
    calls=[]
    async def sleep(seconds):
        pass
    monkeypatch.setattr(asyncio,"sleep",sleep)
    async def handler(request):
        calls.append(request)
        return httpx.Response(503,text="private upstream body")
    llm=ResilientLLM(configured(),{"openai":httpx.MockTransport(handler)})
    with pytest.raises(AssistantError,match="OPENAI_UNAVAILABLE"):
        asyncio.run(llm.complete(ChatTurn,[]))
    assert len(calls)==2 and all(e["provider"]=="openai" for e in llm.events)
