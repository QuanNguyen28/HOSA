#!/usr/bin/env python3
"""Build deterministic browser terrain derivatives from a validated lunar DEM.

GDAL is used intentionally so CRS and NoData handling match the project's raster
toolchain. The output is display-only; scientific code continues reading the source DEM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import rasterio


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("prefix")
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--azimuth", type=float, default=315)
    parser.add_argument("--altitude", type=float, default=38)
    args = parser.parse_args()

    if args.size < 256 or args.size > 4096 or not math.isfinite(args.azimuth + args.altitude):
        raise ValueError("Unsupported rendering parameters")
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    for executable in ("gdal_translate", "gdaldem"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"Missing required executable: {executable}")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    height = args.output_directory / f"{args.prefix}_height.png"
    hillshade = args.output_directory / f"{args.prefix}_hillshade.jpg"

    with rasterio.open(args.source) as dataset:
        if dataset.count != 1 or dataset.crs is None:
            raise ValueError("Expected a single-band projected lunar DEM")
        minimum, maximum = (float(value) for value in dataset.tags(1)["actual_range"].strip("{}").split(","))
        source_metadata = {
            "shape": list(dataset.shape),
            "crs_wkt": dataset.crs.to_wkt(),
            "transform": list(dataset.transform)[:6],
            "bounds": list(dataset.bounds),
            "nodata": str(dataset.nodata),
            "source_range_m": [minimum, maximum],
        }

    with tempfile.TemporaryDirectory(prefix="hosa_terrain_") as temp:
        shade_tif = Path(temp) / "hillshade.tif"
        common = ["--config", "GDAL_PAM_ENABLED", "NO"]
        run([
            "gdal_translate", *common, "-q", "-of", "PNG", "-ot", "Byte",
            "-outsize", str(args.size), str(args.size), "-scale", str(minimum),
            str(maximum), "0", "255", str(args.source), str(height),
        ])
        run([
            "gdaldem", *common, "hillshade", "-q", "-compute_edges", "-az",
            str(args.azimuth), "-alt", str(args.altitude), str(args.source), str(shade_tif),
        ])
        run([
            "gdal_translate", *common, "-q", "-of", "JPEG", "-outsize",
            str(args.size), str(args.size), "-co", "QUALITY=92", str(shade_tif),
            str(hillshade),
        ])

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source),
        "source_sha256": sha256(args.source),
        "source_metadata": source_metadata,
        "parameters": {
            "size": args.size,
            "azimuth_deg": args.azimuth,
            "altitude_deg": args.altitude,
            "height_encoding": "Byte linear scale of source elevation range",
        },
        "outputs": {
            height.name: {"bytes": height.stat().st_size, "sha256": sha256(height)},
            hillshade.name: {"bytes": hillshade.stat().st_size, "sha256": sha256(hillshade)},
        },
        "scientific_use": False,
    }
    receipt_path = args.output_directory / f"{args.prefix}_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(receipt_path)


if __name__ == "__main__":
    main()
