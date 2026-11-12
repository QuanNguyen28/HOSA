#!/usr/bin/env python3
"""Build a candidate-region catalog from NASA Moon Trek Artemis polygons.

Region centroids are navigation anchors for the UI, not recommended landing
points. They remain UNASSESSED until terrain, illumination and communication
pipelines evaluate a specific coordinate inside the polygon.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer
from shapely import transform
from shapely.geometry import Polygon, mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/raw/full_product/sites/artemis_candidate_regions.json"
DEFAULT_OUTPUT = ROOT / "data/processed/lunarsight/v0.4.0/artemis_candidate_regions.geojson"
MOON_SOUTH_POLAR = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
)
MOON_LON_LAT = CRS.from_proj4("+proj=longlat +R=1737400 +no_defs")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hashfile(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "candidate-region"


def build_catalog(source: Path) -> dict[str, Any]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("error"):
        raise ValueError(f"Moon Trek API error: {raw['error']}")
    features = raw.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Moon Trek response has no candidate-region features")

    transformer = Transformer.from_crs(MOON_SOUTH_POLAR, MOON_LON_LAT, always_xy=True)
    output = []
    for feature in features:
        attributes = feature.get("attributes", {})
        rings = feature.get("geometry", {}).get("rings")
        if not rings:
            raise ValueError(f"Region has no polygon rings: {attributes}")
        polygon_projected = Polygon(rings[0], holes=rings[1:] or None)
        if not polygon_projected.is_valid:
            polygon_projected = polygon_projected.buffer(0)
        polygon_lonlat = transform(polygon_projected, transformer.transform, interleaved=False)
        center_projected = polygon_projected.centroid
        center_lon, center_lat = transformer.transform(center_projected.x, center_projected.y)
        name = str(attributes.get("label") or f"Region {attributes.get('FID')}")
        output.append(
            {
                "type": "Feature",
                "id": f"artemis-{int(attributes['FID']):02d}-{slug(name)}",
                "geometry": mapping(polygon_lonlat),
                "properties": {
                    "name": name,
                    "source_feature_id": attributes.get("FID"),
                    "source": "NASA/JPL Moon Trek A3_Named_regions_SP",
                    "source_url": "https://trek.nasa.gov/moon/trekarcgis2/rest/services/A3_Named_regions_SP/MapServer/0",
                    "anchor_longitude_east_deg": center_lon % 360.0,
                    "anchor_latitude_deg": center_lat,
                    "anchor_projected_x_m": center_projected.x,
                    "anchor_projected_y_m": center_projected.y,
                    "area_km2": polygon_projected.area / 1_000_000.0,
                    "assessment_status": "UNASSESSED_REGION_CENTROID",
                    "anchor_warning": "UI navigation anchor only; not a certified or optimized landing point.",
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "NASA Artemis candidate landing regions",
        "lunar_coordinate_model": "sphere radius 1737400 m; planetocentric latitude; east longitude",
        "features": output,
    }


def write_outputs(catalog: dict[str, Any], source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = output.with_suffix(".csv")
    fields = [
        "site_id",
        "display_name",
        "longitude_east_deg",
        "latitude_deg",
        "projected_x_m",
        "projected_y_m",
        "area_km2",
        "assessment_status",
        "source_url",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for feature in catalog["features"]:
            properties = feature["properties"]
            writer.writerow(
                {
                    "site_id": feature["id"],
                    "display_name": properties["name"],
                    "longitude_east_deg": properties["anchor_longitude_east_deg"],
                    "latitude_deg": properties["anchor_latitude_deg"],
                    "projected_x_m": properties["anchor_projected_x_m"],
                    "projected_y_m": properties["anchor_projected_y_m"],
                    "area_km2": properties["area_km2"],
                    "assessment_status": properties["assessment_status"],
                    "source_url": properties["source_url"],
                }
            )
    receipt = {
        "generated_utc": utc_now(),
        "source": str(source.relative_to(ROOT)),
        "source_sha256": hashfile(source),
        "outputs": {
            str(output.relative_to(ROOT)): hashfile(output),
            str(csv_path.relative_to(ROOT)): hashfile(csv_path),
        },
        "feature_count": len(catalog["features"]),
        "status": "DERIVED_UNASSESSED",
    }
    receipt_path = output.with_name(output.name + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    catalog = build_catalog(args.input.resolve())
    write_outputs(catalog, args.input.resolve(), args.output.resolve())
    print(f"Wrote {len(catalog['features'])} unassessed candidate regions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
