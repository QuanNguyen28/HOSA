"""Translate assistant contracts to the existing, unchanged planning engine."""
import hashlib
import json
import math
from datetime import timedelta

from app.services.lunarsight import planning

from .models import Candidate, EvidenceBundle, ParseRequest, RequestPatch, RequestSpec, utc
from .provider import AssistantError


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class PlanningAdapter:
    def capabilities(self) -> dict:
        payload = planning.scenarios()
        scenario = payload["scenarios"][0]
        root = planning.repository_root()
        paths = [root / "manifests/lunarsight/config/scenario.json",
                 root / "manifests/lunarsight/config/geometry_config.json"]
        for site in ("Site01", "Site04"):
            for suffix in ("windows", "intervals"):
                paths.append(planning.processed_root() / "visibility" / f"{site}_{suffix}.csv")
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  if p.is_file() else "MISSING" for p in paths}
        return {"scenario": scenario, "dataset_version": payload["dataset_version"],
                "method_version": payload["method_version"],
                "source_hash": digest({"files": hashes, "dataset": payload["dataset_version"],
                                       "method": payload["method_version"]}), "source_files": hashes,
                "supported_constraints": ["max_darkness_hours", "max_earth_blackout_hours", "min_sunlit_fraction"],
                "warnings": payload["warnings"]}

    @staticmethod
    def index(at: str, scenario: dict) -> int:
        instant = utc(at)
        if not utc(scenario["A_utc"]) <= instant < utc(scenario["B_utc"]):
            raise AssistantError("OUTSIDE_TIME_COVERAGE")
        offset = (instant - utc(scenario["A_utc"])).total_seconds()
        step = scenario["start_step_minutes"] * 60
        if offset % step != 0:
            raise AssistantError("OFF_START_GRID")
        return int(offset // step)

    def baseline_issue(self, request: ParseRequest, caps: dict) -> str | None:
        b, scenario = request.baseline, caps["scenario"]
        if b is None:
            return "MISSING_BASELINE"
        if b.scenario_id != scenario["scenario_id"]:
            return "UNSUPPORTED_SCENARIO"
        if b.duration_hours != scenario["D_hours"] or b.hardware.model_dump() != scenario["device_heights_m"]:
            return "UNSUPPORTED_BASELINE_CONFIG"
        if b.current_site_id not in scenario["site_ids"]:
            return "UNSUPPORTED_BASELINE_SITE"
        try:
            self.index(b.arrival_utc, scenario)
        except (ValueError, AssistantError):
            return "INVALID_BASELINE_TIME"
        return None

    def normalize(self, request: ParseRequest, patch: RequestPatch, caps: dict) -> RequestSpec:
        b, scenario = request.baseline, caps["scenario"]
        assert b is not None
        if patch.hardware_change or patch.unsupported_requirements:
            raise AssistantError("UNSUPPORTED_REQUIREMENT")
        if patch.unresolved_fields:
            raise AssistantError("UNRESOLVED_FIELDS")
        if any(not q.strip() or q not in request.text for q in patch.source_quotes):
            raise AssistantError("UNSUPPORTED_SOURCE_QUOTE")
        if patch.arrival_shift_days is not None and patch.arrival_utc is not None:
            raise AssistantError("AMBIGUOUS_ARRIVAL")
        if patch.duration_hours is not None and patch.duration_hours != scenario["D_hours"]:
            raise AssistantError("UNSUPPORTED_DURATION")
        at = utc(b.arrival_utc)
        if patch.arrival_shift_days is not None:
            try:
                at += timedelta(days=patch.arrival_shift_days)
            except OverflowError as error:
                raise AssistantError("OUTSIDE_TIME_COVERAGE") from error
        if patch.arrival_utc is not None:
            try:
                at = utc(patch.arrival_utc)
            except ValueError as error:
                raise AssistantError("UNRESOLVED_ARRIVAL") from error
        arrival = at.isoformat().replace("+00:00", "Z")
        index = self.index(arrival, scenario)
        selected = [b.current_site_id]
        if patch.site_scope == "selected":
            if not request.selected_site_ids:
                raise AssistantError("MISSING_REGION")
            selected = request.selected_site_ids
        if len(set(selected)) != len(selected) or any(s not in scenario["site_ids"] for s in selected):
            raise AssistantError("UNSUPPORTED_SITE_SCOPE")
        constraints = b.constraints.model_copy(update={k: getattr(patch, k) for k in
            ("max_darkness_hours", "max_earth_blackout_hours") if getattr(patch, k) is not None})
        return RequestSpec(
            scenario_id=b.scenario_id, arrival_utc=arrival,
            end_utc=(at + timedelta(hours=scenario["D_hours"])).isoformat().replace("+00:00", "Z"),
            start_index=index, site_ids=selected, hardware=b.hardware,
            constraints=constraints, min_sunlit_fraction=patch.min_sunlit_fraction,
            current_site_id=b.current_site_id, baseline_hash=digest(b.model_dump()), source_hash=caps["source_hash"],
        )

    def evaluate(self, spec: RequestSpec, run_id: str, spec_hash: str) -> EvidenceBundle:
        candidates, facts = [], {}
        for site_id in spec.site_ids:
            try:
                # Separate site calls preserve partial availability. No external APIs
                # or DEM processing are invoked by this precomputed-data engine.
                payload = planning.analyze_request({"scenario_id": spec.scenario_id, "site_ids": [site_id],
                    "start_index": spec.start_index, "constraints": spec.constraints.model_dump()})
                if payload["dataset_version"] != planning.DATASET_VERSION or payload["method_version"] != planning.METHOD_VERSION or len(payload["sites"]) != 1:
                    raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                row = payload["sites"][0]
                if row["site_id"] != site_id or utc(row["start_utc"]) != utc(spec.arrival_utc) or utc(row["end_utc"]) != utc(spec.end_utc):
                    raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                for pair in row["metrics"].values():
                    if len(pair) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < -1e-7 or v > 72+1e-7 for v in pair) or pair[0] > pair[1]:
                        raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                for event in row["events"]:
                    start, stop = utc(event["start_utc"]), utc(event["end_utc"])
                    if not utc(spec.arrival_utc) <= start < stop <= utc(spec.end_utc) or abs((stop-start).total_seconds()/3600-event["duration_hours"]) > 1e-6:
                        raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                    metric = "longest_dark_hours" if event["body"] == "sun" else "longest_blackout_hours"
                    if event["state"] == "B" and event["duration_hours"] > row["metrics"][metric][1]+1e-6:
                        raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                states = dict(row["constraint_states"])
                for key, metric in (("max_darkness_hours", "longest_dark_hours"),
                                    ("max_earth_blackout_hours", "longest_blackout_hours")):
                    low, high = row["metrics"][metric]
                    limit = getattr(spec.constraints, key)
                    expected = "PASS" if high <= limit+1e-9 else "FAIL" if low > limit+1e-9 else "INDETERMINATE"
                    if states.get(key) != expected:
                        raise AssistantError("ENGINE_CONTRACT_ERROR", 502)
                if spec.min_sunlit_fraction is not None:
                    low, high = row["metrics"]["total_sun_hours"]
                    threshold = spec.min_sunlit_fraction * 72
                    states["min_sunlit_fraction"] = "PASS" if low >= threshold-1e-9 else "FAIL" if high < threshold-1e-9 else "INDETERMINATE"
                decision = "FAIL" if "FAIL" in states.values() else "PASS" if all(s == "PASS" for s in states.values()) else "INDETERMINATE"
                candidates.append(Candidate(site_id=site_id, decision=decision, metrics=row["metrics"],
                    constraint_states=states, decisive_event=row["decisive_event"], provenance=row["provenance"]))
                for suffix, metric in (("dark", "longest_dark_hours"), ("earth", "longest_blackout_hours"), ("sun", "total_sun_hours")):
                    body = "sun" if suffix == "dark" else "earth" if suffix == "earth" else None
                    events = [event for event in row["events"] if event["body"] == body and event["state"] == "B"]
                    worst = max(events, key=lambda event: event["duration_hours"]) if events else None
                    if worst:
                        worst = {**worst, "event_id": digest({"site": site_id, "source": spec.source_hash, "event": worst})[:20]}
                    limit = spec.constraints.max_darkness_hours if suffix == "dark" else spec.constraints.max_earth_blackout_hours if suffix == "earth" else (spec.min_sunlit_fraction*72 if spec.min_sunlit_fraction is not None else None)
                    facts[f"{site_id}.{suffix}"] = {"site_id": site_id, "metric": metric,
                        "bounds": row["metrics"][metric], "unit": "hours", "limit_hours": limit,
                        "worst_interval": worst, "source": row["provenance"]}
            except (KeyError, TypeError, IndexError) as error:
                raise AssistantError("ENGINE_CONTRACT_ERROR", 502) from error
            except (FileNotFoundError, ValueError) as error:
                if isinstance(error, ValueError) and not str(error).startswith("DATA_NOT_READY"):
                    raise AssistantError("ENGINE_CONTRACT_ERROR", 502) from error
                candidates.append(Candidate(site_id=site_id, decision="INDETERMINATE", metrics={},
                    constraint_states={}, decisive_event=None, provenance={}, issue="DATA_NOT_READY"))
                facts[f"{site_id}.availability"] = {"site_id": site_id, "status": "DATA_NOT_READY"}
        passing = [c for c in candidates if c.decision == "PASS"]
        failing = [c for c in candidates if c.decision == "FAIL"]

        def score(c):
            dark = c.metrics["longest_dark_hours"][1]
            earth = c.metrics["longest_blackout_hours"][1]
            violations = [max(0, dark-spec.constraints.max_darkness_hours)/max(spec.constraints.max_darkness_hours, 1e-9),
                          max(0, earth-spec.constraints.max_earth_blackout_hours)/max(spec.constraints.max_earth_blackout_hours, 1e-9)]
            if spec.min_sunlit_fraction is not None:
                violations.append(max(0, spec.min_sunlit_fraction-c.metrics["total_sun_hours"][0]/72)/max(spec.min_sunlit_fraction, 1e-9))
            return max(violations), c.site_id != spec.current_site_id, c.site_id
        known = passing or failing
        recommended = min(known, key=score).site_id if known else None
        status = "FEASIBLE" if passing else "NO_FEASIBLE_IN_EVALUATED_SET" if failing else "INSUFFICIENT_DATA"
        return EvidenceBundle(run_id=run_id, spec_hash=spec_hash, source_hash=spec.source_hash, request=spec,
            status=status, recommended_site_id=recommended, apply_allowed=bool(passing), candidates=candidates,
            coverage={"candidate_total": len(candidates), "pass": len(passing), "fail": len(failing),
                      "indeterminate": sum(c.decision == "INDETERMINATE" for c in candidates)}, facts=facts,
            warnings=["PROVISIONAL; only the selected, evaluated sites and constraints are covered.",
                      "Earth LOS is geometric; sunlight is not a power/thermal model.",
                      "No feasible candidate does not establish that the whole region is infeasible.",
                      "Ranking policy: minimum worst relative violation, then current site, then site ID."])
