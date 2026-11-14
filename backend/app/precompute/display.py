"""Prebuilt or persistent display responses, separate from scientific horizons."""
import gzip
import json
import os
from pathlib import Path

from filelock import FileLock

from .store import Store, digest, mesh_key, json_bytes


def source_signature():
    from app.services.lunarsight.point import terrain_sources
    result = []
    for source in terrain_sources():
        path = source["path"]
        if not path.is_file():
            continue
        receipt = path.with_name(path.name+".receipt.json")
        stat = path.stat()
        result.append({"dataset_id": source["dataset_id"], "bytes": stat.st_size,
                       "mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns,
                       "receipt": receipt.read_text() if receipt.is_file() else None})
    return result


def cached_display(key, compute, *, method, package_key=None):
    package = Store()
    manifest = package.manifest()
    reference = manifest["meshes"].get(package_key or key)
    if reference and reference.get("display_method") == method:
        record = manifest["sites"].get(reference.get("coordinate_key"))
        from .geometry import compatible_sources
        if compatible_sources(record or reference):
            return package.read(reference), reference["sha256"], True
    root = Path(os.environ.get("HOSA_DISPLAY_CACHE_ROOT", Path(__file__).resolve().parents[3]/"data/cache/terrain-display"))
    runtime = Store(root)
    identity = digest({"request": key, "method": method, "sources": source_signature()})
    runtime.root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(runtime.root/f"{identity}.lock")):
        reference = runtime.manifest()["meshes"].get(identity)
        if reference:
            return runtime.read(reference), reference["sha256"], True
        payload = compute()
        # Missing source data must not become a permanently cached UNKNOWN.
        content = gzip.compress(json_bytes(payload), compresslevel=6, mtime=0)
        reference = runtime.put(content, "json.gz")
        if payload.get("coverage_status") == "COVERED":
            runtime.publish_meshes({identity: reference})
        return content, reference["sha256"], False


def mesh_response(latitude, longitude, radius, samples, detail):
    from app.services.lunarsight.point import _terrain_window_uncached, METHOD_VERSION, REGIONAL_COVERAGE_VERSION
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 360:
        raise ValueError("Invalid lunar coordinate")
    if not .5 <= radius <= 300 or samples not in {65, 129, 257, 401, 513} or detail not in {"best", "regional"}:
        raise ValueError("Invalid terrain window parameters")
    key = mesh_key(latitude, longitude, radius, samples, detail)
    # Regional windows changed source selection; best windows (and their
    # packaged meshes) keep the original method key.
    method = METHOD_VERSION if detail == "best" else f"{METHOD_VERSION}+{REGIONAL_COVERAGE_VERSION}"
    return cached_display(key, lambda: _terrain_window_uncached(latitude, longitude, radius, samples, detail), method=method)


def cap_response(samples):
    from app.services.lunarsight.point import _south_polar_cap_uncached, METHOD_VERSION
    if samples not in {257, 513}:
        raise ValueError("samples must be 257 or 513")
    return cached_display(f"polar_cap:{samples}", lambda: _south_polar_cap_uncached(samples), method=METHOD_VERSION)


def http_response(request, result):
    from fastapi import Response
    content, sha, hit = result
    encodings = {}
    for part in request.headers.get("accept-encoding", "").lower().split(","):
        name, *parameters = part.strip().split(";")
        quality = 1.
        for parameter in parameters:
            if parameter.strip().startswith("q="):
                try:
                    quality = float(parameter.strip()[2:])
                except ValueError:
                    quality = 0.
        encodings[name] = quality
    compressed = encodings.get("gzip", encodings.get("*", 0)) > 0
    etag = f'"{sha}-{"gzip" if compressed else "identity"}"'
    headers = {"Cache-Control": "public, max-age=300", "ETag": etag,
               "Vary": "Accept-Encoding", "X-Terrain-Cache": "HIT" if hit else "MISS"}
    candidates = {item.strip().removeprefix("W/") for item in request.headers.get("if-none-match", "").split(",")}
    if etag in candidates or "*" in candidates:
        return Response(status_code=304, headers=headers)
    if compressed:
        headers["Content-Encoding"] = "gzip"
    else:
        content = gzip.decompress(content)
    return Response(content=content, media_type="application/json", headers=headers)


def decode(content):
    return json.loads(gzip.decompress(content))
