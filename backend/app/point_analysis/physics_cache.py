"""Persistent physical series, independent of requirements and exact subwindows."""
from pathlib import Path
import json
import os
import tempfile
import numpy as np
import pandas as pd
from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest
from .transport import write_frame, read_array, frame_from_array
from . import metric_index
from app.services.lunarsight.acquire import hashfile

VERSION = "physical-series-1"


class PhysicalSeriesCache:
    def __init__(self, root):
        self.root = Path(root)/"physical-series"

    def load(self, identity, start, end):
        directory = self.root/digest(identity)
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        for receipt in sorted(directory.glob("*/receipt.json")):
            try:
                record = json.loads(receipt.read_text())
                if record["identity"] != identity:
                    raise ValueError("Physical series identity mismatch")
                if not pd.Timestamp(record["start_utc"]) <= start < end <= pd.Timestamp(record["end_utc"]):
                    continue
                reference = record["timeline_artifact"]
                array = read_array(receipt.parent, reference)
                a, b = [t.tz_convert("UTC").tz_localize(None).to_datetime64().astype("datetime64[us]") for t in (start, end)]
                first = int(np.searchsorted(array["start_utc"], a))
                stop = int(np.searchsorted(array["start_utc"], b))
                if first >= stop or array["start_utc"][first] != a or array["end_utc"][stop-1] != b:
                    continue  # No interpolation or extrapolation across a source grid.
                frame = frame_from_array(array[first:stop], reference)
                # Pandas deep-copies attrs on column access. Immutable JSON keeps
                # provenance without repeatedly cloning decades of receipts.
                frame.attrs.update(physical_series_cache_hit=True, physical_receipts=json.dumps(record.get("ephemerides", [])))
                return frame
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise DomainError("PHYSICAL_SERIES_INTEGRITY_FAILED", 503) from error
        return None

    def summary(self, identity, start, end):
        for receipt in sorted((self.root/digest(identity)).glob("*/receipt.json")):
            record = json.loads(receipt.read_text())
            if record["identity"] != identity:
                raise DomainError("PHYSICAL_SERIES_INTEGRITY_FAILED", 503)
            if not pd.Timestamp(record["start_utc"]) <= pd.Timestamp(start) < pd.Timestamp(end) <= pd.Timestamp(record["end_utc"]):
                continue
            reference = record.get("metrics_index")
            if reference and reference.get("source_sha256") == record["timeline_artifact"]["sha256"]:
                result = metric_index.query(receipt.parent, reference, start, end)
                if result is not None:
                    result["physical_series_cache_hit"] = True
                    return result
        from .prepared_metrics import PreparedMetrics
        return PreparedMetrics(self.root.parent).query(identity, start, end)

    def save(self, identity, frame, ephemerides, *, index=False):
        from .pipeline import atomic_json
        coverage = {"start_utc": frame.start_utc.iloc[0].isoformat(), "end_utc": frame.end_utc.iloc[-1].isoformat()}
        directory = self.root/digest(identity)/digest(coverage)
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(str(directory/"series.lock")):
            if not (directory/"receipt.json").is_file():
                reference = write_frame(directory/"timeline.npy", frame)
                atomic_json(directory/"receipt.json", {"identity": identity, **coverage,
                    "timeline_artifact": reference, "ephemerides": ephemerides})
            if index:
                self._index(directory, frame)

    def prepare_index(self, receipt):
        directory = Path(receipt).parent
        with FileLock(str(directory/"series.lock")):
            self._index(directory)

    @staticmethod
    def _index(directory, frame=None):
        from .pipeline import atomic_json
        record = json.loads((directory/"receipt.json").read_text())
        reference = record.get("metrics_index", {})
        if reference.get("version") == metric_index.VERSION and reference.get("source_sha256") == record["timeline_artifact"]["sha256"]:
            return
        if frame is None:
            frame = frame_from_array(read_array(directory, record["timeline_artifact"]), record["timeline_artifact"])
        content, full_metrics = metric_index.build(frame)
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".npz.tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            os.replace(temporary, directory/"metrics.npz")
        finally:
            Path(temporary).unlink(missing_ok=True)
        record["metrics_index"] = {"version": metric_index.VERSION, "sha256": hashfile(directory/"metrics.npz"),
            "source_sha256": record["timeline_artifact"]["sha256"], "full_metrics": full_metrics}
        atomic_json(directory/"receipt.json", record)


def identity(sun_source, earth_source, profiles, panel, antenna, illumination):
    from app.services.lunarsight.solar_disc import VERSION as DISC_VERSION
    from app.services.lunarsight.visibility import SENSITIVITY_VERSION
    return {"version": VERSION, "sun": sun_source, "earth": earth_source, "illumination_model": illumination,
        "visibility_version": SENSITIVITY_VERSION, "solar_disc_version": DISC_VERSION if illumination == "solar_disc" else None,
        "profiles": {str(h): digest(pd.util.hash_pandas_object(profiles[h], index=True).values.tolist())
                     for h in sorted({panel, antenna})}}
