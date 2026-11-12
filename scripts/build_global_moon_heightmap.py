#!/usr/bin/env python3
"""Build a browser LOD from the verified global NASA LOLA LDEM_64 image."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_RADIUS_M = 1_737_400.0
SOURCE_MIN_M = -18_251 * 0.5
SOURCE_MAX_M = 21_546 * 0.5


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data/raw/global/lola_ldem64/LDEM_64.JP2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "frontend/public/assets/nasa/lola_global_ldem64_4k.png",
    )
    parser.add_argument("--width", type=int, default=4096)
    parser.add_argument("--height", type=int, default=2048)
    args = parser.parse_args()
    source_image = args.source
    source_receipt = source_image.with_name(source_image.name + ".receipt.json")
    if not source_receipt.is_file():
        raise FileNotFoundError("Verified source receipt is required")
    receipt = json.loads(source_receipt.read_text(encoding="utf-8"))
    if (
        receipt.get("status") != "VERIFIED_BYTES"
        or receipt.get("sha256") != digest(source_image)
        or receipt.get("bytes") != source_image.stat().st_size
    ):
        raise ValueError("Global LOLA source receipt does not match installed bytes")

    with rasterio.open(source_image) as dataset:
        if dataset.width != 23_040 or dataset.height != 11_520 or dataset.dtypes[0] != "int16":
            raise ValueError("Unexpected LDEM_64 raster geometry")
        digital_number = dataset.read(
            1,
            out_shape=(args.height, args.width),
            resampling=Resampling.bilinear,
        ).astype("float64")
    elevation_m = digital_number * 0.5
    normalized = np.clip(
        (elevation_m - SOURCE_MIN_M) / (SOURCE_MAX_M - SOURCE_MIN_M),
        0,
        1,
    )
    encoded = np.round(normalized * 255).astype("uint8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "PNG",
        "width": args.width,
        "height": args.height,
        # Browser image decoders and WebGL texture loaders are more consistent
        # with RGB PNGs than single-channel greyscale PNGs.  Repeat the exact
        # encoded height value in all channels; no elevation precision changes.
        "count": 3,
        "dtype": "uint8",
    }
    with rasterio.open(args.output, "w", **profile) as output:
        output.write(np.repeat(encoded[np.newaxis, :, :], 3, axis=0))

    scene_radius = 2.0
    metadata = {
        "id": "lola_global_ldem64_web_lod",
        "status": "DERIVED_FROM_VERIFIED_BYTES",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source_image.relative_to(ROOT)),
        "source_sha256": receipt["sha256"],
        "source_frame": "MOON_ME/DE421",
        "source_resolution": "64 pixels/degree; 473.802 m/pixel at equator",
        "output": str(args.output.relative_to(ROOT)),
        "output_sha256": digest(args.output),
        "output_shape": [args.height, args.width],
        "encoding": {
            "dtype": "uint8",
            "channels": "RGB; identical normalized elevation in each channel",
            "minimum_elevation_m": SOURCE_MIN_M,
            "maximum_elevation_m": SOURCE_MAX_M,
        },
        "renderer": {
            "lunar_reference_radius_m": REFERENCE_RADIUS_M,
            "moon_scene_radius": scene_radius,
            "displacement_scale": scene_radius
            * (SOURCE_MAX_M - SOURCE_MIN_M)
            / REFERENCE_RADIUS_M,
            "displacement_bias": scene_radius * SOURCE_MIN_M / REFERENCE_RADIUS_M,
        },
        "method": "Rasterio bilinear display resampling; source elevations retain true radial scale",
    }
    metadata_path = args.output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(metadata_path)


if __name__ == "__main__":
    main()
