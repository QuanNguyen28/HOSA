"""Read-only snapshot evidence, evaluated by the same core as live coordinates.

Profiles and full native timelines are loaded once per operation. Missing finer
ephemerides or radius profiles remain missing; no evidence is borrowed by date.
"""
import json
from pathlib import Path

import pandas as pd

from app.core.errors import DomainError
from app.point_analysis.geometry import verify_profiles
from app.services.lunarsight import planning as legacy
from app.services.lunarsight.acquire import hashfile
from app.services.lunarsight.catalog import site_catalog
from app.services.lunarsight.visibility import visibility
from .evaluation import angle_difference, evaluate, validate, metrics, constraint_checks, decision


def clip(frame, request):
    if frame is None:
        return None
    start, end = pd.Timestamp(request.start_utc), pd.Timestamp(request.end_utc)
    selected = frame[(frame.start_utc < end) & (frame.end_utc > start)].copy()
    if selected.empty or selected.start_utc.iloc[0] > start or selected.end_utc.iloc[-1] < end:
        return None
    selected["start_utc"] = selected.start_utc.clip(lower=start)
    selected["end_utc"] = selected.end_utc.clip(upper=end)
    return selected


class SnapshotProvider:
    def __init__(self):
        self.root = legacy.processed_root()
        self.prepared = {}
        self.integrity = None

    def prepare(self, site_id):
        if site_id in self.prepared:
            return self.prepared[site_id]
        prefix = legacy.SUPPORTED_SITES[site_id]
        site = next(f["properties"] for f in site_catalog()["features"] if f["properties"]["site_id"] == site_id)
        path = self.root / "visibility" / f"{prefix}_intervals.csv"
        base = pd.read_csv(path)
        for key in ("start_utc", "end_utc"):
            base[key] = pd.to_datetime(base[key], utc=True)
        profiles = {}
        for label, step, radius in (("base", .25, 400000), ("azimuth_0.25_vs_0.125", .125, 400000),
                                     ("radius_400km_vs_300km", .25, 300000)):
            try:
                profiles[label] = {float(h): pd.read_csv(self.root / "horizon" / f"{prefix}_h{h}_az{step:g}_r{radius}.csv") for h in (1, 2)}
            except FileNotFoundError:
                profiles[label] = None
        ephemerides = {}
        for step in (5, 1):
            bodies = []
            for body in ("sun", "earth"):
                tables = []
                for ep in sorted((self.root / "ephemeris").glob(f"{site_id}_{body}_{step}min_*.csv")):
                    table = pd.read_csv(ep)
                    table.index = pd.to_datetime(table.pop("utc"), utc=True)
                    tables.append(table)
                # Never splice distinct observer queries into new synthetic evidence.
                bodies.append(tables)
            ephemerides[step] = bodies
        report = legacy.repository_root() / "docs/validation/lunarsight/v0.2.0/reports" / f"{prefix}_seam_summary.csv"
        seams = []
        if report.is_file():
            near_strategy = set(profiles["base"][1.].get("near_switch_strategy", pd.Series(["fixed"]))) if profiles["base"] else {"fixed"}
            for row in pd.read_csv(report).to_dict("records"):
                if row["fine"] == "5m" and row["method"] != ("footprint" if "footprint" in near_strategy else "fixed"):
                    continue
                seams.append({**row, "passed": bool(row["accepted_for_model"]
                    and row["paired"] >= .9*row["sampled"] and abs(row["median_signed_m"]) <= 10
                    and row["p95_abs_angle_deg"] <= .15)})
        else:
            seams = [{"passed": False, "reason": "SEAM_EVIDENCE_MISSING"}]
        references = {}
        for label, group in profiles.items():
            if group:
                try:
                    references.update({label + ":" + key: value for key, value in verify_profiles(group, site).items()})
                except (ValueError, AssertionError):
                    references[label] = {"passed": False}
        angles = {name: angle_difference(profiles["base"], group)
                  for name, group in profiles.items() if name != "base" and group and profiles["base"]}
        if self.integrity is None:
            receipt = self.root / "derivation.json"
            outputs = json.loads(receipt.read_text()).get("outputs", {}) if receipt.is_file() else {}
            self.integrity = bool(outputs) and all((legacy.repository_root()/name).is_file()
                and hashfile(legacy.repository_root()/name) == sha for name, sha in outputs.items())
        result = dict(base=base, profiles=profiles, ephemerides=ephemerides, seams=seams,
            references=references, angles=angles, site=site, path=str(path.relative_to(legacy.repository_root())))
        self.prepared[site_id] = result
        return result

    def analyze(self, target, request):
        if request.illumination_model != "sun_center":
            raise DomainError("ILLUMINATION_MODEL_MISMATCH", 409)
        evidence = self.prepare(target.site_id)
        frame = clip(evidence["base"], request)
        if frame is None:
            raise DomainError("INCOMPLETE_TIMELINE", 409)
        alternatives = {}
        for name in ("azimuth_0.25_vs_0.125", "radius_400km_vs_300km", "time_5min_vs_1min"):
            step = 1 if name.startswith("time") else 5
            group = evidence["profiles"]["base" if step == 1 else name]
            bodies = []
            for tables in evidence["ephemerides"][step]:
                chosen = None
                for table in tables:
                    part = table.loc[request.start_utc:request.end_utc]
                    expected = pd.date_range(request.start_utc, request.end_utc, freq=f"{step}min")
                    if part.index.equals(expected) and part.row_present.all() and part[["az_deg", "el_deg"]].notna().all().all():
                        chosen = part
                        break
                bodies.append(chosen)
            alternatives[name] = visibility(*bodies, group[1.], group[2.]) if group and all(b is not None for b in bodies) else None
        terrain = all(group is not None and all(p.coverage_complete.all() for p in group.values())
                      for group in evidence["profiles"].values())
        ephemeris = bool(frame[["sun_ephem_valid", "earth_ephem_valid"]].all().all())
        checks = [{"code": "SNAPSHOT_INTEGRITY_FAILED", "passed": bool(self.integrity)}]
        if target.site_id == "Site04_P1":
            reference = self.prepare("Site01_P1")
            checks.append({"code": "SITE01_GEOMETRY_GATE_FAILED", "passed": bool(reference["references"])
                and all(r["passed"] for r in reference["references"].values())
                and all(s["passed"] for s in reference["seams"])})
        validation = validate(request, frame, alternatives, evidence["angles"], terrain_complete=terrain,
            ephemeris_complete=ephemeris, seams=evidence["seams"], references=evidence["references"], evidence_checks=checks)
        result = evaluate(request, frame, validation)
        result.update(timeline_frame=frame, provenance={"provider": "snapshot", "intervals": evidence["path"],
            "dataset_version": legacy.DATASET_VERSION}, coordinate={"latitude_deg": evidence["site"]["lat_deg"],
                "longitude_e_deg": evidence["site"]["lon_e_deg"], "dem_elevation_m": evidence["site"]["dem_z_m"]})
        result["sensitivity"] = sensitivity_summary(request, result)
        return result

    def preflight_failure(self, target, request, latest_end_utc=None):
        """Skip gated candidates only if no later start can fail a hard check.

        A validation warning no longer hides a hard rejection. A fully visible
        suffix can still be pruned when fractions are the only hard requirements.
        """
        try:
            evidence = self.prepare(target.site_id)
        except FileNotFoundError:
            return "DATA_NOT_READY"
        suffix = evidence["base"].loc[evidence["base"].start_utc >= pd.Timestamp(request.start_utc)]
        if latest_end_utc is not None:
            suffix = suffix.loc[suffix.end_utc <= pd.Timestamp(latest_end_utc)]
        if request.contact_requirements is not None or any(
                (getattr(request, requirement) or 0) > 0 and not suffix[column].eq("V").all()
                for requirement, column in (("min_sunlit_fraction", "sun_state"),
                                            ("min_earth_los_fraction", "earth_state"))):
            return None
        if not self.integrity:
            return "SNAPSHOT_INTEGRITY_FAILED"
        if not all(p is not None for p in evidence["profiles"].values()):
            return "COMPARISON_EVIDENCE_MISSING"
        if any(not s["passed"] for s in evidence["seams"]):
            return "DEM_SEAM_FAILED"
        if not evidence["references"] or any(not r["passed"] for r in evidence["references"].values()):
            return "ENU_REFERENCE_FAILED"
        if any(a["max_abs_deg"] is None or a["max_abs_deg"] > .1
               for angles in evidence["angles"].values() for a in angles.values()):
            return "SENSITIVITY_FAILED"
        return None


def sensitivity_summary(request, result):
    """Keep the existing planning diagnostic fields, derived from shared checks."""
    comparisons = {}
    metric, checks = result["metrics_hours"], result["constraint_checks"]
    for name, diagnostic in result["validation"].get("sensitivity", {}).items():
        if "metrics_hours" not in diagnostic:
            comparisons[name] = {"status": "NOT_EVALUATED", "reason": "COMPARISON_WINDOW_NOT_COVERED"}
            continue
        same = checks == diagnostic["constraint_checks"]
        comparisons[name] = {"status": "STABLE_DECISION" if same else "REVIEW",
            "baseline": {"metrics": metric, "constraint_states": checks,
                "decision": result["nominal_sampled_decision"], "soft_constraint_states": result["soft_constraint_checks"]},
            "alternative": {"metrics": diagnostic["metrics_hours"], "constraint_states": diagnostic["constraint_checks"],
                "decision": decision(diagnostic["constraint_checks"].values()), "soft_constraint_states": diagnostic["soft_constraint_checks"]},
            "bounds_abs_delta_minutes": diagnostic["duration_delta_minutes"],
            "soft_preferences_changed": diagnostic["soft_constraint_checks"] != result["soft_constraint_checks"]}
    statuses = [v["status"] for v in comparisons.values()]
    temporal = result["validation"].get("sensitivity", {}).get("time_5min_vs_1min", {})
    time_items = list(temporal.get("temporal", {}).values())
    max_shift = max((v["max_matched_event_shift_minutes"] or 0 for v in time_items), default=None)
    max_angle = max((v["max_abs_deg"] for d in result["validation"].get("sensitivity", {}).values()
                     for v in d.get("angles_by_height", {}).values() if v["max_abs_deg"] is not None), default=None)
    return {"status": "REVIEW" if "REVIEW" in statuses else "NOT_EVALUATED" if not statuses or "NOT_EVALUATED" in statuses else "STABLE_DECISION",
        "scope": {"site_id": request.site_id, "start_utc": request.start_utc, "end_utc": request.end_utc,
            "contact_requirements": request.contact_requirements.model_dump() if request.contact_requirements else None,
            "constraints": request.constraints.model_dump(), "min_sunlit_fraction": request.min_sunlit_fraction,
            "min_earth_los_fraction": request.min_earth_los_fraction,
            "device_heights_m": {"sun_panel": request.panel_height_m, "earth_antenna": request.antenna_height_m}},
        "comparisons": comparisons, "angular_sensitive": max_angle > .1 if max_angle is not None else None,
        "max_horizon_difference_deg": max_angle, "time_sensitive": not temporal["passed"] if time_items else None,
        "max_event_shift_minutes": max_shift,
        "max_duration_difference_minutes": max((v for p in temporal.get("duration_delta_minutes", {}).values() for v in p), default=None),
        "unmatched_events": sum(v["unmatched_first"]+v["unmatched_second"] for v in time_items) if time_items else None,
        "soft_preferences_changed": any(v.get("soft_preferences_changed") for v in comparisons.values())}
