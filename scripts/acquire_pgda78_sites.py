#!/usr/bin/env python3
"""Acquire selected NASA PGDA 78 site rasters with byte-level provenance."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.lunarsight.acquire import download, utc_now  # noqa: E402


from scripts.build_nasa_default_catalog import nasa_sites  # noqa: E402

SITE_NAMES = {site["source_code"]: site["name"] for site in nasa_sites()}
ROI_SITES = {"Site01", "Site04", "Site06", "Site07", "Site11"}
DEFAULT_SITES = tuple(SITE_NAMES)
BASE_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
SOURCE_PAGE = "https://pgda.gsfc.nasa.gov/products/78"
DATASET_COLUMNS = (
    "dataset_id",
    "title",
    "source_url",
    "download_utc",
    "original_filename",
    "sha256",
    "crs",
    "horizontal_unit",
    "vertical_unit",
    "spatial_extent",
    "nodata_value",
    "processing_version",
    "status",
)


def assets(site: str) -> list[dict[str, object]]:
    definitions = [
        ("dem", "surf.tif", "m"),
        ("error", "toterr.tif", "m RMS"),
        ("count", "ldec.tif", "LOLA spots"),
    ]
    if site in ROI_SITES:
        definitions.append(("roi", "ROIs.tgz", None))

    result = []
    for role, suffix, unit in definitions:
        filename = (
            f"{site}_ROIs.tgz"
            if role == "roi"
            else f"{site}_final_adj_5mpp_{suffix}"
        )
        result.append(
            {
                "id": f"{site}_{role}",
                "filename": filename,
                "url": f"{BASE_URL}/{site}/{filename}",
                "source_page": SOURCE_PAGE,
                "role": role,
                "unit": unit,
                "site": site,
                "frame": "MOON_ME/DE421",
            }
        )
    return result


def acquire(item: dict[str, object], offline: bool, range_workers=1) -> dict[str, object]:
    site_dir = ROOT / "data/raw" / str(item["site"])
    flat = ROOT / "data/raw/nasa"
    if not (site_dir / str(item["filename"])).is_file() and (flat / str(item["filename"])).is_file():
        site_dir = flat
    receipt = download(site_dir, item, offline=offline, range_workers=range_workers)
    tracked_dir = ROOT / "manifests/lunarsight/nasa"
    tracked_dir.mkdir(parents=True, exist_ok=True)
    adjacent = site_dir / f"{item['filename']}.receipt.json"
    shutil.copy2(adjacent, tracked_dir / adjacent.name)
    return receipt


def update_dataset_registry(
    records: list[dict[str, object]], failures: list[dict[str, str]] | None = None
) -> None:
    """Merge verified acquisitions into the repository-wide dataset inventory."""
    import rasterio

    registry = ROOT / "manifests/datasets.csv"
    with registry.open(encoding="utf-8", newline="") as stream:
        existing = list(csv.DictReader(stream))
    rows = {row["dataset_id"]: row for row in existing}

    for record in records:
        role = str(record["role"])
        site = str(record["site"])
        crs = horizontal_unit = extent = nodata = ""
        if role in {"dem", "error", "count"}:
            path = ROOT / "data/raw" / site / str(record["filename"])
            if not path.is_file():
                path = ROOT / "data/raw/nasa" / str(record["filename"])
            with rasterio.open(path) as dataset:
                crs = dataset.crs.to_wkt() if dataset.crs else ""
                horizontal_unit = "m"
                extent = str(list(dataset.bounds))
                nodata = "NaN" if dataset.nodata != dataset.nodata else str(dataset.nodata or "")
        rows[str(record["id"])] = {
            "dataset_id": str(record["id"]),
            "title": role,
            "source_url": str(record["url"]),
            "download_utc": str(record["accessed_utc"]),
            "original_filename": str(record["filename"]),
            "sha256": str(record["sha256"]),
            "crs": crs,
            "horizontal_unit": horizontal_unit,
            "vertical_unit": {"dem": "m", "error": "m RMS"}.get(role, ""),
            "spatial_extent": extent,
            "nodata_value": nodata,
            "processing_version": "0.2.0",
            "status": "PASS",
        }

    requested_by_id = {
        str(item["id"]): item for site in SITE_NAMES for item in assets(site)
    }
    for failure in failures or []:
        item = requested_by_id[failure["id"]]
        rows[failure["id"]] = {
            "dataset_id": failure["id"],
            "title": str(item["role"]),
            "source_url": str(item["url"]),
            "download_utc": "",
            "original_filename": str(item["filename"]),
            "sha256": "",
            "crs": "",
            "horizontal_unit": "",
            "vertical_unit": "",
            "spatial_extent": "",
            "nodata_value": "",
            "processing_version": "0.2.0",
            "status": "BLOCKED_UPSTREAM",
        }

    temporary = registry.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=DATASET_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows.values())
    temporary.replace(registry)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", nargs="+", default=list(DEFAULT_SITES))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--range-workers", type=int, default=1, choices=range(1, 17),
                        help="Parallel validated byte ranges per raster (bounded memory)")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--roles", nargs="+", choices=("dem", "error", "count", "roi"),
                        help="Restrict acquisition, e.g. dem error count when no ROI is needed")
    args = parser.parse_args()

    unknown = set(args.sites) - set(SITE_NAMES)
    if unknown:
        parser.error(f"Unknown site(s): {', '.join(sorted(unknown))}")
    if not 1 <= args.workers <= 6:
        parser.error("--workers must be between 1 and 6")

    requested = [item for site in args.sites for item in assets(site)
                 if not args.roles or item["role"] in args.roles]
    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(acquire, item, args.offline, args.range_workers): item for item in requested}
        for future in as_completed(futures):
            item = futures[future]
            try:
                record = future.result()
                records.append(record)
                print(
                    f"PASS {item['id']}: {record['bytes']} bytes "
                    f"sha256={record['sha256']}",
                    flush=True,
                )
            except Exception as exc:  # keep a complete acquisition report
                failures.append(
                    {
                        "id": str(item["id"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                print(f"FAIL {item['id']}: {failures[-1]['error']}", flush=True)

    records.sort(key=lambda record: str(record["id"]))
    report = {
        "schema_version": "1.0.0",
        "source_page": SOURCE_PAGE,
        "updated_utc": utc_now(),
        "sites": [
            {
                "site": site,
                "display_name": SITE_NAMES[site],
                "roi_published_by_nasa": site in ROI_SITES,
            }
            for site in args.sites
        ],
        "records": records,
        "failures": failures,
        "total_verified_bytes": sum(int(record["bytes"]) for record in records),
    }
    report_path = ROOT / "manifests/lunarsight/pgda78_selected_sites.json"
    # A selected/resumed acquisition must not erase provenance of earlier sites.
    if report_path.is_file():
        previous = json.loads(report_path.read_text())
        requested_ids = {item["id"] for item in requested}
        report["records"] = sorted([*records, *(record for record in previous.get("records", [])
            if record["id"] not in requested_ids)], key=lambda record: str(record["id"]))
        report["failures"] = [*failures, *(failure for failure in previous.get("failures", [])
            if failure["id"] not in requested_ids)]
        site_rows = {site["site"]: site for site in previous.get("sites", [])}
        site_rows.update({site["site"]: site for site in report["sites"]})
        report["sites"] = list(site_rows.values())
        report["total_verified_bytes"] = sum(int(record["bytes"]) for record in report["records"])
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    update_dataset_registry(records, failures)
    print(f"Report: {report_path}", flush=True)
    print(
        f"Verified {len(records)}/{len(requested)} assets; "
        f"{report['total_verified_bytes']} bytes; {len(failures)} failures",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
