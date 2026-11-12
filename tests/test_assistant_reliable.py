import asyncio
import json
import sys
import threading
import time

import httpx
import pytest
from filelock import FileLock
from pydantic import SecretStr

sys.path.insert(0,"backend")

from app.assistant.chat import ChatStore
from app.assistant.chat_models import ChatTurn
from app.assistant.config import AssistantSettings
from app.assistant.knowledge import ProjectKnowledge
from app.assistant import provider as provider_module
from app.assistant.provider import NativeLLM, ResilientLLM
from app.assistant.chat_service import ChatService
from app.core.errors import DomainError
from app.point_analysis.service import calculate


@pytest.fixture(autouse=True)
def reset_provider_health():
    with provider_module._NVIDIA_HEALTH_LOCK:
        provider_module._NVIDIA_COOLDOWN_UNTIL=0.0
        provider_module._NVIDIA_PROBE_ACTIVE=False
    yield


def chat_json(**changes):
    return json.dumps({"intent":"knowledge","answer":"HOSA compares illumination and Earth line of sight.",
        "clarification":None,"source_ids":[],"query":None,**changes},ensure_ascii=False)


def configured(**changes):
    values={"assistant_enabled":True,"nvidia_api_key":SecretStr("test-nim-key"),
            "gemini_api_key":SecretStr("test-gemini-key"),"_env_file":None,"assistant_streaming":True}
    values.update(changes)
    return AssistantSettings(**values)


def sse(payloads):
    return "".join("data: "+json.dumps(body,ensure_ascii=False)+"\n\n" for body in payloads)+"data: [DONE]\n\n"


def test_nvidia_native_stream_uses_model_reasoning_and_generation_cap():
    seen=[]
    content=chat_json()
    async def handler(request):
        seen.append(request)
        payload=json.loads(request.content)
        assert request.url.host=="integrate.api.nvidia.com"
        assert request.headers["authorization"]=="Bearer test-nim-key"
        assert "test-nim-key" not in request.content.decode()
        assert payload["model"]=="z-ai/glm-5.3-flash"
        assert payload["reasoning_effort"]=="low"
        assert 8192 < payload["max_tokens"] <= 1048576 and payload["stream"] is True
        assert payload["stream_options"]=={"include_usage":True}
        assert payload["chat_template_kwargs"]=={"reasoning_effort":"low","clear_thinking":True}
        assert "enable_thinking" not in payload and "provider" not in payload
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"choices":[{"delta":{"reasoning_content":"hidden reasoning"},"finish_reason":None}]},
            {"choices":[{"delta":{"content":content[:32]},"finish_reason":None}]},
            {"choices":[{"delta":{"content":content[32:]},"finish_reason":"stop"}]},
            {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":20}}]))
    result=asyncio.run(NativeLLM("nvidia",configured(nvidia_model="z-ai/glm-5.3-flash"),httpx.MockTransport(handler)).complete(ChatTurn,[]))
    assert len(seen)==1 and result.output.intent=="knowledge"
    assert result.usage=={"prompt_tokens":10,"completion_tokens":20}


def test_deepseek_v41_flash_disables_thinking_without_glm_template_fields():
    seen=[]
    content=chat_json()
    async def handler(request):
        seen.append(request)
        payload=json.loads(request.content)
        assert payload["model"]=="deepseek-ai/deepseek-v4.1-flash"
        assert payload["reasoning_effort"]=="none"
        assert payload["chat_template_kwargs"]=={"thinking":False}
        assert payload["stream"] is True
        assert payload["stream_options"]=={"include_usage":True}
        assert "clear_thinking" not in payload["chat_template_kwargs"]
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"choices":[{"delta":{"content":content[:40]},"finish_reason":None}]},
            {"choices":[{"delta":{"content":content[40:]},"finish_reason":"stop"}]},
            {"choices":[],"usage":{"prompt_tokens":15,"completion_tokens":24,"total_tokens":39}}]))
    settings=configured()
    result=asyncio.run(NativeLLM("nvidia",settings,httpx.MockTransport(handler)).complete(ChatTurn,[
        {"role":"user","content":"Explain HOSA briefly."}]))
    assert len(seen)==1 and result.output.intent=="knowledge"
    assert result.usage=={"prompt_tokens":15,"completion_tokens":24,"total_tokens":39}


def test_gemini_native_stream_schema_thinking_and_api_key_header():
    seen=[]
    async def handler(request):
        seen.append(request)
        body=json.loads(request.content)
        assert request.url.path.endswith("/models/gemini-3.1-flash-lite:streamGenerateContent")
        assert request.url.params["alt"]=="sse"
        assert request.headers["x-goog-api-key"]=="test-gemini-key"
        assert body["generationConfig"]["maxOutputTokens"]==65536
        assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"]=="MINIMAL"
        assert body["generationConfig"]["responseMimeType"]=="application/json"
        assert body["contents"][0]["role"]=="user"
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"candidates":[{"content":{"parts":[{"text":"hidden thought","thought":True},{"text":chat_json()}]},"finishReason":"STOP"}],
             "usageMetadata":{"promptTokenCount":12,"candidatesTokenCount":22,"totalTokenCount":34}}]))
    result=asyncio.run(NativeLLM("gemini",configured(),httpx.MockTransport(handler)).complete(ChatTurn,[
        {"role":"user","content":"Return a knowledge response about HOSA."}]))
    assert len(seen)==1 and result.output.intent=="knowledge"
    assert result.usage=={"prompt_tokens":12,"completion_tokens":22,"total_tokens":34}


def test_chat_turn_has_no_legacy_fixed_answer_character_cap():
    answer="A"*20000
    turn=ChatTurn.model_validate({"intent":"knowledge","answer":answer,"source_ids":[],"query":None})
    assert len(turn.answer)==20000


def test_nvidia_429_fails_over_immediately_and_records_both_providers():
    calls={"nvidia":0,"gemini":0}
    attempts=[]
    async def nvidia(request):
        calls["nvidia"]+=1
        return httpx.Response(429,headers={"retry-after":"12"},text="secret response body")
    async def gemini(request):
        calls["gemini"]+=1
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"candidates":[{"content":{"parts":[{"text":chat_json()}]},"finishReason":"STOP"}]}]))
    llm=ResilientLLM(configured(),{"nvidia":httpx.MockTransport(nvidia),"gemini":httpx.MockTransport(gemini)},
                     on_attempt=lambda provider,stage,attempt:attempts.append((provider,stage,attempt)))
    response=asyncio.run(llm.complete(ChatTurn,[]))
    assert response.model=="gemini-3.1-flash-lite" and llm.last_provider=="gemini"
    assert calls=={"nvidia":1,"gemini":1}
    assert llm.events[0]["error_code"]=="NVIDIA_RATE_LIMIT"
    assert llm.events[0]["retry_after_seconds"]==12
    assert llm.events[1]["outcome"]=="failover"
    assert [item[0] for item in attempts]==["nvidia","gemini"]
    assert "secret response body" not in repr(llm.events)


def test_nvidia_cooldown_routes_new_run_to_gemini_then_allows_one_probe(monkeypatch):
    calls={"nvidia":0,"gemini":0}
    async def rate_limit(request):
        calls["nvidia"]+=1
        return httpx.Response(429,headers={"retry-after":"30"})
    async def healthy(request):
        calls["nvidia"]+=1
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"choices":[{"delta":{"content":chat_json()},"finish_reason":"stop"}]}]))
    async def gemini(request):
        calls["gemini"]+=1
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"candidates":[{"content":{"parts":[{"text":chat_json()}]},"finishReason":"STOP"}]}]))
    settings=configured()
    first=ResilientLLM(settings,{"nvidia":httpx.MockTransport(rate_limit),"gemini":httpx.MockTransport(gemini)})
    asyncio.run(first.complete(ChatTurn,[]))
    during=ResilientLLM(settings,{"nvidia":httpx.MockTransport(healthy),"gemini":httpx.MockTransport(gemini)})
    asyncio.run(during.complete(ChatTurn,[]))
    assert calls=={"nvidia":1,"gemini":2}
    assert any(event["outcome"]=="cooldown" for event in during.events)
    monkeypatch.setattr(provider_module,"perf_counter",lambda:provider_module._NVIDIA_COOLDOWN_UNTIL+1)
    recovered=ResilientLLM(settings,{"nvidia":httpx.MockTransport(healthy),"gemini":httpx.MockTransport(gemini)})
    asyncio.run(recovered.complete(ChatTurn,[]))
    assert calls=={"nvidia":2,"gemini":2}


def test_invalid_auth_is_not_hidden_by_provider_failover():
    calls={"nvidia":0,"gemini":0}
    async def handler(request):
        calls["nvidia"]+=1
        return httpx.Response(401,text="sensitive")
    async def secondary(request):
        calls["gemini"]+=1
        return httpx.Response(200,json={})
    llm=ResilientLLM(configured(),{"nvidia":httpx.MockTransport(handler),"gemini":httpx.MockTransport(secondary)})
    try:
        asyncio.run(llm.complete(ChatTurn,[]))
        assert False,"expected auth failure"
    except Exception as error:
        assert getattr(error,"code",None)=="NVIDIA_AUTH_FAILED"
    assert calls=={"nvidia":1,"gemini":0}


def test_removed_nvidia_endpoint_is_a_configuration_error_not_a_failover_signal():
    calls={"nvidia":0,"gemini":0}
    async def gone(request):
        calls["nvidia"]+=1
        return httpx.Response(410,headers={"x-request-id":"gone-model"},text="private upstream detail")
    async def secondary(request):
        calls["gemini"]+=1
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"candidates":[{"content":{"parts":[{"text":chat_json()}]},"finishReason":"STOP"}]}]))
    llm=ResilientLLM(configured(),{"nvidia":httpx.MockTransport(gone),"gemini":httpx.MockTransport(secondary)})
    with pytest.raises(Exception) as raised:
        asyncio.run(llm.complete(ChatTurn,[]))
    assert getattr(raised.value,"code",None)=="NVIDIA_ENDPOINT_GONE"
    assert calls=={"nvidia":1,"gemini":0}
    assert llm.events[0]["upstream_status"]==410 and llm.events[0]["request_id"]=="gone-model"
    assert "private upstream detail" not in repr(llm.events)


def test_slow_stream_has_no_application_read_or_total_deadline():
    async def handler(request):
        await asyncio.sleep(.06)
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=sse([
            {"choices":[{"delta":{"content":chat_json()},"finish_reason":"stop"}]}]))
    settings=configured(assistant_connect_timeout_seconds=.01)
    result=asyncio.run(NativeLLM("nvidia",settings,httpx.MockTransport(handler)).complete(ChatTurn,[]))
    assert result.output.intent=="knowledge"


def test_chat_store_sessions_idempotency_events_and_apply_survive_restart(tmp_path):
    path=tmp_path/"chat.sqlite3"
    database=ChatStore(path)
    session=database.create_session()
    run,created=database.begin_run(session["id"],"request-1","What does HOSA do?")
    same,replayed=database.begin_run(session["id"],"request-1","duplicate")
    assert created and not replayed and same["id"]==run["id"]
    database.set_stage(run["id"],"running","retrieving")
    result={"answer":"It compares illumination and geometric Earth visibility.","intent":"knowledge","citations":[]}
    database.finish(run["id"],"completed",result)
    assert [event["id"] for event in database.events_after(run["id"],0)]==[1,2,3]
    assert database.run(run["id"])["result"]==result
    second=ChatStore(path)
    assert second.session(session["id"])["messages"][-1]["content"]==result["answer"]
    restored=second.session(session["id"])
    assert restored["messages"][-1]["run_id"]==run["id"]
    assert restored["runs"][0]["result"]==result
    assert second.run(run["id"])["status"]=="completed"


def test_restart_marks_interrupted_run_without_erasing_messages(tmp_path):
    database=ChatStore(tmp_path/"chat.sqlite3")
    session=database.create_session()
    run,_=database.begin_run(session["id"],"request-2","Compare these sites")
    database.set_stage(run["id"],"running","computing")
    ChatStore(tmp_path/"chat.sqlite3").interrupt_active()
    assert database.run(run["id"])["status"]=="interrupted"
    assert database.events_after(run["id"],0)[-1]["data"]["error_code"]=="PROCESS_RESTARTED"


def test_cancel_is_idempotent_and_completed_run_cannot_be_overwritten(tmp_path):
    database=ChatStore(tmp_path/"chat.sqlite3")
    session=database.create_session()
    run,_=database.begin_run(session["id"],"cancel-case","What is HOSA?")
    database.cancel(run["id"])
    event_count=len(database.events_after(run["id"],0))
    database.cancel(run["id"])
    database.finish(run["id"],"completed",{"answer":"late answer"})
    assert len(database.events_after(run["id"],0))==event_count
    assert database.run(run["id"])["status"]=="cancelled"
    assert all(item["role"]!="assistant" for item in database.session(session["id"])["messages"])


def test_project_knowledge_indexes_sources_and_returns_valid_source_ids(tmp_path):
    root=tmp_path/"project"; (root/"docs").mkdir(parents=True)
    (root/"docs"/"purpose.md").write_text("HOSA compares lunar illumination and Earth-centre line of sight.",encoding="utf-8")
    knowledge=ProjectKnowledge(tmp_path/"index.sqlite3",root,tmp_path/"missing-raw-data")
    report=knowledge.rebuild()
    hits=knowledge.search("Earth visibility HOSA",4)
    assert report["passages"]>=1 and hits
    assert hits[0]["path"]=="docs/purpose.md"
    assert knowledge.source(hits[0]["source_id"])["excerpt"]==hits[0]["excerpt"]


def test_coordinate_calculation_can_cancel_while_waiting_for_process_lock(tmp_path):
    from app.mission.models import MissionRequest
    from app.mission.identity import digest
    root=tmp_path/"pipeline"
    root.mkdir()
    request=MissionRequest(latitude_deg=-89.5,longitude_e_deg=220,
                           start_utc="2026-11-17T00:00:00Z")
    locks=root/"request-locks";locks.mkdir()
    key=digest(request.model_dump(exclude={"offline"}))
    lock=FileLock(str(locks/f"{key}.lock"))
    lock.acquire(timeout=0)
    cancelled=threading.Event()
    errors=[]
    class Pipeline:
        def __init__(self): self.root=root
        def run(self,request,progress): raise AssertionError("cancelled lock waiter must not enter the pipeline")
    thread=threading.Thread(target=lambda: _capture_error(errors,calculate,request,Pipeline(),cancel_event=cancelled))
    thread.start()
    time.sleep(.05)
    cancelled.set()
    thread.join(1)
    lock.release()
    assert not thread.is_alive()
    assert errors and getattr(errors[0],"code",None)=="POINT_ANALYSIS_CANCELLED"


def _capture_error(errors,function,*args,**kwargs):
    try:
        function(*args,**kwargs)
    except Exception as error:
        errors.append(error)


def test_point_chat_cancellation_waits_for_safe_pipeline_checkpoint(monkeypatch,tmp_path):
    started=threading.Event()
    finished=threading.Event()
    checkpoint=[]
    class Pipeline:
        def __init__(self,root): self.root=root
    def slow_calculate(request,pipeline,progress,timeout,cancel_event):
        started.set()
        cancel_event.wait(2)
        finished.set()
        progress("safe_checkpoint")
        return {"result_id":"must-not-publish"}
    monkeypatch.setattr("app.assistant.chat_service.PointAnalysisPipeline",Pipeline)
    monkeypatch.setattr("app.assistant.chat_service.calculate",slow_calculate)
    service=ChatService(object(),ProjectKnowledge(tmp_path/"index.sqlite3",tmp_path/"project",tmp_path/"raw"))
    async def scenario():
        task=asyncio.create_task(service._execute("point",{"site_id":"Site01_P1","start_utc":"2026-11-14T00:00:00Z","duration_hours":24},checkpoint.append))
        assert await asyncio.to_thread(started.wait,1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert finished.is_set() and checkpoint==[]
