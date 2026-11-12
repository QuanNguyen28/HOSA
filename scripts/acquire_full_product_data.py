#!/usr/bin/env python3
"""Acquire the official raw inputs needed by the complete HOSA product.

The script is intentionally conservative: it never overwrites raw data, rejects
HTML error pages, verifies expected byte counts, writes SHA-256 receipts and
leaves multi-gigabyte COGs remote for windowed extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "manifests/lunarsight/full_product_sources.json"
TRACKED_RECEIPTS = ROOT / "manifests/lunarsight/full_product_receipts"
ALLOWED_HOSTS = {
    # LOLA Science Team archive referenced by the NASA PDS LOLA data page.
    "imbrium.mit.edu",
    "naif.jpl.nasa.gov",
    "pgda.gsfc.nasa.gov",
    "pds-geosciences.wustl.edu",
    "svs.gsfc.nasa.gov",
    "pds.lroc.im-ldi.com",
    "trek.nasa.gov",
}
TIFF_MAGIC = {b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"}
GLB_MAGIC = b"glTF"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("Manifest must contain a non-empty datasets list")
    seen: set[str] = set()
    for item in datasets:
        missing = {"id", "url", "destination", "profile", "access_mode"} - item.keys()
        if missing:
            raise ValueError(f"Dataset is missing fields {sorted(missing)}: {item}")
        if item["id"] in seen:
            raise ValueError(f"Duplicate dataset id: {item['id']}")
        seen.add(item["id"])
        url = urlparse(item["url"])
        if url.scheme != "https" or url.hostname not in ALLOWED_HOSTS:
            raise ValueError(f"Source is not an approved official host: {item['url']}")
        destination = (ROOT / item["destination"]).resolve()
        if ROOT not in destination.parents:
            raise ValueError(f"Destination escapes repository: {destination}")
    return manifest


def selected_datasets(
    manifest: dict[str, Any], profiles: set[str], only: set[str]
) -> list[dict[str, Any]]:
    datasets = manifest["datasets"]
    if only:
        unknown = only - {item["id"] for item in datasets}
        if unknown:
            raise ValueError(f"Unknown dataset ids: {', '.join(sorted(unknown))}")
        return [item for item in datasets if item["id"] in only]
    return [item for item in datasets if item["profile"] in profiles]


def validate_payload(path: Path, item: dict[str, Any]) -> None:
    with path.open("rb") as stream:
        prefix = stream.read(512)
    lowered = prefix.lstrip().lower()
    if lowered.startswith((b"<!doctype html", b"<html")):
        raise ValueError(f"HTML error payload received for {item['id']}")
    media_type = item.get("media_type", "")
    if media_type == "image/tiff" and prefix[:4] not in TIFF_MAGIC:
        raise ValueError(f"Invalid TIFF signature for {item['id']}")
    if media_type == "model/gltf-binary" and prefix[:4] != GLB_MAGIC:
        raise ValueError(f"Invalid GLB signature for {item['id']}")
    if media_type in {"text/plain", "application/xml"} and b"\x00" in prefix:
        raise ValueError(f"Unexpected binary content for {item['id']}")
    if media_type == "application/json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON payload for {item['id']}") from exc
        if isinstance(payload, dict) and payload.get("error"):
            raise ValueError(f"Upstream API error for {item['id']}: {payload['error']}")


def receipt_paths(destination: Path, dataset_id: str) -> tuple[Path, Path]:
    adjacent = destination.with_name(destination.name + ".receipt.json")
    tracked = TRACKED_RECEIPTS / f"{dataset_id}.receipt.json"
    return adjacent, tracked


def existing_receipt(destination: Path, dataset_id: str) -> dict[str, Any] | None:
    for candidate in receipt_paths(destination, dataset_id):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def verify_existing(item: dict[str, Any], destination: Path) -> dict[str, Any]:
    validate_payload(destination, item)
    expected = item.get("expected_bytes")
    if expected is not None and destination.stat().st_size != expected:
        raise ValueError(
            f"Byte-count mismatch for {item['id']}: "
            f"expected {expected}, got {destination.stat().st_size}"
        )
    digest = sha256(destination)
    receipt = existing_receipt(destination, item["id"])
    if receipt is not None:
        receipt_digest = receipt.get("sha256")
        if receipt_digest and receipt_digest != digest:
            raise ValueError(f"Receipt checksum mismatch for {item['id']}")
        receipt_url = receipt.get("url") or receipt.get("final_url")
        if receipt_url and receipt_url != item["url"]:
            raise ValueError(f"Receipt URL mismatch for {item['id']}")
    return {
        **item,
        "bytes": destination.stat().st_size,
        "sha256": digest,
        "verified_utc": utc_now(),
        "status": "VERIFIED_EXISTING",
    }


def session() -> requests.Session:
    current = requests.Session()
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        respect_retry_after_header=True,
    )
    current.mount("https://", HTTPAdapter(max_retries=retry))
    current.headers.update(
        {
            "User-Agent": "HOSA/0.4 official-data-acquisition (NASA Space Apps project)",
            "Accept-Encoding": "identity",
        }
    )
    return current


def download(item: dict[str, Any], current: requests.Session) -> dict[str, Any]:
    destination = ROOT / item["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return verify_existing(item, destination)

    expected = item.get("expected_bytes")
    reserve = (expected or 100 * 1024 * 1024) + 256 * 1024 * 1024
    if shutil.disk_usage(destination.parent).free < reserve:
        raise OSError(f"Insufficient free disk space for {item['id']}")

    partial = destination.with_name(destination.name + ".part")
    partial.unlink(missing_ok=True)
    digest = hashlib.sha256()
    total = 0
    response_headers: dict[str, str | None] = {}
    try:
        with current.get(item["url"], stream=True, timeout=(20, 180)) as response:
            response.raise_for_status()
            final = urlparse(response.url)
            if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
                raise ValueError(f"Unexpected redirect host for {item['id']}: {response.url}")
            content_length = response.headers.get("Content-Length")
            if content_length and expected is not None and int(content_length) != expected:
                raise ValueError(
                    f"Server byte count changed for {item['id']}: "
                    f"expected {expected}, server reports {content_length}"
                )
            with partial.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if expected is not None and total > expected:
                        raise ValueError(f"Payload exceeds expected size for {item['id']}")
                    stream.write(chunk)
                    digest.update(chunk)
            response_headers = {
                key: response.headers.get(key)
                for key in ("Content-Length", "Content-Type", "ETag", "Last-Modified")
            }
            final_url = response.url
        if expected is not None and total != expected:
            raise ValueError(
                f"Truncated payload for {item['id']}: expected {expected}, got {total}"
            )
        validate_payload(partial, item)
        partial.replace(destination)
        receipt = {
            **item,
            "final_url": final_url,
            "bytes": total,
            "sha256": digest.hexdigest(),
            "retrieved_utc": utc_now(),
            "status": "VERIFIED_BYTES",
            "http_headers": response_headers,
        }
        adjacent, tracked = receipt_paths(destination, item["id"])
        atomic_json(adjacent, receipt)
        atomic_json(tracked, receipt)
        return receipt
    finally:
        partial.unlink(missing_ok=True)


def human_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def write_run_report(results: Iterable[dict[str, Any]], failures: list[dict[str, str]]) -> Path:
    report = {
        "run_utc": utc_now(),
        "results": list(results),
        "failures": failures,
    }
    path = ROOT / "data/raw/full_product/acquisition_report.json"
    atomic_json(path, report)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--profile",
        action="append",
        choices=("core", "extended", "on_demand"),
        help="Profile to acquire; may be repeated. Defaults to core.",
    )
    parser.add_argument("--only", action="append", default=[], help="Acquire one dataset id")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without downloading")
    parser.add_argument("--verify", action="store_true", help="Verify installed files only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest.resolve())
    profiles = set(args.profile or ["core"])
    items = selected_datasets(manifest, profiles, set(args.only))
    downloadable = [item for item in items if item["access_mode"] == "download"]
    remote = [item for item in items if item["access_mode"] != "download"]
    missing_bytes = sum(
        item.get("expected_bytes", 0)
        for item in downloadable
        if not (ROOT / item["destination"]).exists()
    )
    print(
        f"Selected {len(items)} datasets: {len(downloadable)} downloads, "
        f"{len(remote)} remote/on-demand; missing transfer {human_bytes(missing_bytes)}"
    )
    for item in remote:
        print(f"REMOTE {item['id']:<34} {item['access_mode']}")
    if args.dry_run:
        for item in downloadable:
            destination = ROOT / item["destination"]
            state = "installed" if destination.exists() else human_bytes(item.get("expected_bytes"))
            print(f"PLAN   {item['id']:<34} {state}")
        return 0

    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    current = session()
    for index, item in enumerate(downloadable, start=1):
        destination = ROOT / item["destination"]
        try:
            if args.verify:
                if not destination.exists():
                    raise FileNotFoundError(destination)
                receipt = verify_existing(item, destination)
            else:
                print(
                    f"[{index}/{len(downloadable)}] {item['id']} "
                    f"({human_bytes(item.get('expected_bytes'))})",
                    flush=True,
                )
                receipt = download(item, current)
            results.append(receipt)
            print(f"OK     {item['id']} {receipt['status']}", flush=True)
        except Exception as exc:  # keep the run report useful when one upstream is unavailable
            failures.append({"id": item["id"], "error": str(exc)})
            print(f"ERROR  {item['id']}: {exc}", file=sys.stderr, flush=True)
    report = write_run_report(results, failures)
    print(f"Run report: {report.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
