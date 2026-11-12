#!/usr/bin/env python3
"""Acquire the official global LOLA LDEM_64 PDS image with provenance."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
TRACKED_RECEIPTS = ROOT / "manifests/lunarsight/full_product_receipts"
BASE = "https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/JP2"
EXPECTED_BYTES = 211_190_204
FILES = {
    "LDEM_64.JP2": EXPECTED_BYTES,
    "LDEM_64_JP2.LBL": None,
    "LDEM_64_AUX.XML": None,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def acquire(filename: str, expected_bytes: int | None, destination: Path) -> dict:
    url = f"{BASE}/{filename}"
    receipt_path = destination.with_name(destination.name + ".receipt.json")
    if destination.is_file() and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("url") == url
            and receipt.get("bytes") == destination.stat().st_size
            and receipt.get("sha256") == sha256(destination)
        ):
            if filename.endswith(".JP2"):
                TRACKED_RECEIPTS.mkdir(parents=True, exist_ok=True)
                atomic_json(TRACKED_RECEIPTS / "global_ldem64.receipt.json", receipt)
            return receipt
        raise ValueError(f"Existing global DEM cache failed verification: {destination}")

    partial = destination.with_suffix(destination.suffix + ".part")
    if shutil.disk_usage(destination.parent).free < (expected_bytes or 1_000_000) + 1_000_000_000:
        raise OSError("Insufficient free disk for global LOLA DEM acquisition")
    current = requests.Session()
    current.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=4,
                backoff_factor=1,
                status_forcelist=(429, 500, 502, 503, 504),
            )
        ),
    )
    digest = hashlib.sha256()
    total = 0
    try:
        if expected_bytes is not None and expected_bytes > 100_000_000:
            with current.head(url, timeout=(20, 60)) as head:
                head.raise_for_status()
                source_etag = head.headers.get("ETag")
                source_modified = head.headers.get("Last-Modified")
                if int(head.headers.get("Content-Length", 0)) != expected_bytes:
                    raise ValueError("NASA source byte count changed")
                if not source_etag or head.headers.get("Accept-Ranges") != "bytes":
                    raise ValueError("NASA source does not expose stable byte ranges")
            range_directory = destination.with_name(destination.name + ".ranges")
            range_directory.mkdir(exist_ok=True)
            chunk_size = 4 * 1024 * 1024
            ranges = [
                (index, start, min(expected_bytes - 1, start + chunk_size - 1))
                for index, start in enumerate(range(0, expected_bytes, chunk_size))
            ]

            def fetch_range(item: tuple[int, int, int]) -> Path:
                index, start, stop = item
                part = range_directory / f"{index:05d}.part"
                expected = stop - start + 1
                if part.is_file() and part.stat().st_size == expected:
                    return part
                with requests.get(
                    url,
                    timeout=(20, 120),
                    headers={
                        "Accept-Encoding": "identity",
                        "Range": f"bytes={start}-{stop}",
                    },
                ) as response:
                    response.raise_for_status()
                    if response.status_code != 206:
                        raise ValueError("Expected HTTP 206 for ranged NASA transfer")
                    if response.headers.get("ETag") != source_etag:
                        raise ValueError("NASA asset identity changed during transfer")
                    expected_range = f"bytes {start}-{stop}/{expected_bytes}"
                    if response.headers.get("Content-Range") != expected_range:
                        raise ValueError("Unexpected NASA Content-Range")
                    body = response.content
                if len(body) != expected:
                    raise ValueError("Truncated NASA byte range")
                part.write_bytes(body)
                return part

            completed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(fetch_range, item) for item in ranges]
                for future in concurrent.futures.as_completed(futures):
                    future.result()
                    completed += 1
                    if completed % 8 == 0 or completed == len(ranges):
                        print(f"LDEM_64.JP2 ranges {completed}/{len(ranges)}", flush=True)
            with partial.open("wb") as output:
                for index, start, stop in ranges:
                    part = range_directory / f"{index:05d}.part"
                    with part.open("rb") as source:
                        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                            output.write(chunk)
                            digest.update(chunk)
                            total += len(chunk)
            shutil.rmtree(range_directory)
        else:
            with current.get(
                url,
                stream=True,
                timeout=(20, 180),
                headers={"Accept-Encoding": "identity"},
            ) as response:
                response.raise_for_status()
                if response.url != url or not response.url.startswith("https://imbrium.mit.edu/"):
                    raise ValueError("Unexpected redirect while acquiring NASA LOLA data")
                content_length = response.headers.get("Content-Length")
                if expected_bytes is not None and content_length and int(content_length) != expected_bytes:
                    raise ValueError("NASA source byte count changed")
                with partial.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        digest.update(chunk)
                        total += len(chunk)
        if total == 0 or (expected_bytes is not None and total != expected_bytes):
            raise ValueError(f"Truncated global DEM transfer: {total} bytes")
        if filename.endswith(".LBL"):
            label = partial.read_text(encoding="ascii")
            required = (
                'DATA_SET_ID               = "LRO-L-LOLA-4-GDR-V1.0"',
                'COORDINATE_SYSTEM_NAME       = "MEAN EARTH/POLAR AXIS OF DE421"',
                "MAP_RESOLUTION               = 64 <pix/deg>",
            )
            if not all(value in label for value in required):
                raise ValueError("Unexpected PDS label contents")
        partial.replace(destination)
        receipt = {
            "id": "global_ldem64" if filename.endswith(".JP2") else f"global_ldem64_{filename.rsplit('.', 1)[-1].lower()}",
            "status": "VERIFIED_BYTES",
            "url": url,
            "source_page": "https://pds-geosciences.wustl.edu/missions/lro/lola.htm",
            "filename": filename,
            "bytes": total,
            "sha256": digest.hexdigest(),
            "accessed_utc": datetime.now(timezone.utc).isoformat(),
            "http_identity": {
                "etag": source_etag if expected_bytes is not None and expected_bytes > 100_000_000 else None,
                "last_modified": source_modified if expected_bytes is not None and expected_bytes > 100_000_000 else None,
            },
            "frame": "MOON_ME/DE421",
            "reference_radius_m": 1_737_400,
            "native_resolution": "64 pixels/degree; 473.802 m/pixel at equator",
        }
        atomic_json(receipt_path, receipt)
        if filename.endswith(".JP2"):
            TRACKED_RECEIPTS.mkdir(parents=True, exist_ok=True)
            atomic_json(TRACKED_RECEIPTS / "global_ldem64.receipt.json", receipt)
        return receipt
    finally:
        partial.unlink(missing_ok=True)
        current.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "data/raw/global/lola_ldem64",
    )
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for filename, expected_bytes in FILES.items():
        receipt = acquire(filename, expected_bytes, args.output_directory / filename)
        print(filename, receipt["bytes"], receipt["sha256"], flush=True)


if __name__ == "__main__":
    main()
