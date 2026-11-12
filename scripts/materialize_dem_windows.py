#!/usr/bin/env python3
"""Materialize bounded 10 m/20 m LOLA COG windows for selected lunar sites."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from pyproj import CRS, Transformer
from rasterio.windows import from_bounds


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "data/processed/lunarsight/v0.4.0/artemis_candidate_regions.geojson"
DESTINATION = ROOT / "data/raw/full_product/dem/windows"
SOURCES = {
    "near10": {
        "dataset_id": "lola_dem_83s_10m",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "resolution_m": 10.0,
        "half_size_m": 20_000.0,
        "limit_m": 216_400.0,
    },
    "mid20": {
        "dataset_id": "lola_dem_80s_20m",
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF",
        "resolution_m": 20.0,
        "half_size_m": 60_000.0,
        "limit_m": 304_000.0,
    },
}
MOON_SOUTH_POLAR = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
)
MOON_LON_LAT = CRS.from_proj4("+proj=longlat +R=1737400 +no_defs")
TO_POLAR = Transformer.from_crs(MOON_LON_LAT, MOON_SOUTH_POLAR, always_xy=True)
GDAL_HTTP_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".TIF,.tif",
    "GDAL_HTTP_USERAGENT": "LunarSight/0.4 official-data-acquisition",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": str(256 * 1024 * 1024),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "point"


def snapped_bounds(x: float, y: float, tier: str) -> tuple[float, float, float, float]:
    config = SOURCES[tier]
    half = config["half_size_m"]
    resolution = config["resolution_m"]
    limit = config["limit_m"]
    low = lambda value: max(-limit, np.floor(value / resolution) * resolution)
    high = lambda value: min(limit, np.ceil(value / resolution) * resolution)
    bounds = (low(x - half), low(y - half), high(x + half), high(y + half))
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError(f"Point is outside the {tier} DEM coverage")
    return tuple(float(value) for value in bounds)


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    points = []
    for feature in payload.get("features", []):
        properties = feature["properties"]
        points.append(
            {
                "id": feature.get("id") or safe_name(properties["name"]),
                "name": properties["name"],
                "lat": float(properties["anchor_latitude_deg"]),
                "lon": float(properties["anchor_longitude_east_deg"]),
            }
        )
    if not points:
        raise ValueError(f"No site anchors found in {path}")
    return points


def parse_point(value: str) -> dict[str, Any]:
    try:
        name, latitude, longitude = value.split(",", 2)
        lat = float(latitude)
        lon = float(longitude)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Point must be NAME,LATITUDE,LONGITUDE_EAST") from exc
    if not -90 <= lat <= 90:
        raise argparse.ArgumentTypeError("Latitude must be between -90 and 90")
    return {"id": safe_name(name), "name": name, "lat": lat, "lon": lon % 360.0}


def source_identity(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
        timeout=(20, 90),
    )
    response.raise_for_status()
    content_range = response.headers.get("Content-Range")
    if response.status_code != 206 or not content_range:
        raise ValueError("Remote DEM does not provide stable HTTP byte ranges")
    return {
        "content_range_probe": content_range,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
    }


def materialize(point: dict[str, Any], tier: str, identity: dict[str, Any]) -> Path:
    config = SOURCES[tier]
    x, y = TO_POLAR.transform(point["lon"], point["lat"])
    bounds = snapped_bounds(float(x), float(y), tier)
    destination = DESTINATION / tier / f"{safe_name(point['id'])}.tif"
    receipt_path = destination.with_name(destination.name + ".receipt.json")
    if destination.exists():
        if not receipt_path.exists():
            raise ValueError(f"Unreceipted existing DEM window: {destination}")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    url = config["url"]
    with rasterio.Env(**GDAL_HTTP_ENV), rasterio.open("/vsicurl/" + url) as source:
        if abs(abs(source.transform.a) - config["resolution_m"]) > 0.01:
            raise ValueError(f"Unexpected source resolution for {tier}: {source.transform.a}")
        window = from_bounds(*bounds, transform=source.transform).round_offsets().round_lengths()
        data = source.read(1, window=window)
        if data.size == 0 or not np.isfinite(data).any():
            raise ValueError(f"No finite DEM samples for {point['name']} in {tier}")
        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            dtype=str(data.dtype),
            count=1,
            width=data.shape[1],
            height=data.shape[0],
            transform=source.window_transform(window),
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="deflate",
            predictor=3,
        )
    try:
        with rasterio.open(temporary, "w", **profile) as target:
            target.write(data, 1)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    receipt = {
        "dataset_id": config["dataset_id"],
        "source_url": url,
        "source_identity": identity,
        "site": point,
        "projected_anchor_m": [x, y],
        "requested_bounds_m": bounds,
        "resolution_m": config["resolution_m"],
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "created_utc": utc_now(),
        "status": "VERIFIED_WINDOW",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--point", action="append", type=parse_point, default=[])
    parser.add_argument("--tier", action="append", choices=tuple(SOURCES), default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    points = args.point or load_catalog(args.catalog.resolve())
    tiers = args.tier or list(SOURCES)
    for tier in tiers:
        identity = {} if args.dry_run else source_identity(SOURCES[tier]["url"])
        for point in points:
            x, y = TO_POLAR.transform(point["lon"], point["lat"])
            bounds = snapped_bounds(float(x), float(y), tier)
            if args.dry_run:
                rows = int(round((bounds[3] - bounds[1]) / SOURCES[tier]["resolution_m"]))
                columns = int(round((bounds[2] - bounds[0]) / SOURCES[tier]["resolution_m"]))
                print(f"PLAN {tier} {point['id']} {rows}x{columns} pixels")
            else:
                output = materialize(point, tier, identity)
                print(f"OK   {tier} {point['id']} -> {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
