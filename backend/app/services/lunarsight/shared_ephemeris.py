"""Reusable, hourly Moon-centred SPICE vectors; no network in a calculation.

UTC tables are generated in monthly chunks, including both boundaries. The
observer is subtracted in MOON_ME before rotation to ENU (Earth parallax matters).
Coverage is determined by the installed kernels, never by clamping a timestamp.
"""
from functools import lru_cache
from pathlib import Path
from threading import RLock
import json

import numpy as np
import pandas as pd
from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest
from .acquire import hashfile
from .terrain import R

VERSION = "shared-spice-hourly-1.0"
FRAME = "MOON_ME"
CORRECTION = "LT+S"
ANGLE_TOLERANCE_DEG = .001
KERNELS = (
    "lsk/naif0012.tls", "pck/pck00011.tpc", "spk/planets/de440s.bsp",
    "pck/moon_pa_de440_200625.bpc", "fk/satellites/moon_de440_250416.tf",
)
NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
_lock = RLock()
_loaded = None


def default_root():
    return Path(__file__).resolve().parents[4] / "data/cache/shared-ephemeris"


@lru_cache(maxsize=32)
def _checked_hash(path, size, mtime, ctime):
    return hashfile(Path(path))


class SharedEphemeris:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else default_root()

    def identity(self):
        kernels = []
        for relative in KERNELS:
            path = self.root / "kernels" / Path(relative).name
            receipt = path.with_suffix(path.suffix + ".receipt.json")
            if not path.is_file() or not receipt.is_file():
                raise DomainError("EPHEMERIS_NOT_PREPARED", 503)
            try:
                record = json.loads(receipt.read_text())
                stat = path.stat()
                sha = _checked_hash(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                if record["url"] != NAIF + relative or record["sha256"] != sha or record["bytes"] != stat.st_size:
                    raise ValueError("Kernel receipt mismatch")
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise DomainError("EPHEMERIS_INTEGRITY_FAILED", 503) from error
            kernels.append({"name": path.name, "sha256": sha})
        return {"method_version": VERSION, "kernels": kernels, "frame": FRAME,
                "correction": CORRECTION, "step_seconds": 3600, "units": "km", "storage": "float64"}

    def descriptor(self):
        try:
            return {"available": True, **self.identity()}
        except DomainError as error:
            return {"available": False, "method_version": VERSION, "error_code": error.code}

    def _load(self, identity):
        import spiceypy as sp
        global _loaded
        key = (str(self.root.resolve()), digest(identity))
        if _loaded != key:
            # All SPICE calls in this module hold _lock: kernel pools are global.
            sp.kclear()
            for item in identity["kernels"]:
                sp.furnsh(str(self.root / "kernels" / item["name"]))
            _loaded = key
        return sp

    def exact(self, times, identity=None):
        identity = identity or self.identity()
        with _lock:
            sp = self._load(identity)
            try:
                et = np.array([sp.str2et(t.tz_convert("UTC").tz_localize(None).isoformat()) for t in pd.DatetimeIndex(times)])
                return np.column_stack([np.asarray(sp.spkpos(body, et, FRAME, CORRECTION, "MOON")[0]).reshape(-1, 3)
                                        for body in ("SUN", "EARTH")])
            except (sp.utils.exceptions.SpiceSPKINSUFFDATA, sp.utils.exceptions.SpiceFRAMEDATANOTFOUND) as error:
                raise DomainError("OUTSIDE_EPHEMERIS_COVERAGE", 409) from error

    def chunk(self, month, identity):
        start = pd.Timestamp(month, tz="UTC")
        stop = start + pd.offsets.MonthBegin(1)
        key = digest({**identity, "start": start.isoformat(), "stop": stop.isoformat()})
        directory = self.root / "tables"
        directory.mkdir(parents=True, exist_ok=True)
        path, receipt = directory / f"{key}.npy", directory / f"{key}.json"
        with FileLock(str(directory / f"{key}.lock")):
            if not path.exists():
                values = self.exact(pd.date_range(start, stop, freq="1h"), identity)
                temporary = path.with_suffix(".part")
                with temporary.open("wb") as handle:
                    np.save(handle, values, allow_pickle=False)
                temporary.replace(path)
                receipt.write_text(json.dumps({"key": key, "sha256": hashfile(path)}))
            try:
                record = json.loads(receipt.read_text())
                if record != {"key": key, "sha256": hashfile(path)}:
                    raise ValueError("Shared vector table checksum mismatch")
                values = np.load(path, allow_pickle=False)
                if values.shape != (int((stop-start).total_seconds()/3600)+1, 6) or not np.isfinite(values).all():
                    raise ValueError("Invalid vector table")
            except (OSError, ValueError) as error:
                raise DomainError("EPHEMERIS_INTEGRITY_FAILED", 503) from error
        return values, {"month": month, "sha256": record["sha256"]}

    def vectors(self, times, identity):
        times = pd.DatetimeIndex(times)
        if times.tz is None or times.empty or times.hasnans:
            raise ValueError("Expected nonempty aware timestamps")
        times = times.tz_convert("UTC")
        # Microseconds cover Python's complete calendar; nanoseconds would wrap
        # dates beyond 2262 into another century before a coverage check.
        utc = times.to_numpy(dtype="datetime64[us]")
        months = utc.astype("datetime64[M]")
        output, receipts = np.empty((len(times), 6)), []
        for month in np.unique(months):
            table, receipt = self.chunk(str(month)+"-01", identity)
            selected = months == month
            f = np.asarray((utc[selected]-month.astype("datetime64[us]"))/np.timedelta64(1, "h"))
            k = np.floor(f).astype(int)
            # No clipping or reuse of another month's boundary value.
            if (k < 0).any() or (k+1 >= len(table)).any():
                raise DomainError("OUTSIDE_EPHEMERIS_COVERAGE", 409)
            output[selected] = table[k] + (f-k)[:, None]*(table[k+1]-table[k])
            receipts.append(receipt)
        return output, receipts

    @staticmethod
    def topocentric(vectors, site, height, target):
        lon, lat = np.deg2rad([site["lon_e_deg"], site["lat_deg"]])
        up = np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
        east = np.array([-np.sin(lon), np.cos(lon), 0.])
        north = np.cross(up, east)
        observer = (R+site["dem_z_m"]+height)/1000*up
        vector = vectors[:, :3] if target == 10 else vectors[:, 3:]
        delta = vector-observer
        e, n, u = delta@east, delta@north, delta@up
        return np.rad2deg(np.arctan2(e, n)) % 360, np.rad2deg(np.arctan2(u, np.hypot(e, n))), np.linalg.norm(delta, axis=1)

    def sample(self, site, target, height, start, end, step):
        identity = self.identity()
        grid = pd.date_range(start, end, freq=f"{step}min")
        vectors, tables = self.vectors(grid, identity)
        az, el, distance = self.topocentric(vectors, site, height, target)
        # Independent exact SPICE epochs check interpolation, not a second
        # interpolation of the same coarse table. Sampling is provisional.
        count = min(25, len(grid))
        weights = np.r_[0., (np.arange(count-2)+.38196601125)/(count-2), 1.]
        probes = pd.DatetimeIndex(pd.Timestamp(start)+(pd.Timestamp(end)-pd.Timestamp(start))*weights)
        exact = self.topocentric(self.exact(probes, identity), site, height, target)
        sampled = self.topocentric(self.vectors(probes, identity)[0], site, height, target)
        errors = [float(np.max(np.abs((sampled[0]-exact[0]+180) % 360-180))),
                  float(np.max(np.abs(sampled[1]-exact[1])))]
        passed = max(errors) <= ANGLE_TOLERANCE_DEG
        frame = pd.DataFrame({"az_deg": az, "el_deg": el, "distance_km": distance, "row_present": True}, index=grid)
        return frame, {"provider": VERSION, "identity": identity, "tables": tables,
            "target": target, "step_minutes": step, "missing_timestamps": 0, "missing_angles": 0,
            "interpolation_validation": {"passed": passed, "probe_count": len(probes),
                "max_az_error_deg": errors[0], "max_el_error_deg": errors[1],
                "tolerance_deg": ANGLE_TOLERANCE_DEG, "reference": "exact SPICE at probe epochs",
                "scope": "sampled numerical check, not a continuous-time error bound"}}
