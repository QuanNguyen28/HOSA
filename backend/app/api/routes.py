import json

from fastapi import APIRouter, Body, HTTPException, Query, Response

from app.core.config import settings
from app.models.health import HealthResponse
from app.services.lunarsight.catalog import (
    coverage_summary,
    site_analysis,
    site_catalog,
    site_timeline,
)
from app.services.lunarsight.point import sample_terrain, terrain_window
from app.services.lunarsight.planning import (
    analyze_request,
    load_result,
    result_csv,
    scenarios,
    site_profile,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a lightweight liveness response without touching external services."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.app_version,
    )


@router.get("/lunar/sites", tags=["lunar"])
def lunar_sites() -> dict:
    """Return the immutable candidate-site catalog and its provenance."""
    try:
        return site_catalog()
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/lunar/coverage", tags=["lunar"])
def lunar_coverage() -> dict:
    """Describe where visualization and scientific analysis are supported."""
    return coverage_summary()


@router.get("/scenarios", tags=["lunar"])
@router.get("/lunar/scenarios", tags=["lunar"], include_in_schema=False)
def lunar_scenarios() -> dict:
    """Return the immutable MVP scenario and its supported start grid."""
    try:
        return scenarios()
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/sites/{site_id}/profile", tags=["lunar"])
@router.get("/lunar/sites/{site_id}/profile", tags=["lunar"], include_in_schema=False)
def lunar_site_profile(
    site_id: str,
    target: str = Query(default="sun", pattern="^(sun|earth)$"),
) -> dict:
    """Return the validated terrain horizon used for Sun or Earth visibility."""
    try:
        return site_profile(site_id, target=target)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/analyze", tags=["lunar"])
@router.post("/lunar/analyze", tags=["lunar"], include_in_schema=False)
def lunar_analyze(payload: dict = Body()) -> dict:
    """Evaluate an exact 72-hour start on the supported 15-minute grid."""
    try:
        return analyze_request(payload)
    except ValueError as error:
        message = str(error)
        status = 409 if message.startswith("DATA_NOT_READY") else 400
        raise HTTPException(status_code=status, detail=message) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/results/{result_id}/export", tags=["lunar"])
@router.get("/lunar/results/{result_id}/export", tags=["lunar"], include_in_schema=False)
def lunar_result_export(
    result_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
) -> Response:
    """Export a persisted analysis with its reproducibility metadata."""
    try:
        result = load_result(result_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if format == "csv":
        return Response(
            content=result_csv(result),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="lunarsight-{result_id}.csv"'},
        )
    return Response(
        content=json.dumps(result, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="lunarsight-{result_id}.json"'},
    )


@router.get("/lunar/sites/{site_id}/timeline", tags=["lunar"])
def lunar_site_timeline(
    site_id: str,
    max_points: int = Query(default=360, ge=24, le=1440),
) -> dict:
    """Serve a bounded display sample without changing the scientific intervals."""
    try:
        return site_timeline(site_id, max_points=max_points)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/lunar/sites/{site_id}/analysis", tags=["lunar"])
def lunar_site_analysis(site_id: str, at_utc: str = Query()) -> dict:
    """Return the native visibility interval and nearest precomputed 72-hour window."""
    try:
        return site_analysis(site_id, at_utc=at_utc)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/lunar/point/terrain", tags=["lunar"])
def lunar_point_terrain(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=360),
) -> dict:
    """Sample the best validated DEM available at an arbitrary lunar coordinate."""
    try:
        return sample_terrain(latitude=latitude, longitude=longitude)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/lunar/point/terrain-window", tags=["lunar"])
def lunar_point_terrain_window(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=360),
    radius_km: float = Query(default=8.0, ge=0.5, le=32),
    samples: int = Query(default=129),
) -> dict:
    """Return a bounded, downsampled terrain grid for interactive rendering."""
    try:
        return terrain_window(latitude, longitude, radius_km, samples)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
