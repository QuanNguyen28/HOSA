"""Bounded background horizon preparation, independent of mission evaluation."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from threading import RLock
import logging

from app.core.errors import DomainError
from app.mission.identity import digest
from .geometry import METHOD_VERSION
from .horizon_view import profile_view


class HorizonPreloads:
    def __init__(self, max_pending=4):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lunar-horizon")
        self.lock = RLock()
        self.pending, self.stages = {}, {}
        self.max_pending = max_pending

    def ensure(self, request, pipeline):
        request = request.resolved()
        key = digest({"geometry_method": METHOD_VERSION, "latitude_deg": request.latitude_deg,
            "longitude_e_deg": request.longitude_e_deg % 360,
            "heights_m": sorted({request.panel_height_m, request.antenna_height_m})})
        with self.lock:
            future = self.pending.get(key)
            if future is not None and not future.done():
                return self.progress(key)
        try:
            return {"status": "ready", "profile": profile_view(request, pipeline)}
        except DomainError as error:
            if error.code != "HORIZON_NOT_PREPARED":
                raise
        with self.lock:
            future = self.pending.get(key)
            if future is not None:
                if not future.done():
                    return self.progress(key)
                try:
                    future.result()
                except DomainError:
                    raise
                except Exception as error:
                    raise DomainError("HORIZON_PREPARATION_FAILED", 503) from error
            if sum(not item.done() for item in self.pending.values()) >= self.max_pending:
                raise DomainError("HORIZON_PREPARATION_BUSY", 429)
            # Completed futures carry no profile data. Bound metadata as users
            # inspect arbitrary coordinates; durable geometry stays on disk.
            if len(self.pending) >= 64:
                for old in list(self.pending):
                    if self.pending[old].done():
                        self.pending.pop(old)
                        self.stages.pop(old, None)
            self.stages[key] = "queued"
            self.pending[key] = self.executor.submit(self.work, key, request, pipeline)
            return self.progress(key)

    def progress(self, key):
        return {"status": "preparing", "preparation_id": key,
                "stage": self.stages.get(key, "queued"), "retry_after_ms": 750}

    def work(self, key, request, pipeline):
        def progress(stage):
            with self.lock:
                self.stages[key] = stage
        try:
            progress("verify_dem")
            with pipeline.terrain(request) as terrain:
                pipeline.geometry(terrain, {request.panel_height_m, request.antenna_height_m}, progress)
            progress("complete")
        except Exception:
            logging.getLogger(__name__).exception("Horizon preparation failed: %s", key)
            raise

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=False)


@lru_cache
def get_horizon_preloads():
    return HorizonPreloads()
