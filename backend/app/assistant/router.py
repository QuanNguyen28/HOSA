from fastapi import APIRouter, Depends, HTTPException

from .config import AssistantSettings, get_assistant_settings
from .engine import PlanningAdapter
from .models import EvaluateRequest, EvaluateResponse, ParseRequest, ParseResponse
from .provider import AssistantError, OpenRouterLLM
from .service import AssistantService
from .store import store

router = APIRouter(prefix="/assistant", tags=["assistant"])


def get_service(settings: AssistantSettings = Depends(get_assistant_settings)) -> AssistantService:
    if not settings.assistant_enabled:
        raise HTTPException(status_code=503, detail={"code": "ASSISTANT_DISABLED"})
    return AssistantService(settings, OpenRouterLLM(settings), store)


@router.get("/capabilities")
def capabilities(settings: AssistantSettings = Depends(get_assistant_settings)) -> dict:
    try:
        return {"assistant_enabled": settings.assistant_enabled, **PlanningAdapter().capabilities()}
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=503, detail={"code": "DATA_NOT_READY"}) from error


@router.post("/parse", response_model=ParseResponse)
async def parse(request: ParseRequest, service: AssistantService = Depends(get_service)):
    try:
        return await service.parse(request)
    except AssistantError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail={"code": "DATA_NOT_READY"}) from error


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest, service: AssistantService = Depends(get_service)):
    try:
        return await service.evaluate(request)
    except AssistantError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail={"code": "DATA_NOT_READY"}) from error
