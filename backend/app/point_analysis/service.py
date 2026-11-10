"""Bounded background jobs with on-disk status and verifiable result cache."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

from filelock import FileLock, Timeout

from app.core.errors import DomainError
from app.services.lunarsight.point import repository_root
from .models import JobStatus
from .pipeline import PointAnalysisPipeline, atomic_json


@lru_cache
def get_point_pipeline():
    return PointAnalysisPipeline(repository_root() / "data/cache/point-analysis")


def calculate(request, pipeline, progress=lambda stage: None, timeout=0):
    """Direct and queued requests share the same process-safe scientific cache lock."""
    pipeline.root.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(pipeline.root / "pipeline.lock"), timeout=timeout):
            return pipeline.run(request, progress)
    except Timeout as error:
        raise DomainError("POINT_ANALYSIS_BUSY", 429) from error


class PointAnalysisJobs:
    def __init__(self, root=None, pipeline=None, max_pending=4):
        self.root = Path(root) if root else repository_root() / "data/cache/point-analysis"
        self.root.mkdir(parents=True, exist_ok=True)
        self.pipeline = pipeline or PointAnalysisPipeline(self.root)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lunar-point")
        self.max_pending = max_pending
        self.lock = Lock()
        self.active = set()
        self.owner_token = uuid4().hex
        (self.root / "owners").mkdir(exist_ok=True)
        self.owner_lock = FileLock(str(self.root / "owners" / f"{self.owner_token}.lock"), thread_local=False)
        self.owner_lock.acquire(timeout=0)

    def submit(self, request):
        with self.lock:
            if len(self.active) >= self.max_pending:
                raise DomainError("POINT_ANALYSIS_BUSY", 429)
            identifier = uuid4().hex
            self.active.add(identifier)
            status = JobStatus(job_id=identifier, status="queued", stage="queued")
            self.write(status)
            try:
                self.executor.submit(self.work, identifier, request)
            except RuntimeError:
                self.active.discard(identifier)
                raise DomainError("POINT_ANALYSIS_UNAVAILABLE", 503)
            return status

    def work(self, identifier, request):
        def progress(stage):
            self.write(JobStatus(job_id=identifier, status="running", stage=stage))
        try:
            progress("waiting_for_worker")
            # Serialize across uvicorn processes as well as within this worker.
            # Foundation Horizons cache uses fixed .part names for identical requests.
            result = calculate(request, self.pipeline, progress, timeout=-1)
            self.write(JobStatus(job_id=identifier, status="succeeded", stage="complete",
                result_url=f"/api/lunar/point/analyses/{identifier}/result"), result_id=result["result_id"],
                execution=result.get("execution"), request=result.get("request"))
        except DomainError as error:
            self.write(JobStatus(job_id=identifier, status="failed", stage="failed", error_code=error.code))
        except Exception:
            logging.getLogger(__name__).exception("Coordinate pipeline failed: job=%s", identifier)
            self.write(JobStatus(job_id=identifier, status="failed", stage="failed", error_code="POINT_ANALYSIS_FAILED"))
        finally:
            with self.lock:
                self.active.discard(identifier)

    def write(self, status, **extra):
        atomic_json(self.root / "jobs" / f"{status.job_id}.json", {**status.model_dump(),
                    "owner_pid": os.getpid(), "owner_token": self.owner_token, **extra})

    def read(self, identifier):
        # Also defend callers outside the HTTP route from traversal.
        if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
            raise DomainError("POINT_JOB_NOT_FOUND", 404)
        path = self.root / "jobs" / f"{identifier}.json"
        if not path.is_file():
            raise DomainError("POINT_JOB_NOT_FOUND", 404)
        return json.loads(path.read_text(encoding="utf-8"))

    def status(self, identifier):
        record = self.read(identifier)
        if record["status"] in {"queued", "running"}:
            token = record.get("owner_token", "")
            if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
                record.update(status="failed", stage="interrupted", error_code="POINT_JOB_INTERRUPTED")
            else:
                try:
                    with FileLock(str(self.root / "owners" / f"{token}.lock"), timeout=0):
                        record.update(status="failed", stage="interrupted", error_code="POINT_JOB_INTERRUPTED")
                except Timeout:
                    pass  # A live process still owns the queued/running job.
        return JobStatus.model_validate({k: v for k, v in record.items() if k in JobStatus.model_fields})

    def result(self, identifier):
        status = self.status(identifier)
        if status.status != "succeeded":
            raise DomainError(status.error_code or "POINT_RESULT_NOT_READY", 409)
        record = self.read(identifier)
        directory = self.root / "results" / record["result_id"]
        try:
            receipt = json.loads((directory / "receipt.json").read_text())
            result = self.pipeline.cached_result(directory, receipt["identity"])
        except (OSError, ValueError, KeyError) as error:
            raise DomainError("POINT_RESULT_MISSING", 503) from error
        if result is None:
            raise DomainError("POINT_RESULT_MISSING", 503)
        return {**result, "execution": record.get("execution") or result.get("execution"),
                "request": record.get("request") or result.get("request")}

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=False)
        self.owner_lock.release()


@lru_cache
def get_point_jobs():
    return PointAnalysisJobs()
