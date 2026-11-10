"""HTTP adapters only; deterministic endpoints work without an LLM key."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.errors import DomainError
from .models import CompareRequest, PlanningResult, SearchRequest
from .repository import result_csv
from .service import PlanningService

router = APIRouter(prefix="/planning", tags=["planning"])


def get_planning_service() -> PlanningService:
    return PlanningService()


def http_error(error):
    if isinstance(error, DomainError):
        return HTTPException(error.status_code, detail={"code": error.code})
    return HTTPException(503, detail={"code": "DATA_NOT_READY"})


@router.get("/capabilities")
def capabilities(service: PlanningService = Depends(get_planning_service)):
    try:
        return service.capabilities()
    except (DomainError, OSError, ValueError) as error:
        raise http_error(error) from error


@router.post("/compare", response_model=PlanningResult)
def compare(query: CompareRequest, service: PlanningService = Depends(get_planning_service)):
    try:
        return service.compare(query)
    except (DomainError, OSError, ValueError) as error:
        raise http_error(error) from error


@router.post("/windows/search", response_model=PlanningResult)
def search(query: SearchRequest, service: PlanningService = Depends(get_planning_service)):
    try:
        return service.search(query)
    except (DomainError, OSError, ValueError) as error:
        raise http_error(error) from error


@router.get("/results/{result_id}")
def export(result_id: str, format: Literal["json", "csv"] = "json",
           service: PlanningService = Depends(get_planning_service)):
    try:
        result = service.results.load(result_id)
        content = result_csv(result) if format == "csv" else result.model_dump_json(indent=2)
        return Response(content, media_type="text/csv; charset=utf-8" if format == "csv" else "application/json",
                        headers={"Content-Disposition": f'attachment; filename="planning-{result_id}.{format}"'})
    except (DomainError, OSError, ValueError) as error:
        raise http_error(error) from error
