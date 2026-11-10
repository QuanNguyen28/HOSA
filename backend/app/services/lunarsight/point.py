"""Dynamic lunar terrain sampling with explicit coverage and provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any


METHOD_VERSION = "terrain-point-api-0.1.0"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def has_verified_receipt(path: Path) -> bool:
    receipt = path.with_name(path.name + ".receipt.json")
    if not path.is_file() or not receipt.is_file():
        return False
    try:
        import json

        record = json.loads(receipt.read_text(encoding="utf-8"))
        return (
            record.get("status") == "VERIFIED_BYTES"
            and record.get("bytes") == path.stat().st_size
            and isinstance(record.get("sha256"), str)
            and len(record["sha256"]) == 64
        )
    except (OSError, ValueError, TypeError):
        return False


def terrain_sources() -> list[dict[str, Any]]:
    root = repository_root()
    sources = [
        {
            "dataset_id": "Site01_dem",
            "path": root / "data/raw/Site01/Site01_final_adj_5mpp_surf.tif",
            "error_path": root / "data/raw/Site01/Site01_final_adj_5mpp_toterr.tif",
            "count_path": root / "data/raw/Site01/Site01_final_adj_5mpp_ldec.tif",
            "resolution_m": 5,
            "coverage_label": "Site01 local DEM",
        },
        {
            "dataset_id": "Site04_dem",
            "path": root / "data/raw/Site04/Site04_final_adj_5mpp_surf.tif",
            "error_path": root / "data/raw/Site04/Site04_final_adj_5mpp_toterr.tif",
            "count_path": root / "data/raw/Site04/Site04_final_adj_5mpp_ldec.tif",
            "resolution_m": 5,
            "coverage_label": "Site04 local DEM",
        },
        {
            "dataset_id": "dem80",
            "path": root / "data/raw/global/LDEM_80S_80MPP_ADJ.TIF",
            "resolution_m": 80,
            "coverage_label": "South of 80 degrees latitude",
        },
        {
            "dataset_id": "dem240",
            "path": root / "data/raw/global/LDEM_60S_240MPP_ADJ.TIF",
            "resolution_m": 240,
            "coverage_label": "South of 60 degrees latitude",
        },
    ]
    # Both the original site directories and prepare_point_data.py's flat NASA
    # directory are supported. Never select an unfinished .part file.
    for source in sources:
        for key in ("path", "error_path", "count_path"):
            if key in source:
                primary = source[key]
                alternative = root/"data/raw/nasa"/primary.name
                if not primary.is_file() and alternative.is_file():
                    source[key] = alternative
    return sources


def sample_terrain(latitude: float, longitude: float) -> dict[str, Any]:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 360:
        raise ValueError("Latitude must be within [-90, 90] and longitude within [-180, 360]")

    try:
        import numpy as np
        import rasterio

        from .terrain import DEM
    except ImportError as error:
        raise RuntimeError("Scientific terrain dependencies are not installed") from error

    inspected: list[str] = []
    for source in terrain_sources():
        path: Path = source["path"]
        if not has_verified_receipt(path):
            continue
        inspected.append(source["dataset_id"])
        with DEM(path, source["dataset_id"]) as dem:
            x, y = dem.fwd.transform(longitude, latitude)
            bounds = dem.ds.bounds
            if not (bounds.left <= x < bounds.right and bounds.bottom < y <= bounds.top):
                continue
            elevation = float(dem.xy_at(x, y))
            if not np.isfinite(elevation):
                continue
            row, col = dem.ds.index(x, y)
            neighborhood = dem.array(
                window=((max(0, row - 1), min(dem.ds.height, row + 2)),
                        (max(0, col - 1), min(dem.ds.width, col + 2)))
            )
            slope_deg: float | None = None
            roughness_m: float | None = None
            if neighborhood.shape == (3, 3) and np.isfinite(neighborhood).all():
                dz_dy, dz_dx = np.gradient(
                    neighborhood,
                    abs(dem.ds.res[1]),
                    abs(dem.ds.res[0]),
                )
                slope_deg = float(
                    np.degrees(np.arctan(np.hypot(dz_dx[1, 1], dz_dy[1, 1])))
                )
                roughness_m = float(np.std(neighborhood - neighborhood[1, 1]))
            quality: dict[str, Any] | None = None
            error_path = source.get("error_path")
            count_path = source.get("count_path")
            if (
                error_path
                and count_path
                and has_verified_receipt(error_path)
                and has_verified_receipt(count_path)
            ):
                quality = {}
                for label, quality_path in (
                    ("rms_error_m", error_path),
                    ("lola_spot_count", count_path),
                ):
                    with rasterio.open(quality_path) as layer:
                        if layer.shape != dem.ds.shape or layer.transform != dem.ds.transform:
                            raise ValueError(f"Quality raster is not aligned: {quality_path.name}")
                        raw = layer.read(1, window=((row, row + 1), (col, col + 1)), masked=True)
                        value = float(raw[0, 0]) * layer.scales[0] + layer.offsets[0]
                        quality[label] = value if np.isfinite(value) else None
            return {
                "coverage_status": "COVERED",
                "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
                "terrain": {
                    "elevation_m": elevation,
                    "resolution_m": source["resolution_m"],
                    "dataset_id": source["dataset_id"],
                    "coverage_label": source["coverage_label"],
                    "pixel_row": row,
                    "pixel_col": col,
                    "x_m": x,
                    "y_m": y,
                    "slope_deg": slope_deg,
                    "local_3x3_roughness_m": roughness_m,
                    "quality": quality,
                },
                "method_version": METHOD_VERSION,
                "provenance": {
                    "source": str(path.relative_to(repository_root())),
                    "frame": "MOON_ME/DE421",
                    "sample_method": "nearest registered pixel centre",
                },
                "warnings": [
                    "Elevation coverage alone is not a landing-suitability assessment.",
                    *([] if quality is not None else ["Aligned count/error quality rasters are not available for this dataset."]),
                ],
            }

    return {
        "coverage_status": "UNKNOWN",
        "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
        "terrain": None,
        "method_version": METHOD_VERSION,
        "inspected_datasets": inspected,
        "warnings": [
            "No validated local raster covers this coordinate; no elevation was inferred."
        ],
    }


def terrain_window(
    latitude: float,
    longitude: float,
    radius_km: float = 8.0,
    samples: int = 129,
) -> dict[str, Any]:
    """Return a bounded display mesh around a covered coordinate.

    Heights remain metres from the native DEM. The regular grid is a visualization
    transport and must not be used to recompute scientific horizon products.
    """
    if not 0.5 <= radius_km <= 32:
        raise ValueError("radius_km must be between 0.5 and 32")
    if samples not in {65, 129, 257}:
        raise ValueError("samples must be one of 65, 129 or 257")

    try:
        import numpy as np
        from rasterio.enums import Resampling
        from rasterio.windows import Window

        from .terrain import DEM
    except ImportError as error:
        raise RuntimeError("Scientific terrain dependencies are not installed") from error

    for source in terrain_sources():
        path: Path = source["path"]
        if not has_verified_receipt(path):
            continue
        with DEM(path, source["dataset_id"]) as dem:
            x, y = dem.fwd.transform(longitude, latitude)
            bounds = dem.ds.bounds
            if not (bounds.left <= x < bounds.right and bounds.bottom < y <= bounds.top):
                continue
            row, col = dem.ds.index(x, y)
            radius_m = radius_km * 1000
            half_cols = radius_m / abs(dem.ds.res[0])
            half_rows = radius_m / abs(dem.ds.res[1])
            window = Window(
                col - half_cols,
                row - half_rows,
                half_cols * 2,
                half_rows * 2,
            )
            values = dem.array(
                window=window,
                out_shape=(samples, samples),
                boundless=True,
                fill_value=np.nan,
                resampling=Resampling.bilinear,
            )
            finite = np.isfinite(values)
            if not finite.any():
                continue
            encoded = [None if not np.isfinite(value) else round(float(value), 3) for value in values.ravel()]
            return {
                "coverage_status": "COVERED",
                "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
                "dataset_id": source["dataset_id"],
                "native_resolution_m": source["resolution_m"],
                "radius_km": radius_km,
                "grid": {
                    "rows": samples,
                    "columns": samples,
                    "elevation_m_row_major": encoded,
                    "min_elevation_m": round(float(np.nanmin(values)), 3),
                    "max_elevation_m": round(float(np.nanmax(values)), 3),
                    "valid_fraction": round(float(finite.mean()), 6),
                    "spacing_m": round(radius_m * 2 / (samples - 1), 3),
                },
                "method_version": METHOD_VERSION,
                "provenance": {
                    "source": str(path.relative_to(repository_root())),
                    "frame": "local projected lunar polar stereographic",
                    "resampling": "bilinear for visualization only",
                },
                "warnings": [
                    "Display mesh only; use native DEM and validated horizon engine for scientific decisions."
                ],
            }

    return {
        "coverage_status": "UNKNOWN",
        "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
        "grid": None,
        "method_version": METHOD_VERSION,
        "warnings": ["No validated DEM covers the requested terrain window centre."],
    }
