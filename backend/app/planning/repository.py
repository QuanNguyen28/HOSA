"""Versioned input and result I/O; never imports an LLM client."""
import csv
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from app.core.errors import DomainError
from app.services.lunarsight import planning as legacy
from .metrics import METRICS
from .models import PlanningResult, utc

METHOD_VERSION = "planning-services-1.0"


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class SnapshotRepository:
    def capabilities(self) -> dict:
        payload = legacy.scenarios()
        scenario = payload["scenarios"][0]
        root = legacy.repository_root()
        paths = [root/"manifests/lunarsight/config/scenario.json", root/"manifests/lunarsight/config/geometry_config.json",
                 root/"manifests/lunarsight/source_manifest.json"]
        for prefix in legacy.SUPPORTED_SITES.values():
            paths.extend(legacy.processed_root()/"visibility"/f"{prefix}_{kind}.csv" for kind in ("windows", "intervals"))
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING" for p in paths}
        return {"scenario": scenario, "dataset_version": payload["dataset_version"], "method_version": METHOD_VERSION,
                "source_hash": digest({"files": hashes, "dataset": payload["dataset_version"], "method": METHOD_VERSION}),
                "source_files": hashes, "supported_constraints": ["max_darkness_hours", "max_earth_blackout_hours", "min_sunlit_fraction"],
                "supported_operations": ["compare", "window_search"], "ranking_metrics": list(METRICS),
                "warnings": payload["warnings"]}

    def windows(self, site_id: str) -> dict[int, dict]:
        path = legacy.processed_root()/"visibility"/f"{legacy.SUPPORTED_SITES[site_id]}_windows.csv"
        rows = {}
        with path.open(encoding="utf-8", newline="") as stream:
            for raw in csv.DictReader(stream):
                index = int(raw["start_index"])
                if index in rows or raw["site_id"] != site_id:
                    raise DomainError("ENGINE_CONTRACT_ERROR", 502)
                metrics = {}
                for metric in METRICS:
                    pair = [raw[metric+"_L"], raw[metric+"_U"]]
                    metrics[metric] = [float(v) for v in pair] if all(v not in ("", None) for v in pair) else None
                rows[index] = {"start_index": index, "start_utc": raw["start_utc"], "end_utc": raw["end_utc"],
                               "metrics": metrics, "source": str(path.relative_to(legacy.repository_root()))}
        return rows


    def covered_ranges(self, site_id: str):
        path = legacy.processed_root()/"visibility"/f"{legacy.SUPPORTED_SITES[site_id]}_intervals.csv"
        ranges = []
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                start, stop = utc(row["start_utc"]), utc(row["end_utc"])
                if stop <= start or (ranges and start < ranges[-1][1]):
                    raise DomainError("ENGINE_CONTRACT_ERROR", 502)
                if ranges and start == ranges[-1][1]:
                    ranges[-1] = (ranges[-1][0], stop)
                else:
                    ranges.append((start, stop))
        return ranges


class ResultRepository:
    def directory(self) -> Path:
        return legacy.repository_root()/"data/cache/planning/results"

    def save(self, result: PlanningResult) -> None:
        directory = self.directory()
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory/f".{result.result_id}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(directory/f"{result.result_id}.json")
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, result_id: str) -> PlanningResult:
        if len(result_id) != 20 or any(c not in "0123456789abcdef" for c in result_id):
            raise DomainError("INVALID_RESULT_ID")
        path = self.directory()/f"{result_id}.json"
        if not path.is_file():
            raise DomainError("RESULT_NOT_FOUND", 404)
        return PlanningResult.model_validate_json(path.read_text(encoding="utf-8"))


def result_csv(result: PlanningResult) -> str:
    stream = io.StringIO()
    fields = ["candidate_id", "site_id", "start_utc", "end_utc", "decision", "dataset_version", "method_version", "source_hash"]
    fields += [metric+suffix for metric in METRICS for suffix in ("_L", "_U")]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for candidate in result.candidates:
        row = {k: getattr(candidate, k) for k in ("candidate_id", "site_id", "start_utc", "end_utc", "decision")}
        row.update(dataset_version=result.dataset_version, method_version=result.method_version, source_hash=result.source_hash)
        for metric, pair in candidate.metrics.items():
            row[metric+"_L"], row[metric+"_U"] = pair
        writer.writerow(row)
    return stream.getvalue()
