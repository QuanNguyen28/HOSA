from fastapi import APIRouter

from app.core.config import settings
from app.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a lightweight liveness response without touching external services."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.app_version,
    )
