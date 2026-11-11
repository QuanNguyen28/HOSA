from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.errors import DomainError
from .models import JobStatus, PointAnalysisRequest, PointAnalysisResult
from .service import PointAnalysisJobs, get_point_jobs, get_point_pipeline, calculate
from .pipeline import PointAnalysisPipeline

router = APIRouter(prefix="/lunar/point", tags=["coordinate analysis"])


@router.post("/analyze", response_model=PointAnalysisResult,
             summary="Calculate coordinate metrics and return the complete result directly")
def analyze(request: PointAnalysisRequest,
            pipeline: PointAnalysisPipeline = Depends(get_point_pipeline)):
    try:
        return calculate(request, pipeline)
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
def result(job_id: str, jobs: PointAnalysisJobs = Depends(get_point_jobs)):
    try:
        return jobs.result(job_id)
    except DomainError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
