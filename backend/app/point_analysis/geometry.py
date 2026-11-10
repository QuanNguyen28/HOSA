"""Coordinate horizon scan using the existing spherical ENU primitives."""
import numpy as np
import pandas as pd

from app.services.lunarsight.horizon import ray_positions, ray_elevation, reference_check, footprint_radius

METHOD_VERSION = "coordinate-enu-0.1.1"


def near_boundary(terrain, azimuths):
    if terrain.observer_source["resolution_m"] != 5:
        return np.zeros(len(azimuths))
    return np.minimum(8000, footprint_radius(terrain.site, terrain.observer_dem, azimuths, 275))


def scan_horizons(terrain, heights, radius=400000, az_step=.125):
    """Both device heights share DEM reads. Missing radial samples remain unknown.

    Radial spacing follows available resolution: 2.5 m near local 5 m data,
    40 m within 200 km with regional 80 m data, otherwise 120 m. Resolution
    transitions are validated independently before a scientific decision.
    """
    finest = terrain.observer_source["resolution_m"]
    has80 = any(source["resolution_m"] <= 80 for source, _ in terrain.layers)
    near_step = finest / 2
    near_stop = 8000 if finest == 5 else 0
    middle_step = 40 if has80 else 120
    azimuths = np.arange(0, 360, az_step)
    site = terrain.site
    outputs = {height: [] for height in heights}
    for offset in range(0, len(azimuths), 32):
        azimuth = azimuths[offset:offset+32]
        n = len(azimuth)
        near = near_boundary(terrain, azimuth)
        pieces = []
        if near_stop:
            distance = np.arange(near_step, near.max() + near_step / 2, near_step)
            pieces.append((0, distance, distance[None, :] <= near[:, None]))
        stop = min(200000, radius)
        steps = np.ceil((stop-near)/middle_step).astype(int)
        indices = np.arange(1, steps.max()+1)
        distance = near[:, None] + (stop-near)[:, None] * indices[None, :] / steps[:, None]
        pieces.append((80, distance, indices[None, :] <= steps[:, None]))
        if radius > 200000:
            distance = np.linspace(200000, radius, int(np.ceil((radius-200000)/120))+1)[1:]
            pieces.append((240, distance, np.ones((n, len(distance)), dtype=bool)))
        best = {h: np.full(n, -np.inf) for h in heights}
        blocker = {h: [np.full(n, np.nan) for _ in range(4)] for h in heights}
        missing = np.zeros(n, dtype=int)
        valid = np.zeros(n, dtype=int)
        for minimum_resolution, distance, active in pieces:
            lon, lat = ray_positions(site["lon_e_deg"], site["lat_deg"], azimuth, distance)
            z = np.full(lon.shape, np.nan)
            z[active], _ = terrain.sample(lon[active], lat[active], minimum_resolution)
            finite = np.isfinite(z)
            missing += (active & ~finite).sum(axis=1)
            valid += finite.sum(axis=1)
            for height in heights:
                elevation = np.where(finite, ray_elevation(z, site["dem_z_m"], height, distance), -np.inf)
                winner = elevation.argmax(axis=1)
                value = elevation[np.arange(n), winner]
                take = np.flatnonzero(value > best[height])
                win = winner[take]
                best[height][take] = value[take]
                for dest, data in zip(blocker[height], (np.broadcast_to(distance, z.shape), z, lon % 360, lat)):
                    dest[take] = data[take, win]
        for height in heights:
            for k, az in enumerate(azimuth):
                distance, z, lon, lat = [data[k] for data in blocker[height]]
                outputs[height].append({"site_id": "coordinate", "height_m": height,
                    "az_deg": float(az), "az_step_deg": az_step,
                    "horizon_deg": best[height][k] if np.isfinite(best[height][k]) else np.nan,
                    "blocker_distance_m": distance, "blocker_z_m": z,
                    "blocker_lon_e_deg": lon, "blocker_lat_deg": lat,
                    "scan_radius_m": radius, "coverage_complete": bool(missing[k] == 0),
                    "missing_samples": int(missing[k]), "valid_samples": int(valid[k])})
    return {h: pd.DataFrame(rows) for h, rows in outputs.items()}


def seam_checks(terrain):
    """Check overlapping source heights with independent angular phases, no datum fitting."""
    checks = []
    lon, lat, z = (terrain.site[k] for k in ("lon_e_deg", "lat_deg", "dem_z_m"))
    for i, (fine_source, fine) in enumerate(terrain.layers[:-1]):
        _, coarse = terrain.layers[i+1]
        for phase in (0, .25):
            az = np.arange(phase, 360, .5)
            switch = near_boundary(terrain, az) if fine_source["resolution_m"] == 5 else np.full(len(az), 200000)
            distances = switch[:, None] + np.linspace(-250, 250, 11)
            longitude, latitude = ray_positions(lon, lat, az, distances)
            a, b = fine.lonlat_at(longitude, latitude), coarse.lonlat_at(longitude, latitude)
            valid = np.isfinite(a) & np.isfinite(b)
            delta = b[valid] - a[valid]
            angular = (ray_elevation(b, z, 1, distances) - ray_elevation(a, z, 1, distances))[valid]
            # Multiple source tiles may have no shared valid region along this scan.
            # An unverified transition may never yield an ungated PASS.
            checks.append({"fine": fine_source["dataset_id"], "coarse": terrain.layers[i+1][0]["dataset_id"],
                "phase_deg": phase, "paired_samples": int(valid.sum()),
                "median_signed_m": float(np.median(delta)) if len(delta) else None,
                "p95_abs_angle_deg": float(np.percentile(abs(angular), 95)) if len(delta) else None,
                "passed": bool(len(delta) >= .9 * valid.size and abs(np.median(delta)) <= 10
                               and np.percentile(abs(angular), 95) <= .15)})
    return checks


def verify_profiles(profiles, site):
    return {str(h): {**reference_check(p, site), "passed": True}
            if np.isfinite(p.horizon_deg).any() else {"checks": 0, "passed": False}
            for h, p in profiles.items()}
