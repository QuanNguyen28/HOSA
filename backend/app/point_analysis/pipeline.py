"""Validated coordinate → DEM → Horizons → terrain visibility → duration bounds."""
from pathlib import Path
import json
import os
import tempfile
from filelock import FileLock

import numpy as np
import pandas as pd
import requests

from app.core.errors import DomainError
from app.mission.identity import digest
from app.mission.resolution import VERSION as RESOLUTION_VERSION, FINE_AZIMUTH_STEPS, can_refine, attempt
from app.mission.mission_path import validate_mission_path
from app.services.lunarsight.decision_policy import decision_validated
from app.mission.evaluation import (EVALUATION_VERSION, VALIDATION_VERSION, metrics, constraint_checks, decision, records, events, angle_difference, validate, evaluate, frame_contacts)
from app.services.lunarsight.acquire import hashfile, utc_now
from app.services.lunarsight.horizons import fetch, ADAPTER_VERSION
from app.services.lunarsight.terrain import R
from app.services.lunarsight.visibility import visibility, SENSITIVITY_VERSION
from app.services.lunarsight.contact_windows import analyze_contacts, METHOD_VERSION as CONTACT_METHOD_VERSION
from .geometry import METHOD_VERSION, scan_horizons, seam_checks, verify_profiles
from .sources import TerrainInputs
from .ephemeris_plan import segments

METRICS_VERSION = "coordinate-metrics-0.2.0"


class PointAnalysisPipeline:
    def __init__(self, root: Path):
        self.root = Path(root)

    def identity(self, request, terrain):
        identity = {"method_version": METHOD_VERSION, "metrics_version": METRICS_VERSION,
                        "sensitivity_version": SENSITIVITY_VERSION,
                        "evaluation_version": EVALUATION_VERSION, "validation_version": VALIDATION_VERSION,
                        "contact_method_version": CONTACT_METHOD_VERSION if request.contact_requirements else None,
                        "horizons_adapter_version": ADAPTER_VERSION,
                        "request": request.model_dump(exclude={"offline", "resolve_indeterminate"}),
                        "datasets": terrain.provenance(), "radius_m": R,
                        "az_step_deg": .25, "fine_az_step_deg": .125,
                        "scan_radii_m": [400000, 300000], "time_steps_minutes": [5, 1]}
        if request.resolve_indeterminate:
            identity["resolution_policy"] = {"version": RESOLUTION_VERSION, "fine_az_steps_deg": list(FINE_AZIMUTH_STEPS)}
        return identity

    def lookup_cached(self, request):
        """Read committed, hash-verified results without waiting for compute workers."""
        request = request.resolved()
        with TerrainInputs(request) as terrain:
            identity = self.identity(request, terrain)
            cached = self.cached_result(self.root / "results" / digest(identity), identity)
        if cached is not None:
            return {**cached, "request": request.model_dump(),
                    "execution": {"result_cache_hit": True, "offline": request.offline}}

    def run(self, request, progress=lambda stage: None):
        request = request.resolved()
        progress("verify_dem")
        with TerrainInputs(request) as terrain:
            identity = self.identity(request, terrain)
            result_id = digest(identity)
            directory = self.root / "results" / result_id
            cached = self.cached_result(directory, identity)
            if cached is not None:
                progress("cached")
                return {**cached, "request": request.model_dump(),
                        "execution": {"result_cache_hit": True, "offline": request.offline}}
            directory.mkdir(parents=True, exist_ok=True)
            heights = set((request.panel_height_m, request.antenna_height_m))
            fine, shorter, seams, geometry_receipt = self.geometry(terrain, heights, progress)
            progress("horizons_5min")
            sun, earth, records5 = self.ephemerides(request, terrain.site, 5, progress=progress)
            progress("horizons_1min")
            sun1, earth1, records1 = self.ephemerides(request, terrain.site, 1, progress=progress)
            progress("metrics_and_validation")
            ephemerides = (sun, earth, sun1, earth1, records5, records1)
            v, base, validation, evaluation, complete_terrain, complete_ephemerides = self.evaluate_geometry(
                request, terrain, fine, shorter, seams, ephemerides, .125)
            resolution = {"enabled": request.resolve_indeterminate, "policy_version": RESOLUTION_VERSION,
                "status": "disabled" if not request.resolve_indeterminate else (
                    "hard_requirement_failed" if evaluation["decision"] == "FAIL" and not validation["passed"] else "not_needed"),
                "initial_decision": evaluation["decision"], "initial_reason_codes": list(validation["reason_codes"]),
                "max_refinement_rounds": len(FINE_AZIMUTH_STEPS), "refinement_rounds": 0,
                "attempts": [attempt(evaluation, .25, .125)]}
            if request.resolve_indeterminate and evaluation["decision"] == "INDETERMINATE":
                resolution["status"] = "unresolved"
                # Existing native grids and spatial comparisons may already
                # prove every hard requirement. Refinement is only needed
                # when those conservative bounds remain inconclusive.
                progress("checking_mission_bounds")
                validation["mission_path"] = validate_mission_path(
                    request, validation, base, fine, shorter, ephemerides)
                evaluation = evaluate(request, v, validation)
                if evaluation["decision"] != "INDETERMINATE":
                    resolution["status"] = "resolved"
                    resolution["attempts"].append(attempt(evaluation, .25, .125))
                for fine_step in FINE_AZIMUTH_STEPS:
                    if evaluation["decision"] != "INDETERMINATE" or not can_refine(validation):
                        break
                    progress(f"refining_horizon_{fine_step:g}deg")
                    fine, shorter, seams, geometry_receipt = self.geometry(terrain, heights,
                        lambda stage: progress(f"revalidating_{stage}_{fine_step:g}deg"), az_step=fine_step)
                    v, base, validation, evaluation, complete_terrain, complete_ephemerides = self.evaluate_geometry(
                        request, terrain, fine, shorter, seams, ephemerides, fine_step)
                    if evaluation["decision"] == "INDETERMINATE":
                        validation["mission_path"] = validate_mission_path(
                            request, validation, base, fine, shorter, ephemerides)
                        evaluation = evaluate(request, v, validation)
                    resolution["refinement_rounds"] += 1
                    resolution["attempts"].append(attempt(evaluation, fine_step*2, fine_step))
                    if evaluation["decision"] != "INDETERMINATE":
                        resolution["status"] = "resolved"
                        break
                # Radius/time sensitivity may be decision-irrelevant even if
                # angular refinement cannot address that global diagnostic.
                if evaluation["decision"] == "INDETERMINATE":
                    validation["mission_path"] = validate_mission_path(
                        request, validation, base, fine, shorter, ephemerides)
                    evaluation = evaluate(request, v, validation)
                    if evaluation["decision"] != "INDETERMINATE":
                        resolution["status"] = "resolved"
            resolution["final_decision"] = evaluation["decision"]
            resolution["remaining_reason_codes"] = list(validation["reason_codes"])
            selected_step = float(next(iter(fine.values())).az_step_deg.iloc[0])
            for height, profile in fine.items():
                profile.to_csv(directory / f"horizon_h{height:g}_az{selected_step:g}.csv", index=False)
            metric = evaluation["metrics_hours"]
            validated = decision_validated(validation)
            warnings = ["PROVISIONAL: numerical tolerances require mission-owner approval.",
                "Sun/Earth centre visibility only; no solar-disc, power, thermal or RF link-budget model.",
                "Duration bounds cover missing samples in this sampled model, not continuous-time or DEM uncertainty.",
                "Horizon coverage describes sampled rays to 400 km; no global occluder or landing certification."]
            if not validated:
                warnings.append("Decision validation did not pass; metrics are exploratory. Hard failures remain FAIL; PASS is withheld.")
            elif not validation["passed"]:
                warnings.append("Only the requested hard requirements passed conservative sampled mission-path bounds; full-horizon numerical validation still failed. Nominal metrics are retained; robust bounds are in validation.mission_path.metrics_hours.")
            result = {"result_id": result_id, "method_version": METHOD_VERSION, "created_utc": utc_now(),
                "execution": {"result_cache_hit": False, "offline": request.offline},
                "request": request.model_dump(), "end_utc": request.end_utc,
                "coordinate": {"latitude_deg": request.latitude_deg, "longitude_e_deg": request.longitude_e_deg,
                               "dem_elevation_m": terrain.site["dem_z_m"],
                               "observer_dataset_id": terrain.observer_source["dataset_id"],
                               "observer_resolution_m": terrain.observer_source["resolution_m"],
                               "elevation_sampling": "nearest registered DEM pixel; observer coordinate is not snapped"},
                "decision": evaluation["decision"], "nominal_sampled_decision": evaluation["nominal_sampled_decision"],
                "requirement_policy": "availability-and-contact-windows-v1" if request.contact_requirements else "availability-fractions-v1",
                "constraint_checks": evaluation["constraint_checks"], "metrics_hours": metric,
                "soft_constraint_checks": evaluation["soft_constraint_checks"],
                "soft_violations": evaluation["soft_violations"],
                "availability_fraction": {"sun": [x/request.duration_hours for x in metric["total_sun_hours"]],
                                          "earth": [x/request.duration_hours for x in metric["total_earth_los_hours"]]},
                "coverage": {"terrain_complete": complete_terrain, "ephemeris_complete": complete_ephemerides,
                    "covered_azimuth_fraction_by_height": {str(h): float(p.coverage_complete.mean()) for h, p in fine.items()},
                    "state_counts": {key: {str(k): int(n) for k, n in v[key].value_counts().items()}
                                     for key in ("sun_state", "earth_state", "joint_state")}},
                "validation": validation, "resolution": resolution,
                "timeline": records(v), "events": events(v),
                "horizons": {str(h): records(p) for h, p in base.items()},
                "provenance": {"identity": identity, "ephemerides": records5 + records1, "geometry": geometry_receipt,
                               "frame": "MOON_ME/DE421", "radial_reference_radius_m": R},
                "warnings": warnings}
            if request.contact_requirements is not None:
                result["contact_analysis"] = frame_contacts(request, v, result)
            v.to_csv(directory / "intervals.csv", index=False)
            result["provenance"]["artifacts"] = {path.name: hashfile(path) for path in directory.glob("*.csv")}
            atomic_json(directory / "result.json", result)
            atomic_json(directory / "receipt.json", {"identity": identity, "sha256": hashfile(directory / "result.json")})
            progress("complete")
            return result

    def evaluate_geometry(self, request, terrain, fine, shorter, seams, ephemerides, fine_step):
        sun, earth, sun1, earth1, records5, records1 = ephemerides
        references = verify_profiles(fine, terrain.site)
        references.update({"short:"+key: value for key, value in verify_profiles(shorter, terrain.site).items()})
        base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=fine_step*2) for h, p in fine.items()}
        v = visibility(sun, earth, base[request.panel_height_m], base[request.antenna_height_m])
        name = f"azimuth_{fine_step*2:g}_vs_{fine_step:g}"
        alternatives = {name: visibility(sun, earth, fine[request.panel_height_m], fine[request.antenna_height_m]),
            "radius_400km_vs_300km": visibility(sun, earth, shorter[request.panel_height_m], shorter[request.antenna_height_m]),
            "time_5min_vs_1min": visibility(sun1, earth1, base[request.panel_height_m], base[request.antenna_height_m])}
        angles = {name: angle_difference(base, fine), "radius_400km_vs_300km": angle_difference(base, shorter)}
        complete_ephemerides = all(item.get("used_coverage", item)["missing_timestamps"] == 0
            and item.get("used_coverage", item)["missing_angles"] == 0 for item in records5+records1)
        complete_ephemerides = complete_ephemerides and all(
            bool(g.row_present.eq(True).all() and np.isfinite(g[["az_deg", "el_deg"]]).all().all())
            for g in (sun, earth, sun1, earth1))
        complete_terrain = all(bool(p.coverage_complete.all()) for p in [*fine.values(), *shorter.values()])
        validation = validate(request, v, alternatives, angles, terrain_complete=complete_terrain,
            ephemeris_complete=complete_ephemerides, seams=seams, references=references, azimuth_comparison_name=name)
        validation["configuration"] = {"coarse_az_step_deg": fine_step*2, "fine_az_step_deg": fine_step,
            "scan_radii_m": [400000, 300000], "time_steps_minutes": [5, 1]}
        return v, base, validation, evaluate(request, v, validation), complete_terrain, complete_ephemerides

    def geometry(self, terrain, heights, progress, az_step=.125):
        identity = {"method_version": METHOD_VERSION, "site": terrain.site,
                    "datasets": terrain.provenance(), "heights": sorted(heights),
                    "scan_radii_m": [400000, 300000], "az_steps_deg": [az_step, az_step*2]}
        directory = self.root / "geometry" / digest(identity)
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(str(directory / "geometry.lock")):
            return self._geometry(terrain, heights, progress, az_step, identity, directory)

    def _geometry(self, terrain, heights, progress, az_step, identity, directory):
        receipt_path = directory / "receipt.json"
        if receipt_path.is_file():
            try:
                receipt = json.loads(receipt_path.read_text())
            except (OSError, ValueError) as error:
                raise DomainError("HORIZON_CACHE_INTEGRITY_FAILED", 503) from error
            expected = {f"{label}_h{h:g}.csv" for label in ("fine", "short") for h in heights}
            if (receipt.get("identity") != identity or set(receipt.get("files", {})) != expected or any(
                    not (directory/name).is_file() or hashfile(directory/name) != checksum
                    for name, checksum in receipt.get("files", {}).items())):
                raise DomainError("HORIZON_CACHE_INTEGRITY_FAILED", 503)
            progress("cached_horizon")
            try:
                return ({h: pd.read_csv(directory / f"fine_h{h:g}.csv") for h in heights},
                        {h: pd.read_csv(directory / f"short_h{h:g}.csv") for h in heights},
                        receipt["seams"], receipt)
            except (OSError, ValueError, KeyError) as error:
                raise DomainError("HORIZON_CACHE_INTEGRITY_FAILED", 503) from error
        directory.mkdir(parents=True, exist_ok=True)
        progress("seam_validation")
        seams = seam_checks(terrain)
        progress("terrain_horizon")
        fine = scan_horizons(terrain, heights, az_step=az_step)
        verify_profiles(fine, terrain.site)
        progress("radius_sensitivity")
        short = scan_horizons(terrain, heights, radius=300000, az_step=az_step*2)
        verify_profiles(short, terrain.site)
        files = {}
        for label, profiles in (("fine", fine), ("short", short)):
            for h, profile in profiles.items():
                name = f"{label}_h{h:g}.csv"
                profile.to_csv(directory / name, index=False)
                files[name] = hashfile(directory / name)
        receipt = {"identity": identity, "files": files, "seams": seams}
        atomic_json(receipt_path, receipt)
        return fine, short, seams, receipt

    def ephemerides(self, request, site, step, progress=lambda stage: None):
        data, receipts = [], []
        for target, height in ((10, request.panel_height_m), (399, request.antenna_height_m)):
            parts = []
            try:
                plan = segments(self.root, site, target, height, request.start_utc, request.end_utc, step)
                total = len(plan)
                for chunk, (start, stop, fetch_start, fetch_stop) in enumerate(plan, 1):
                    progress(f"horizons_{step}min_{'sun' if target == 10 else 'earth'}_batch_{chunk}_of_{total}")
                    df, receipt = fetch(self.root, site, target, height, fetch_start.isoformat(),
                                        fetch_stop.isoformat(), step, R, R, offline=request.offline)
                    df = df.loc[start:stop]
                    receipt = {**receipt, "used_start_utc": start.isoformat(), "used_end_utc": stop.isoformat(),
                        "used_coverage": {"missing_timestamps": int((~df.row_present.eq(True)).sum()),
                                          "missing_angles": int(df[["az_deg", "el_deg"]].isna().any(axis=1).sum())}}
                    if parts:
                        previous = parts[-1].iloc[-1]
                        boundary = df.iloc[0]
                        if (parts[-1].index[-1] != df.index[0] or
                                bool(previous.row_present) != bool(boundary.row_present) or
                                not np.allclose(previous[["az_deg", "el_deg"]].to_numpy(dtype=float),
                                                boundary[["az_deg", "el_deg"]].to_numpy(dtype=float),
                                                atol=1e-7, rtol=0, equal_nan=True)):
                            raise DomainError("HORIZONS_CHUNK_BOUNDARY_MISMATCH", 502)
                    parts.append(df)
                    receipts.append(receipt)
            except FileNotFoundError as error:
                raise DomainError("HORIZONS_CACHE_MISS", 503) from error
            except requests.RequestException as error:
                raise DomainError("HORIZONS_UNAVAILABLE", 502) from error
            except ValueError as error:
                raise DomainError("HORIZONS_VALIDATION_FAILED", 502) from error
            # Keep the terminal sample once; no interpolation between queries.
            combined = pd.concat([p.iloc[:-1] for p in parts[:-1]] + parts[-1:])
            expected = pd.date_range(request.start_utc, request.end_utc, freq=f"{step}min")
            if not combined.index.equals(expected):
                raise DomainError("HORIZONS_GRID_MISMATCH", 502)
            data.append(combined)
        if not data[0].index.equals(data[1].index):
            raise DomainError("HORIZONS_GRID_MISMATCH", 502)
        return *data, receipts

    @staticmethod
    def cached_result(directory, identity):
        path, receipt = directory / "result.json", directory / "receipt.json"
        if not path.exists() or not receipt.exists():
            return None
        try:
            record = json.loads(receipt.read_text())
        except (OSError, ValueError) as error:
            raise DomainError("RESULT_CACHE_INTEGRITY_FAILED", 503) from error
        if record.get("identity") != identity or record.get("sha256") != hashfile(path):
            raise DomainError("RESULT_CACHE_INTEGRITY_FAILED", 503)
        return json.loads(path.read_text())


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
