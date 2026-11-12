"""Atomic content-addressed blobs shared by offline builds and runtime readers."""
from pathlib import Path
import hashlib
import json
import os
import tempfile

from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest

VERSION = "site-precompute-1.0"


def package_root():
    configured = os.environ.get("HOSA_PRECOMPUTE_ROOT")
    return Path(configured) if configured else Path(__file__).resolve().parents[3]/"data/processed/site-precompute/v1"


def coordinate_key(latitude, longitude):
    return digest({"latitude_deg": float(latitude), "longitude_e_deg": float(longitude) % 360})


def mesh_key(latitude, longitude, radius, samples, detail):
    return digest({"coordinate": coordinate_key(latitude, longitude), "radius_km": float(radius),
                   "samples": int(samples), "detail": detail})


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".artifact-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


class Store:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else package_root()

    def manifest(self):
        path = self.root/"manifest.json"
        if not path.is_file():
            return {"schema_version": VERSION, "sites": {}, "meshes": {}}
        try:
            record = json.loads(path.read_bytes())
            if record["schema_version"] != VERSION:
                raise ValueError("Unsupported precompute schema")
            if not isinstance(record["sites"], dict) or not isinstance(record["meshes"], dict):
                raise ValueError("Invalid precompute index")
            return record
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise DomainError("PRECOMPUTE_MANIFEST_INVALID", 503) from error

    def descriptor(self):
        record = self.manifest()
        return {"schema_version": VERSION, "manifest_hash": digest(record),
                "sites": len(record["sites"]), "meshes": len(record["meshes"])}

    def put(self, content, suffix):
        sha = hashlib.sha256(content).hexdigest()
        name = f"blobs/{sha}.{suffix}"
        path = self.root/name
        if not path.is_file():
            atomic_bytes(path, content)
        return {"file": name, "sha256": sha, "bytes": len(content)}

    def read(self, reference):
        try:
            sha = reference["sha256"]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("Invalid checksum")
            name = reference["file"]
            if name not in {f"blobs/{sha}.npz", f"blobs/{sha}.json.gz"}:
                raise ValueError("Invalid artifact path")
            content = (self.root/name).read_bytes()
            if len(content) != reference["bytes"] or hashlib.sha256(content).hexdigest() != sha:
                raise ValueError("Artifact checksum mismatch")
            return content
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise DomainError("PRECOMPUTE_INTEGRITY_FAILED", 503) from error

    def publish(self, site_key, record, meshes=None):
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.root/"publish.lock")):
            manifest = self.manifest()
            manifest["sites"][site_key] = record
            manifest["meshes"].update(meshes or {})
            atomic_bytes(self.root/"manifest.json", json_bytes(manifest))

    def publish_meshes(self, meshes):
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.root/"publish.lock")):
            manifest = self.manifest()
            manifest["meshes"].update(meshes)
            atomic_bytes(self.root/"manifest.json", json_bytes(manifest))
