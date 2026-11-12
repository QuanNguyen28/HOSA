"""Validated coordinate → DEM → Horizons → terrain visibility → duration bounds."""
from pathlib import Path
import json
import os
import tempfile
import time

import numpy as np
import pandas as pd
import requests

from app.core.errors import DomainError
from app.mission.identity import digest
from app.mission.evaluation import (EVALUATION_VERSION, VALIDATION_VERSION, metrics, constraint_checks, decision, records, events, angle_difference, validate, evaluate)
from app.services.lunarsight.acquire import hashfile, utc_now
from app.services.lunarsight.horizons import fetch, ADAPTER_VERSION
from app.services.lunarsight.terrain import R
from app.services.lunarsight.visibility import visibility, SENSITIVITY_VERSION
from app.services.lunarsight.contact_windows import analyze_contacts, METHOD_VERSION as CONTACT_METHOD_VERSION
from .geometry import METHOD_VERSION, scan_horizons, seam_checks, verify_profiles
from .sources import TerrainInputs

METRICS_VERSION = "coordinate-metrics-0.2.0"


class PointAnalysisPipeline:
    def __init__(self, root: Path):
        self.root = Path(root)

    def run(self, request, progress=lambda stage: None):
        request = request.resolved()
        progress("verify_dem")
        with TerrainInputs(request) as terrain:
            identity = {"method_version": METHOD_VERSION, "metrics_version": METRICS_VERSION,
                        "sensitivity_version": SENSITIVITY_VERSION,
                        "evaluation_version": EVALUATION_VERSION, "validation_version": VALIDATION_VERSION,
                        "contact_method_version": CONTACT_METHOD_VERSION if request.contact_requirements else None,
                        "horizons_adapter_version": ADAPTER_VERSION,
                        "request": request.model_dump(exclude={"offline"}),
                        "datasets": terrain.provenance(), "radius_m": R,
                        "az_step_deg": .25, "fine_az_step_deg": .125,
                        "scan_radii_m": [400000, 300000], "time_steps_minutes": [5, 1]}
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
            references = verify_profiles(fine, terrain.site)
            base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25) for h, p in fine.items()}
            verify_profiles(shorter, terrain.site)
            for height, profile in fine.items():
                profile.to_csv(directory / f"horizon_h{height:g}_az0.125.csv", index=False)
            progress("horizons_5min")
            sun, earth, records5 = self.ephemerides(request, terrain.site, 5)
            progress("horizons_1min")
            sun1, earth1, records1 = self.ephemerides(request, terrain.site, 1)
            v = visibility(sun, earth, base[request.panel_height_m], base[request.antenna_height_m])
            vfine = visibility(sun, earth, fine[request.panel_height_m], fine[request.antenna_height_m])
            vshort = visibility(sun, earth, shorter[request.panel_height_m], shorter[request.antenna_height_m])
            vtime = visibility(sun1, earth1, base[request.panel_height_m], base[request.antenna_height_m])
            progress("metrics_and_validation")
            alternatives = {"azimuth_0.25_vs_0.125": vfine, "radius_400km_vs_300km": vshort,
                            "time_5min_vs_1min": vtime}
            angles = {"azimuth_0.25_vs_0.125": angle_difference(base, fine),
                      "radius_400km_vs_300km": angle_difference(base, shorter)}
            complete_ephemerides = all(item["missing_timestamps"] == 0 and item["missing_angles"] == 0
                                       for item in records5 + records1)
            complete_terrain = all(bool(p.coverage_complete.all()) for p in [*fine.values(), *shorter.values()])
            validation = validate(request, v, alternatives, angles, terrain_complete=complete_terrain,
                ephemeris_complete=complete_ephemerides, seams=seams, references=references)
            evaluation = evaluate(request, v, validation)
            metric = evaluation["metrics_hours"]
            validated = validation["passed"]
            warnings = ["PROVISIONAL: numerical tolerances require mission-owner approval.",
                "Sun/Earth centre visibility only; no solar-disc, power, thermal or RF link-budget model.",
                "Duration bounds cover missing samples in this sampled model, not continuous-time or DEM uncertainty.",
                "Horizon coverage describes sampled rays to 400 km; no global occluder or landing certification."]
            if not validated:
                warnings.append("Validation gate did not pass; metrics are exploratory. Requested hard decisions are gated to INDETERMINATE.")
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
                "validation": validation,
                "timeline": records(v), "events": events(v),
                "horizons": {str(h): records(p) for h, p in base.items()},
                "provenance": {"identity": identity, "ephemerides": records5 + records1, "geometry": geometry_receipt,
                               "frame": "MOON_ME/DE421", "radial_reference_radius_m": R},
                "warnings": warnings}
            if request.contact_requirements is not None:
                result["contact_analysis"] = analyze_contacts(result, **request.contact_requirements.model_dump())
            progress("commit_artifacts")
            v.to_csv(directory / "intervals.csv", index=False)
            result["provenance"]["artifacts"] = {path.name: hashfile(path) for path in directory.glob("*.csv")}
            atomic_json(directory / "result.json", result)
            atomic_json(directory / "receipt.json", {"identity": identity, "sha256": hashfile(directory / "result.json")})
            progress("complete")
            return result

    def geometry(self, terrain, heights, progress):
        identity = {"method_version": METHOD_VERSION, "site": terrain.site,
                    "datasets": terrain.provenance(), "heights": sorted(heights),
                    "scan_radii_m": [400000, 300000], "az_steps_deg": [.125, .25]}
        directory = self.root / "geometry" / digest(identity)
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
        fine = scan_horizons(terrain, heights)
        verify_profiles(fine, terrain.site)
        progress("radius_sensitivity")
        short = scan_horizons(terrain, heights, radius=300000, az_step=.25)
        verify_profiles(short, terrain.site)
        progress("verify_horizon_artifacts")
        files = {}
        for label, profiles in (("fine", fine), ("short", short)):
            for h, profile in profiles.items():
                name = f"{label}_h{h:g}.csv"
                profile.to_csv(directory / name, index=False)
                files[name] = hashfile(directory / name)
        receipt = {"identity": identity, "files": files, "seams": seams}
        atomic_json(receipt_path, receipt)
        return fine, short, seams, receipt

    def ephemerides(self, request, site, step):
        data, receipts = [], []
        for target, height in ((10, request.panel_height_m), (399, request.antenna_height_m)):
            try:
                df, receipt = fetch(self.root, site, target, height, request.start_utc,
                                    request.end_utc, step, R, R, offline=request.offline)
            except FileNotFoundError as error:
                raise DomainError("HORIZONS_CACHE_MISS", 503) from error
            except requests.RequestException as error:
                raise DomainError("HORIZONS_UNAVAILABLE", 502) from error
            except ValueError as error:
                raise DomainError("HORIZONS_VALIDATION_FAILED", 502) from error
            data.append(df)
            receipts.append(receipt)
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
        for attempt in range(6):
            try:
                os.replace(name,path)
                break
            except PermissionError:
                if attempt==5:
                    raise
                # Windows scanners/readers can hold an atomic-replace target briefly.
                time.sleep(.01*(attempt+1))
    finally:
        Path(name).unlink(missing_ok=True)
