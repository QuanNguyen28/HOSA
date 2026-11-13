#!/usr/bin/env python3
"""Build portable, hash-checked display meshes and scientific horizon products.

Raw NASA inputs must be installed/verified. No model calls. Safe to resume:
each observer is published atomically only after geometry verification.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.mission.targets import compare_sites, coordinates_for_site, default_sites
from app.services.lunarsight.point import _terrain_window_uncached as terrain_window, _south_polar_cap_uncached as south_polar_cap, METHOD_VERSION as DISPLAY_VERSION
from app.point_analysis.sources import TerrainInputs, installed_sources
from app.point_analysis.geometry import scan_horizons, seam_checks, verify_profiles, METHOD_VERSION
from app.precompute.geometry import HEIGHTS, FINE_STEP, SHORT_STEP, encode_profile, compatible_sources
from app.precompute.store import Store, coordinate_key, mesh_key, json_bytes

MESHES = [(1.5, 401, "best"), (6., 257, "best"), (6., 401, "best")]
MESHES += [(radius, samples, "regional") for radius in (24., 48., 120., 300.) for samples in (257, 401)]


def targets(include_legacy=False):
    keys = ("Site01_P1", "Site04_P1", *compare_sites()) if include_legacy else default_sites()
    sites = {key: coordinates_for_site(key) for key in keys}
    groups = {}
    for key, coordinate in sites.items():
        identity = coordinate_key(coordinate["latitude_deg"], coordinate["longitude_e_deg"])
        groups.setdefault(identity, {"site_ids": [], **coordinate})["site_ids"].append(key)
    return list(groups.values())


def build_one(target, output_root):
    started = perf_counter()
    store = Store(output_root)
    key = coordinate_key(target["latitude_deg"], target["longitude_e_deg"])
    previous = store.manifest()["sites"].get(key)
    if (previous and previous.get("geometry_method") == METHOD_VERSION and compatible_sources(previous)
            and previous.get("display_method") == DISPLAY_VERSION
            and previous.get("heights_m") == list(HEIGHTS)
            and all(mesh_key(target["latitude_deg"], target["longitude_e_deg"], *config) in store.manifest()["meshes"] for config in MESHES)):
        for reference in previous["profiles"].values():
            store.read(reference)
        for config in MESHES:
            store.read(store.manifest()["meshes"][mesh_key(target["latitude_deg"], target["longitude_e_deg"], *config)])
        return {"site_ids": target["site_ids"], "status": "already_prepared", "seconds": perf_counter()-started}
    print(json.dumps({"site_ids": target["site_ids"], "stage": "display_meshes"}), flush=True)
    meshes = {}
    for radius, samples, detail in MESHES:
        value = terrain_window(target["latitude_deg"], target["longitude_e_deg"], radius, samples, detail)
        reference = store.put(gzip.compress(json_bytes(value), mtime=0), "json.gz")
        meshes[mesh_key(target["latitude_deg"], target["longitude_e_deg"], radius, samples, detail)] = {
            **reference, "display_method": DISPLAY_VERSION,
            "coordinate_key": key, "radius_km": radius, "samples": samples, "detail": detail}
    request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
                             start_utc="2026-11-17T00:00:00Z")
    with TerrainInputs(request) as terrain:
        seams = seam_checks(terrain)
        print(json.dumps({"site_ids": target["site_ids"], "stage": "horizon_400km", "seconds": perf_counter()-started}), flush=True)
        fine = scan_horizons(terrain, HEIGHTS, radius=400000, az_step=FINE_STEP)
        print(json.dumps({"site_ids": target["site_ids"], "stage": "horizon_300km", "seconds": perf_counter()-started}), flush=True)
        short = scan_horizons(terrain, HEIGHTS, radius=300000, az_step=SHORT_STEP)
        references = {"fine": verify_profiles(fine, terrain.site), "short": verify_profiles(short, terrain.site)}
        profiles = {}
        for label, group in (("fine", fine), ("short", short)):
            for height, profile in group.items():
                profiles[f"{label}_h{height:g}"] = store.put(encode_profile(profile), "npz")
        inventory = [{"dataset_id": source["dataset_id"], "sha256": source["sha256"]} for source in installed_sources()]
        record = {"site_ids": target["site_ids"], "site": terrain.site, "observer_source": {
                    key: terrain.observer_source[key] for key in ("dataset_id", "resolution_m")},
            "geometry_method": METHOD_VERSION, "display_method": DISPLAY_VERSION,
            "heights_m": list(HEIGHTS), "fine_az_step_deg": FINE_STEP, "short_az_step_deg": SHORT_STEP,
            "datasets": terrain.provenance(), "source_inventory": inventory,
            "seams": seams, "references": references, "profiles": profiles,
            "coverage_complete": all(bool(p.coverage_complete.all()) for p in [*fine.values(), *short.values()])}
        store.publish(key, record, meshes)
    result = {"site_ids": target["site_ids"], "status": "prepared", "seconds": perf_counter()-started,
              "meshes": len(meshes), "coverage_complete": record["coverage_complete"]}
    print(json.dumps(result), flush=True)
    return result


def build_cap(store):
    inventory = [{"dataset_id": source["dataset_id"], "sha256": source["sha256"]} for source in installed_sources()]
    for samples in (257, 513):
        content = gzip.compress(json_bytes(south_polar_cap(samples)), mtime=0)
        store.publish_meshes({f"polar_cap:{samples}": {**store.put(content, "json.gz"),
            "display_method": DISPLAY_VERSION, "source_inventory": inventory, "samples": samples}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sites", nargs="+")
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2, 3, 4))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--global-only", action="store_true", help="Build just the two polar-cap display grids")
    args = parser.parse_args()
    selected = [target for target in targets(include_legacy=bool(args.sites)) if not args.sites or set(args.sites)&set(target["site_ids"])]
    if args.sites and set(args.sites)-{key for item in selected for key in item["site_ids"]}:
        parser.error("Unknown site ID")
    if args.list:
        print(json.dumps(selected, indent=2)); return
    store = Store(args.output_root)
    build_cap(store)
    if args.global_only:
        print(json.dumps(store.descriptor(), indent=2)); return
    records, errors = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(build_one, target, store.root): target for target in selected}
        for future in as_completed(pending):
            target = pending[future]
            try:
                records.append(future.result())
            except Exception as error:
                failure = {"site_ids": target["site_ids"], "error": f"{type(error).__name__}: {error}"}
                errors.append(failure)
                print(json.dumps(failure), flush=True)
    report = {"passed": not errors and len(records) == len(selected), "requested_sites": len(selected),
              "records": records, "errors": errors, "package": store.descriptor(), "live_llm_calls": 0}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
