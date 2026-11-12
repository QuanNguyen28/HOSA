"""Read and verify original NASA DEMs; never fetch datasets inside an HTTP request."""
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
import csv

import numpy as np

from app.core.errors import DomainError
from app.services.lunarsight.acquire import hashfile, load, sources
from app.services.lunarsight.point import repository_root, terrain_sources
from app.services.lunarsight.terrain import DEM


@lru_cache(maxsize=32)
def checked_digest(path: str, size: int, mtime_ns: int, ctime_ns: int):
    return hashfile(path)


def verified_source(source):
    path = Path(source["path"])
    receipt = path.with_name(path.name + ".receipt.json")
    if not path.is_file():
        return None
    if not receipt.is_file():
        raise DomainError("DEM_RECEIPT_MISSING", 503)
    receipt_record = load(receipt)
    official = next((item for item in sources() if item["id"] == source["dataset_id"]), None)
    if official is None:
        manifest = repository_root() / "manifests/datasets.csv"
        with manifest.open(newline="", encoding="utf-8") as stream:
            manifest_record = next(
                (
                    row for row in csv.DictReader(stream)
                    if row.get("dataset_id") == source["dataset_id"]
                    and row.get("status") == "PASS"
                ),
                None,
            )
        if manifest_record is None:
            raise DomainError("DEM_SOURCE_UNREGISTERED", 503)
        official = {"url": manifest_record["source_url"]}
    stat = path.stat()
    digest = checked_digest(str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if (receipt_record.get("status") not in {"VERIFIED_BYTES", "PASS"}
            or receipt_record.get("url") != official["url"] or receipt_record.get("frame") != "MOON_ME/DE421"
            or receipt_record.get("unit") != "m" or receipt_record.get("bytes") != stat.st_size
            or receipt_record.get("sha256") != digest):
        raise DomainError("DEM_INTEGRITY_FAILED", 503)
    return {**source, "sha256": digest, "bytes": stat.st_size, "url": official["url"],
            "frame": receipt_record["frame"], "unit": "m"}


def installed_sources():
    result = []
    for source in terrain_sources():
        primary = Path(source["path"])
        alternative = repository_root() / "data/raw/nasa" / primary.name
        candidate = {**source, "path": primary if primary.is_file() else alternative}
        checked = verified_source(candidate)
        if checked:
            result.append(checked)
    return result


class TerrainInputs:
    def __init__(self, request):
        self.request = request
        self.stack = ExitStack()

    def __enter__(self):
        try:
            self.sources = installed_sources()
            if not self.sources:
                raise DomainError("DEM_NOT_INSTALLED", 503)
            self.layers = []
            for source in self.sources:
                dem = self.stack.enter_context(DEM(source["path"], source["dataset_id"]))
                if (not np.allclose(dem.ds.res, source["resolution_m"], rtol=0, atol=1e-5)
                        or dem.meta()["pixel_registration"] not in {"Area", "Point"}):
                    raise DomainError("DEM_GEOMETRY_INVALID", 503)
                self.layers.append((source, dem))
            self.layers.sort(key=lambda item: item[0]["resolution_m"])
            lon, lat = self.request.longitude_e_deg, self.request.latitude_deg
            for source, dem in self.layers:
                if source["resolution_m"] == 5:
                    x, y = dem.fwd.transform(lon, lat)
                    bb = dem.ds.bounds
                    if min(x-bb.left, bb.right-x, y-bb.bottom, bb.top-y) <= 275:
                        continue  # Prefer a regional DEM rather than an unbracketed fine seam.
                elevation = float(dem.lonlat_at(lon, lat))
                if np.isfinite(elevation):
                    self.observer_source = source
                    self.observer_dem = dem
                    self.site = {"site_id": "coordinate", "lon_e_deg": lon, "lat_deg": lat,
                                 "dem_z_m": elevation, "dem_sha256": source["sha256"]}
                    self.layers = [(s, d) for s, d in self.layers
                                   if s["resolution_m"] >= source["resolution_m"]
                                   and (s["resolution_m"] != 5 or s["dataset_id"] == source["dataset_id"])]
                    break
            else:
                raise DomainError("OUTSIDE_DEM_COVERAGE", 422)
            return self
        except Exception:
            self.stack.close()
            raise

    def __exit__(self, *args):
        self.stack.close()

    def sample(self, longitude, latitude, minimum_resolution_m=0):
        """Fine-to-coarse lookup, preserving nodata; provenance records actual sources."""
        out = np.full(np.broadcast_shapes(np.shape(longitude), np.shape(latitude)), np.nan)
        source_index = np.full(out.shape, -1, dtype=np.int8)
        for index, (source, dem) in enumerate(self.layers):
            if source["resolution_m"] < minimum_resolution_m:
                continue
            missing = ~np.isfinite(out)
            if not missing.any():
                break
            value = dem.lonlat_at(np.broadcast_to(longitude, out.shape)[missing],
                                  np.broadcast_to(latitude, out.shape)[missing])
            out[missing] = value
            source_index[missing] = np.where(np.isfinite(value), index, -1)
        return out, source_index

    def provenance(self):
        return [{key: source[key] for key in ("dataset_id", "sha256", "bytes", "url", "frame", "unit", "resolution_m")}
                for source, _ in self.layers]
