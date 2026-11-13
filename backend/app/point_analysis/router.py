from fastapi import APIRouter, Depends, HTTPException, Response, Query, Request
from typing import Literal
from fastapi.responses import StreamingResponse

from app.core.errors import DomainError
from .models import JobStatus, PointAnalysisRequest, PointAnalysisResult
from .service import PointAnalysisJobs, get_point_jobs, get_point_pipeline, calculate
from .pipeline import PointAnalysisPipeline

router = APIRouter(prefix="/lunar/point", tags=["coordinate analysis"])


@router.post("/horizon-profile/preload", summary="Prepare missing terrain horizons in background without Analyze")
def preload_horizon_profile(request: PointAnalysisRequest, response: Response,
                            pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    from .horizon_preload import get_horizon_preloads
    try:
        state = get_horizon_preloads().ensure(request, pipeline)
        if state["status"] == "preparing":
            response.status_code = 202
            response.headers["Retry-After"] = "1"
        return state
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.post("/horizon-profile", summary="Cached 360-degree terrain horizon at the requested hardware heights")
def horizon_profile(request: PointAnalysisRequest, pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    from .horizon_view import profile_view
    try:
        return profile_view(request, pipeline)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.post("/sky-track", summary="Bounded sampled Sun/Earth positions across the whole mission")
def mission_sky_track(request: PointAnalysisRequest, http_request: Request, chunk_index: int = Query(default=0, ge=0),
                      pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    from .horizon_view import sky_track
    try:
        import gzip
        from app.precompute.store import json_bytes
        from app.precompute.display import http_response
        import hashlib
        payload = gzip.compress(json_bytes(sky_track(request, pipeline, chunk_index)), mtime=0)
        return http_response(http_request, (payload, hashlib.sha256(payload).hexdigest(), False))
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.get("/sky-vectors", summary="Checked hourly Moon-frame vectors for smooth 3D playback")
def sky_vectors(at_utc: str = Query(), pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    try:
        return pipeline.shared_ephemeris.preview_table(at_utc)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    except (ValueError, OverflowError) as error:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INTERVAL_TIME"}) from error


@router.post("/metrics", response_model=PointAnalysisResult,
             summary="Prepared nominal metrics only; no timeline scan or validation job")
def prepared_metrics(request: PointAnalysisRequest,
                     pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    try:
        return pipeline.indexed_metrics(request)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.post("/instant", summary="Nominal five-minute instant using prepared terrain; no mission evaluation")
def prepared_instant(request: PointAnalysisRequest, at_utc: str = Query(),
                     pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    try:
        return pipeline.prepared_instant(request, at_utc)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    except (ValueError, OverflowError) as error:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INTERVAL_TIME"}) from error


@router.post("/analyze", response_model=PointAnalysisResult,
             summary="Calculate coordinate metrics and return the complete result directly")
def analyze(request: PointAnalysisRequest,
            view: Literal["full", "display"] = "full",
            pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    try:
        return calculate(request, pipeline, display=view == "display")
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.post("/analyses", status_code=202, response_model=JobStatus)
def submit(request: PointAnalysisRequest, response: Response,
           jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        status = jobs.submit(request)
        response.headers["Location"] = f"/api/lunar/point/analyses/{status.job_id}"
        return status
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.get("/analyses/{job_id}", response_model=JobStatus)
def status(job_id: str, jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return jobs.status(job_id)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.get("/analyses/{job_id}/result", response_model=PointAnalysisResult)
def result(job_id: str, view: Literal["full", "display"] = "full",
           jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return jobs.result(job_id, display=view == "display")
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.get("/analyses/{job_id}/preview", response_model=PointAnalysisResult,
            summary="Initial sampled metrics while requirements/validation are pending")
def preview(job_id: str, jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return jobs.preview(job_id)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error


@router.get("/analyses/{job_id}/interval", summary="Exact native interval at a UTC instant; half-open mission window")
def interval(job_id: str, at_utc: str = Query(), jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return jobs.interval(job_id, at_utc)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    except (ValueError, OverflowError) as error:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INTERVAL_TIME"}) from error


@router.get("/analyses/{job_id}/intervals.csv", summary="Stream native intervals as CSV on demand")
def interval_csv(job_id: str, jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return StreamingResponse(jobs.interval_csv(job_id), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="intervals-{job_id}.csv"'})
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
