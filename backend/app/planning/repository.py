"""Versioned input and result I/O; never imports an LLM client."""
import csv
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from app.core.errors import DomainError
from app.mission.identity import digest
from app.mission.evaluation import EVALUATION_VERSION, VALIDATION_VERSION
from app.mission.resolution import VERSION as RESOLUTION_VERSION, FINE_AZIMUTH_STEPS
from app.services.lunarsight.visibility import SENSITIVITY_VERSION
from app.services.lunarsight import planning as legacy
from .metrics import METRICS
from .models import PlanningResult, utc

METHOD_VERSION = "planning-services-3.1.0"


class SnapshotRepository:
    def capabilities(self) -> dict:
        payload = legacy.scenarios()
        scenario = payload["scenarios"][0]
        root = legacy.repository_root()
        paths = [root/"manifests/lunarsight/config/scenario.json", root/"manifests/lunarsight/config/geometry_config.json",
                 root/"manifests/lunarsight/source_manifest.json", legacy.processed_root()/"derivation.json",
                 legacy.processed_root()/"site_catalog.geojson"]
        for prefix in legacy.SUPPORTED_SITES.values():
            paths.extend(legacy.processed_root()/"visibility"/f"{prefix}_{kind}.csv" for kind in ("windows", "intervals"))
        paths.extend(sorted((legacy.processed_root()/"horizon").glob("*.csv")))
        paths.extend(sorted((root/"docs/validation/lunarsight/v0.2.0/reports").glob("*_seam_summary.csv")))
        paths.extend(sorted((legacy.processed_root()/"ephemeris").glob("*.csv")))
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING" for p in paths}
        return {"scenario": scenario, "dataset_version": payload["dataset_version"], "method_version": METHOD_VERSION,
                "source_hash": digest({"files": hashes, "dataset": payload["dataset_version"], "method": METHOD_VERSION,
                    "evaluation": EVALUATION_VERSION, "validation": VALIDATION_VERSION, "sensitivity": SENSITIVITY_VERSION}),
                "source_files": hashes, "supported_constraints": ["min_sunlit_fraction", "min_earth_los_fraction"],
                "supported_soft_constraints": ["max_darkness_hours", "max_earth_blackout_hours"],
                "supported_operations": ["compare", "window_search"], "ranking_metrics": list(METRICS),
                "supported_contact_requirements": ["min_contact_minutes", "setup_minutes", "required_windows", "first_contact_deadline_minutes"],
                "data_sources": ["snapshot", "coordinate"],
                "indeterminate_resolution": {"request_field": "resolve_indeterminate", "default": False,
                    "policy_version": RESOLUTION_VERSION, "max_refinement_rounds": len(FINE_AZIMUTH_STEPS),
                    "fine_azimuth_steps_deg": list(FINE_AZIMUTH_STEPS), "max_search_evaluations": 128},
                "coordinate_analysis": {"target": "site_id or exact coordinates", "duration_hours": {"minimum": 1, "maximum": None},
                    "alternative_end_field": "end_utc", "duration_step_minutes": 5,
                    "start_step_minutes": 5, "max_search_evaluations": 128},
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
    fields = ["candidate_id", "site_id", "start_utc", "end_utc", "decision", "dataset_version", "method_version", "source_hash",
              "min_sunlit_fraction", "min_earth_los_fraction", "soft_constraint_states_json", "soft_violations_json",
              "sensitivity_status", "sensitivity_scope_json", "sensitivity_comparisons_json", "resolution_json", "validation_json"]
    fields += [metric+suffix for metric in METRICS for suffix in ("_L", "_U")]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for candidate in result.candidates:
        row = {k: getattr(candidate, k) for k in ("candidate_id", "site_id", "start_utc", "end_utc", "decision")}
        row.update(dataset_version=result.dataset_version, method_version=result.method_version, source_hash=result.source_hash)
        row.update(min_sunlit_fraction=result.request["min_sunlit_fraction"], min_earth_los_fraction=result.request["min_earth_los_fraction"],
                   soft_constraint_states_json=json.dumps(candidate.soft_constraint_states, separators=(",", ":")),
                   soft_violations_json=json.dumps(candidate.soft_violations, separators=(",", ":")))
        row.update(sensitivity_status=candidate.sensitivity.get("status", "NOT_EVALUATED"),
                   sensitivity_scope_json=json.dumps(candidate.sensitivity.get("scope", {}), separators=(",", ":")),
                   sensitivity_comparisons_json=json.dumps(candidate.sensitivity.get("comparisons", {}), separators=(",", ":")))
        row["resolution_json"] = json.dumps(candidate.resolution, separators=(",", ":"))
        row["validation_json"] = json.dumps(candidate.validation, separators=(",", ":"))
        for metric, pair in candidate.metrics.items():
            row[metric+"_L"], row[metric+"_U"] = pair
        writer.writerow(row)
    return stream.getvalue()
