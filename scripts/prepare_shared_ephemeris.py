#!/usr/bin/env python3
"""Install official NAIF kernels and optionally warm monthly vector tables.

Run with PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_shared_ephemeris.py
No external reference repository's derived tables are imported.
"""
import argparse
import json
from pathlib import Path
import tempfile

import pandas as pd
import requests
from filelock import FileLock

from app.services.lunarsight.shared_ephemeris import SharedEphemeris, KERNELS, NAIF
from app.services.lunarsight.acquire import hashfile, utc_now


def prepare(root=None, start=None, end=None):
    provider = SharedEphemeris(root)
    directory = provider.root / "kernels"
    directory.mkdir(parents=True, exist_ok=True)
    with FileLock(str(directory / "install.lock")):
        for relative in KERNELS:
            path = directory / Path(relative).name
            if path.exists():
                continue  # identity() below rejects missing/mismatched receipts.
            url = NAIF+relative
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                if response.url != url:
                    raise ValueError("Unexpected kernel download redirect")
                with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        for block in response.iter_content(1024*1024):
                            output.write(block)
                        output.close()
                        if temporary.stat().st_size == 0:
                            raise ValueError("Empty kernel")
                        record = {"url": url, "bytes": temporary.stat().st_size,
                                  "sha256": hashfile(temporary), "accessed_utc": utc_now()}
                        path.with_suffix(path.suffix+".receipt.json").write_text(json.dumps(record, indent=2)+"\n")
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
    identity = provider.identity()
    tables = []
    if start and end:
        a, b = pd.Timestamp(start), pd.Timestamp(end)
        if a.tzinfo is None or b.tzinfo is None or b < a:
            raise ValueError("Supply an ordered UTC range")
        for month in pd.date_range(a.tz_convert("UTC").strftime("%Y-%m-01"),
                                   b.tz_convert("UTC").strftime("%Y-%m-01"), freq="MS"):
            tables.append(provider.chunk(month.strftime("%Y-%m-01"), identity)[1])
    return {"identity": identity, "warmed_tables": tables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be supplied together")
    print(json.dumps(prepare(args.root, args.start, args.end), indent=2))
