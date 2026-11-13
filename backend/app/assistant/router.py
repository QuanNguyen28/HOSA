import asyncio
import json
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .chat import ChatStore, default_database
from .chat_models import ApplyPlan, NewMessage
from .chat_service import ChatService, assistant_brand_text
from .config import AssistantSettings, get_assistant_settings
from .engine import PlanningAdapter
from .knowledge import ProjectKnowledge
from .models import EvaluateRequest, EvaluateResponse, ParseRequest, ParseResponse
from .provider import AssistantError, ResilientLLM
from app.planning.models import CompareRequest, SearchRequest
from app.planning.service import PlanningService
from .service import AssistantService
from .store import store

router = APIRouter(prefix="/assistant", tags=["assistant"])
_ACTIVE_TASKS: dict[str,asyncio.Task] = {}


@lru_cache
def _chat_store(path: str) -> ChatStore:
    database=ChatStore(path)
    # Runs owned by a previous process are never advertised as still running.
    database.interrupt_active()
    return database


def _require_enabled(settings: AssistantSettings):
    if not settings.assistant_enabled:
        raise HTTPException(status_code=503, detail={"code":"ASSISTANT_DISABLED"})


def get_service(request: Request, settings: AssistantSettings = Depends(get_assistant_settings)) -> AssistantService:
    _require_enabled(settings)
    return AssistantService(settings, ResilientLLM(settings, clients=getattr(request.app.state,"llm_clients",{})), store)


@router.get("/capabilities")
def capabilities(settings: AssistantSettings = Depends(get_assistant_settings)) -> dict:
    try:
        provider_ready = (bool(settings.nvidia_api_key and settings.nvidia_api_key.get_secret_value().strip())
                          if settings.assistant_provider=="nvidia" else
                          bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip())
                          if settings.assistant_provider=="gemini" else
                          bool(settings.llm_proxy_api_key and settings.llm_proxy_api_key.get_secret_value().strip()
                               and settings.llm_proxy_model and settings.llm_proxy_base_url)
                          if settings.assistant_provider=="openai" else
                          bool(settings.openrouter_api_key and settings.openrouter_model))
        primary_model = (settings.nvidia_model if settings.assistant_provider=="nvidia" else
                         settings.llm_proxy_model if settings.assistant_provider=="openai" else
                         settings.gemini_model if settings.assistant_provider=="gemini" else settings.openrouter_model)
        return {"assistant_enabled":settings.assistant_enabled,"provider":settings.assistant_provider,
                "provider_configured":provider_ready,"primary_model":primary_model,
                "fallback_model":settings.gemini_model if settings.assistant_provider=="nvidia" and settings.assistant_failover_enabled else None,
                "fallback_configured":bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip()),
                "streaming":settings.assistant_streaming,"generation_deadline":None,
                **PlanningAdapter().capabilities()}
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=503, detail={"code":"DATA_NOT_READY"}) from error


@router.post("/parse", response_model=ParseResponse)
async def parse(request: ParseRequest, service: AssistantService = Depends(get_service)):
    try:
        return await service.parse(request)
    except AssistantError as error:
        raise HTTPException(status_code=error.status_code, detail={"code":error.code}) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail={"code":"DATA_NOT_READY"}) from error


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest, service: AssistantService = Depends(get_service)):
    try:
        return await service.evaluate(request)
    except AssistantError as error:
        raise HTTPException(status_code=error.status_code, detail={"code":error.code}) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail={"code":"DATA_NOT_READY"}) from error


@router.post("/sessions", status_code=201)
def create_session(settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    return _chat_store(str(default_database(settings))).create_session()


@router.get("/sessions/{session_id}")
def read_session(session_id: str, settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    session=_chat_store(str(default_database(settings))).session(session_id)
    if not session:
        raise HTTPException(status_code=404,detail={"code":"SESSION_NOT_FOUND"})
    for message in session["messages"]:
        if message["role"] == "assistant":
            message["content"] = assistant_brand_text(message["content"])
    return session


async def _run_chat(store_: ChatStore, run_id: str, session_id: str, settings: AssistantSettings,
                    clients: dict[str,object] | None = None, *, knowledge_only: bool = False):
    llm=None
    database=store_.session(session_id)
    try:
        store_.set_stage(run_id,"running","retrieving")
        messages=database["messages"] if database else []
        user_index=next((index for index in range(len(messages)-1,-1,-1)
                         if messages[index].get("run_id")==run_id and messages[index]["role"]=="user"),None)
        if user_index is None:
            raise AssistantError("RUN_MESSAGE_NOT_FOUND",500)
        history=[{"role":item["role"],"content":assistant_brand_text(item["content"])
                  if item["role"] == "assistant" else item["content"]}
                 for item in messages[:user_index] if item["role"] in {"user","assistant"}][-24:]
        user_text=messages[user_index]["content"]
        history_archive=[]
        for prior in (database.get("runs",[]) if database else []):
            if prior["id"]==run_id:
                continue
            prior_result=prior.get("result") or {}
            prior_engine=prior_result.get("result") or {}
            history_archive.append({"run_id":prior["id"],"status":prior["status"],
                "intent":prior_result.get("intent"),"query":prior_result.get("query"),
                "answer_summary":assistant_brand_text(prior_result.get("answer",""))[:240],
                "result_id":prior_engine.get("result_id"),"result_status":prior_engine.get("status") or prior_engine.get("decision"),
                "source_ids":[item.get("source_id") for item in prior_result.get("citations",[]) if item.get("source_id")]})
        working_state={**(database.get("working_state",{}) if database else {}),
                       "history_archive":history_archive[-50:]}
        llm=ResilientLLM(settings,clients=clients,
            on_attempt=lambda provider,stage,attempt:store_.set_stage(run_id,"running",f"generating_{provider}"))
        chat=ChatService(llm,ProjectKnowledge(raw_root=settings.lunarsight_raw_dataset_path or None),
                         retrieval_llm=llm,review_answers=settings.assistant_answer_review)
        store_.set_stage(run_id,"running","understanding")
        result=await chat.respond(user_text,history,working_state,
                                  progress=lambda stage:store_.set_stage(run_id,"running",stage),
                                  knowledge_only=knowledge_only)
        result["trace"]=llm.events
        result["provider"]=llm.last_provider
        result["model"]=next((event.get("model") for event in reversed(llm.events)
                              if event.get("outcome")=="success" and event.get("provider")==llm.last_provider),None)
        if result["status"] in {"completed","partial"}:
            state={**working_state,"intent":result.get("intent"),"provider":llm.last_provider}
            if result.get("query") is not None:
                state["query"]=result["query"]
            engine_result=result.get("result") or {}
            if engine_result.get("result_id"):
                state["result_id"]=engine_result["result_id"]
                state["result_status"]=engine_result.get("status") or engine_result.get("decision")
                state["last_engine_evidence"]=result.get("evidence",{})
            state["last_answer_summary"]=result.get("answer","")[:240]
            store_.update_working(session_id,state)
            store_.finish(run_id,result["status"],result)
        else:
            store_.finish(run_id,"needs_input",result)
    except asyncio.CancelledError:
        store_.cancel(run_id)
        raise
    except AssistantError as error:
        # Keep error details sanitized while preserving an explicit retryable state.
        details={"answer":"Không thể hoàn thành lượt LLM. Kiểm tra cấu hình provider hoặc thử lại.",
                 "provider":llm.last_provider if llm else None,"trace":llm.events if llm else []}
        store_.finish(run_id,"failed",result=details,error_code=error.code)
    except (OSError,ValueError) as error:
        code="DATA_NOT_READY" if isinstance(error,OSError) else "CHAT_REQUEST_INVALID"
        store_.finish(run_id,"failed",result={"provider":llm.last_provider if llm else None,
                     "trace":llm.events if llm else []},error_code=code)
    except Exception:
        store_.finish(run_id,"failed",result={"provider":llm.last_provider if llm else None,
                     "trace":llm.events if llm else []},error_code="CHAT_RUN_FAILED")


@router.post("/sessions/{session_id}/messages",status_code=202)
async def post_message(session_id: str, app_request: Request, request: NewMessage,
                       idempotency_key: str = Header(alias="Idempotency-Key"),
                       settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    if not idempotency_key.strip() or len(idempotency_key)>128:
        raise HTTPException(status_code=400,detail={"code":"INVALID_IDEMPOTENCY_KEY"})
    database=_chat_store(str(default_database(settings)))
    try:
        run,created=database.begin_run(session_id,idempotency_key,request.text)
    except KeyError as error:
        raise HTTPException(status_code=404,detail={"code":"SESSION_NOT_FOUND"}) from error
    if created:
        task=asyncio.create_task(_run_chat(database,run["id"],session_id,settings,
            getattr(app_request.app.state,"llm_clients",{}),knowledge_only=request.knowledge_only))
        _ACTIVE_TASKS[run["id"]]=task
        task.add_done_callback(lambda _task,identifier=run["id"]:_ACTIVE_TASKS.pop(identifier,None))
    return {**run,"replayed":not created}


@router.get("/runs/{run_id}")
def read_run(run_id: str, settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    run=_chat_store(str(default_database(settings))).run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail={"code":"RUN_NOT_FOUND"})
    return run


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, after: int = Query(default=0,ge=0),
                     last_event_id: str | None = Header(default=None,alias="Last-Event-ID"),
                     settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    database=_chat_store(str(default_database(settings)))
    if not database.run(run_id):
        raise HTTPException(status_code=404,detail={"code":"RUN_NOT_FOUND"})
    async def stream():
        try:
            cursor=max(after,int(last_event_id or 0))
        except ValueError:
            cursor=after
        while True:
            events=database.events_after(run_id,cursor)
            for item in events:
                cursor=item["id"]
                yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(item['data'],ensure_ascii=False)}\n\n"
            run=database.run(run_id)
            if run and run["status"] in {"completed","needs_input","partial","failed","cancelled","interrupted"}:
                yield "event: complete\ndata: {}\n\n"
                return
            if not events:
                yield ": heartbeat\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    database=_chat_store(str(default_database(settings)))
    run=database.run(run_id)
    if not run:
        raise HTTPException(status_code=404,detail={"code":"RUN_NOT_FOUND"})
    database.cancel(run_id)
    task=_ACTIVE_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()
    return {"run_id":run_id,"status":database.run(run_id)["status"]}


@router.post("/sessions/{session_id}/apply")
def apply_candidate(session_id: str, request: ApplyPlan,
                    settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    database=_chat_store(str(default_database(settings)))
    session=database.session(session_id)
    run=database.run(request.run_id)
    if not session or not run or run["session_id"]!=session_id:
        raise HTTPException(status_code=404,detail={"code":"SESSION_OR_RUN_NOT_FOUND"})
    if session["applied_state"] != request.expected_applied_state:
        raise HTTPException(status_code=409,detail={"code":"STALE_APPLIED_STATE"})
    result=run["result"].get("result") if run.get("result") else None
    if not result or not result.get("apply_allowed"):
        raise HTTPException(status_code=409,detail={"code":"CANDIDATE_NOT_APPLICABLE"})
    query=run["result"].get("query")
    intent=run["result"].get("intent")
    try:
        typed_query=SearchRequest.model_validate(query) if intent=="search" else CompareRequest.model_validate(query)
        current_source_hash=PlanningService().source_capabilities(typed_query)["source_hash"]
    except (ValueError,KeyError,TypeError,OSError) as error:
        raise HTTPException(status_code=409,detail={"code":"CANDIDATE_SOURCE_UNAVAILABLE"}) from error
    if current_source_hash!=result.get("source_hash"):
        raise HTTPException(status_code=409,detail={"code":"STALE_SOURCE_HASH"})
    candidate=next((item for item in result.get("candidates",[]) if item.get("candidate_id")==request.candidate.get("candidate_id")),None)
    if candidate is None or candidate.get("decision")!="PASS":
        raise HTTPException(status_code=409,detail={"code":"CANDIDATE_NOT_APPLICABLE"})
    applied={"run_id":request.run_id,"result_id":result.get("result_id"),"source_hash":result.get("source_hash"),
             "candidate":candidate,"query":run["result"].get("query")}
    database.apply(session_id,applied)
    return {"applied_state":applied}


@router.get("/sources/{source_id}")
def read_source(source_id: str, settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    source=ProjectKnowledge(raw_root=settings.lunarsight_raw_dataset_path or None).source(source_id)
    if source is None:
        raise HTTPException(status_code=404,detail={"code":"SOURCE_NOT_FOUND"})
    return source


@router.post("/knowledge/reindex")
def reindex_knowledge(settings: AssistantSettings = Depends(get_assistant_settings)):
    _require_enabled(settings)
    return ProjectKnowledge(raw_root=settings.lunarsight_raw_dataset_path or None).rebuild()
