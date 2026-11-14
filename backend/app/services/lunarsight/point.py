"""Dynamic lunar terrain sampling with explicit coverage and provenance."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


METHOD_VERSION = "terrain-point-api-0.1.0"
# Regional (context) windows fall back to a coarser DEM that covers more of the
# window; their display cache key carries this version (see precompute.display).
REGIONAL_COVERAGE_VERSION = "regional-coverage-1"
REGIONAL_MIN_COVERAGE = 0.999
LUNAR_REFERENCE_RADIUS_M = 1_737_400.0


def _initial_bearing_deg(
    longitude_a_deg: float,
    latitude_a_deg: float,
    longitude_b_deg: float,
    latitude_b_deg: float,
) -> float:
    """Return spherical initial bearing clockwise from local north."""
    longitude_a = math.radians(longitude_a_deg)
    latitude_a = math.radians(latitude_a_deg)
    longitude_b = math.radians(longitude_b_deg)
    latitude_b = math.radians(latitude_b_deg)
    delta_longitude = longitude_b - longitude_a
    east = math.sin(delta_longitude) * math.cos(latitude_b)
    north = (
        math.cos(latitude_a) * math.sin(latitude_b)
        - math.sin(latitude_a) * math.cos(latitude_b) * math.cos(delta_longitude)
    )
    return math.degrees(math.atan2(east, north)) % 360.0


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
    local_sites = (
        "Site01",
        "Site04",
        "Site06",
        "Site07",
        "Site11",
        "Site20v2",
        "Site20",
        "Site23",
        "Site42",
        "Haworth",
        "Shoemaker",
        "DM1",
        "DM2",
        "SL2",
        "SL3",
        "NPA",
        "NPB",
        "NPC",
        "NPD",
        *[f"LM{i}" for i in range(1, 9)],
    )
    sources = [
        {
            "dataset_id": f"{site}_dem",
            "path": root / f"data/raw/{site}/{site}_final_adj_5mpp_surf.tif",
            "error_path": root / f"data/raw/{site}/{site}_final_adj_5mpp_toterr.tif",
            "count_path": root / f"data/raw/{site}/{site}_final_adj_5mpp_ldec.tif",
            "resolution_m": 5,
            "coverage_label": f"{site} local DEM",
        }
        for site in local_sites
    ]
    sources.extend([
        {
            "dataset_id": "dem80",
            "path": root / "data/raw/global/LDEM_80S_80MPP_ADJ.TIF",
            "error_path": root / "data/raw/full_product/quality/LDEM_80S_80MPP_ADJ_ERR.TIF",
            "effective_resolution_path": root / "data/raw/full_product/quality/LDEM_80S_80MPP_ADJ_EFFRES.TIF",
            "resolution_m": 80,
            "coverage_label": "South of 80 degrees latitude",
        },
        {
            "dataset_id": "dem240",
            "path": root / "data/raw/global/LDEM_60S_240MPP_ADJ.TIF",
            "resolution_m": 240,
            "coverage_label": "South of 60 degrees latitude",
        },
    ])
    # Both the original site directories and prepare_point_data.py's flat NASA
    # directory are supported. Never select an unfinished .part file.
    for source in sources:
        for key in ("path", "error_path", "count_path", "effective_resolution_path"):
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
            effective_resolution_path = source.get("effective_resolution_path")
            verified_quality_paths = [
                ("rms_error_m", error_path),
                ("lola_spot_count", count_path),
                ("effective_resolution_m", effective_resolution_path),
            ]
            verified_quality_paths = [
                (label, quality_path)
                for label, quality_path in verified_quality_paths
                if quality_path and has_verified_receipt(quality_path)
            ]
            if verified_quality_paths:
                quality = {}
                for label, quality_path in verified_quality_paths:
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
    detail: str = "best",
) -> dict[str, Any]:
    from app.precompute.display import mesh_response, decode
    return decode(mesh_response(latitude, longitude, radius_km, samples, detail)[0])


def _terrain_window_uncached(
    latitude: float,
    longitude: float,
    radius_km: float = 8.0,
    samples: int = 129,
    detail: str = "best",
) -> dict[str, Any]:
    """Return a bounded display mesh around a covered coordinate.

    Heights remain metres from the native DEM. The regular grid is a visualization
    transport and must not be used to recompute scientific horizon products.
    """
    if not 0.5 <= radius_km <= 300:
        raise ValueError("radius_km must be between 0.5 and 300")
    if samples not in {65, 129, 257, 401, 513}:
        raise ValueError("samples must be one of 65, 129, 257, 401 or 513")
    if detail not in {"best", "regional"}:
        raise ValueError("detail must be best or regional")

    try:
        import numpy as np
        from rasterio.enums import Resampling
        from rasterio.windows import Window

        from .terrain import DEM
    except ImportError as error:
        raise RuntimeError("Scientific terrain dependencies are not installed") from error

    best: tuple[float, dict[str, Any]] | None = None
    for source in terrain_sources():
        # A wide context mesh must not inherit the finite footprint of a local
        # 5 m tile. Use the continuous south-polar DEM for that LOD instead.
        if detail == "regional" and source["resolution_m"] < 80:
            continue
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
            centre_index = samples // 2
            centre_elevation = float(values[centre_index, centre_index])
            if not np.isfinite(centre_elevation):
                centre_elevation = float(dem.xy_at(x, y))
            if not np.isfinite(centre_elevation):
                continue
            step_x = abs(float(dem.ds.res[0]))
            step_y = abs(float(dem.ds.res[1]))
            column_lon, column_lat = dem.inv.transform(x + step_x, y)
            row_lon, row_lat = dem.inv.transform(x, y - step_y)
            column_azimuth = _initial_bearing_deg(
                longitude, latitude, column_lon, column_lat
            )
            row_azimuth = _initial_bearing_deg(
                longitude, latitude, row_lon, row_lat
            )
            encoded = [None if not np.isfinite(value) else round(float(value), 3) for value in values.ravel()]
            payload = {
                "coverage_status": "COVERED",
                "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
                "dataset_id": source["dataset_id"],
                "native_resolution_m": source["resolution_m"],
                "detail": detail,
                "radius_km": radius_km,
                "geometry": {
                    "horizontal_scale": 1.0,
                    "vertical_scale": 1.0,
                    "horizontal_unit": "metre",
                    "vertical_unit": "metre",
                    "lunar_reference_radius_m": LUNAR_REFERENCE_RADIUS_M,
                    "center_elevation_m": round(centre_elevation, 3),
                    "center_x_m": round(float(x), 6),
                    "center_y_m": round(float(y), 6),
                    "column_azimuth_deg": round(column_azimuth, 9),
                    "row_azimuth_deg": round(row_azimuth, 9),
                    "projection": "spherical south polar stereographic",
                    "surface_model": "spherical tangent frame with DEM radial elevation",
                },
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
                    "Geometry uses a true 1:1 horizontal/vertical metre scale and lunar spherical curvature.",
                    "The transported grid is bilinearly resampled for display; use the native DEM and validated horizon engine for scientific decisions."
                ],
            }
            # Wide context rings around points near 80 S run past the 80 m
            # south-polar DEM (half of a 300 km ring at 81.5 S is NaN). Keep
            # the finest source that covers the window; otherwise use the one
            # covering most of it (the 240 m DEM reaches 60 S).
            fraction = float(finite.mean())
            if detail != "regional" or fraction >= REGIONAL_MIN_COVERAGE:
                return payload
            if best is None or fraction > best[0]:
                best = (fraction, payload)

    if best is not None:
        return best[1]
    return {
        "coverage_status": "UNKNOWN",
        "coordinate": {"latitude_deg": latitude, "longitude_e_deg": longitude},
        "grid": None,
        "method_version": METHOD_VERSION,
        "warnings": ["No validated DEM covers the requested terrain window centre."],
    }


def south_polar_cap(samples: int = 513) -> dict[str, Any]:
    from app.precompute.display import cap_response, decode
    return decode(cap_response(samples)[0])


def _south_polar_cap_uncached(samples: int = 513) -> dict[str, Any]:
    """Return a display LOD for the complete NASA DEM south of 80 degrees.

    The grid remains in the source lunar polar-stereographic frame. Clients can
    reconstruct geocentric vertices without treating the raster as an Earth map.
    Site footprints are the exact projected bounds of each verified 5 m DEM.
    """
    if samples not in {257, 513}:
        raise ValueError("samples must be 257 or 513")

    try:
        import numpy as np
        from rasterio.enums import Resampling

        from .terrain import DEM
    except ImportError as error:
        raise RuntimeError("Scientific terrain dependencies are not installed") from error

    source = next(item for item in terrain_sources() if item["dataset_id"] == "dem80")
    path: Path = source["path"]
    if not has_verified_receipt(path):
        raise RuntimeError("Verified south-polar DEM is not installed")

    with DEM(path, source["dataset_id"]) as dem:
        values = dem.array(
            out_shape=(samples, samples),
            resampling=Resampling.bilinear,
        )
        finite = np.isfinite(values)
        if not finite.any():
            raise RuntimeError("South-polar DEM contains no valid terrain samples")
        bounds = dem.ds.bounds
        encoded = [
            None if not np.isfinite(value) else round(float(value), 1)
            for value in values.ravel()
        ]

    footprints: list[dict[str, Any]] = []
    for local in terrain_sources():
        if local["resolution_m"] != 5 or not has_verified_receipt(local["path"]):
            continue
        with DEM(local["path"], local["dataset_id"]) as site_dem:
            site_bounds = site_dem.ds.bounds
            projected_ring = [
                (site_bounds.left, site_bounds.top),
                (site_bounds.right, site_bounds.top),
                (site_bounds.right, site_bounds.bottom),
                (site_bounds.left, site_bounds.bottom),
                (site_bounds.left, site_bounds.top),
            ]
            geographic_ring = []
            for x_m, y_m in projected_ring:
                longitude, latitude = site_dem.inv.transform(x_m, y_m)
                geographic_ring.append(
                    [round(float(longitude), 9), round(float(latitude), 9)]
                )
            footprints.append({
                "site_id": local["dataset_id"].removesuffix("_dem"),
                "dataset_id": local["dataset_id"],
                "native_resolution_m": local["resolution_m"],
                "bounds_xy_m": [
                    site_bounds.left,
                    site_bounds.bottom,
                    site_bounds.right,
                    site_bounds.top,
                ],
                "ring_lon_lat": geographic_ring,
            })

    return {
        "coverage_status": "COVERED",
        "dataset_id": source["dataset_id"],
        "native_resolution_m": source["resolution_m"],
        "latitude_limit_deg": -80.0,
        "projection": {
            "name": "spherical south polar stereographic",
            "lunar_reference_radius_m": LUNAR_REFERENCE_RADIUS_M,
            "bounds_xy_m": [bounds.left, bounds.bottom, bounds.right, bounds.top],
        },
        "grid": {
            "rows": samples,
            "columns": samples,
            "elevation_m_row_major": encoded,
            "min_elevation_m": round(float(np.nanmin(values)), 1),
            "max_elevation_m": round(float(np.nanmax(values)), 1),
            "valid_fraction": round(float(finite.mean()), 6),
            "effective_spacing_m": round((bounds.right - bounds.left) / (samples - 1), 3),
        },
        "site_footprints": footprints,
        "method_version": METHOD_VERSION,
        "provenance": {
            "source": str(path.relative_to(repository_root())),
            "frame": "MOON_ME/DE421",
            "resampling": "bilinear display LOD from the validated native 80 m DEM",
        },
        "warnings": [
            "This cap is a visualization LOD; scientific point values must be sampled from the native DEM.",
            "Terrain elevation is rendered at true radial scale relative to the 1,737.4 km lunar reference sphere.",
        ],
    }
