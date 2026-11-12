"""Compact deployable metrics-only products, rebuilt from verified native chunks."""
from pathlib import Path
import json
import os
import tempfile

import pandas as pd
from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest
from app.services.lunarsight.acquire import hashfile
from . import metric_index

VERSION = "prepared-metrics-1"


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class PreparedMetrics:
    def __init__(self, root):
        self.root = Path(root)/"prepared-metrics"

    def query(self, identity, start, end):
        for receipt in sorted((self.root/digest(identity)).glob("*/receipt.json")):
            try:
                record = json.loads(receipt.read_text())
                if record["identity"] != identity:
                    raise ValueError("Prepared metrics identity mismatch")
                if record.get("version") != VERSION:
                    continue
                if not pd.Timestamp(record["start_utc"]) <= pd.Timestamp(start) < pd.Timestamp(end) <= pd.Timestamp(record["end_utc"]):
                    continue
                directory, reference = receipt.parent, record["metrics_index"]
                # Short queries can use a checked yearly part rather than
                # decompressing the entire century's hourly prefix arrays.
                for chunk in record.get("chunks", []):
                    if not chunk.get("start_utc") or not chunk.get("end_utc"):
                        continue
                    if pd.Timestamp(chunk["start_utc"]) <= pd.Timestamp(start) < pd.Timestamp(end) <= pd.Timestamp(chunk["end_utc"]):
                        coverage = {key: chunk[key] for key in ("start_utc", "end_utc")}
                        part = receipt.parent.parent/".parts"/digest(coverage)/"receipt.json"
                        if part.is_file():
                            if hashfile(part) != chunk["receipt_sha256"]:
                                raise ValueError("Prepared metric part receipt checksum mismatch")
                            detail = json.loads(part.read_text())
                            if detail["identity_sha256"] != digest(identity) or detail["metrics_index"]["sha256"] != chunk["index_sha256"]:
                                raise ValueError("Prepared metric part source mismatch")
                            directory, reference = part.parent, detail["metrics_index"]
                        break
                result = metric_index.query(directory, reference, start, end)
                if result is not None:
                    result.update(physical_series_cache_hit=False, source={"kind": "prepared_metrics_only",
                        "identity_sha256": digest(identity), "source_sha256": record["source_sha256"],
                        "index_sha256": reference["sha256"],
                        "prepared_start_utc": record["start_utc"], "prepared_end_utc": record["end_utc"]})
                    return result
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise DomainError("PREPARED_METRICS_INTEGRITY_FAILED", 503) from error
        return None

    def publish(self, identity, start, end, content, full_metrics, chunks):
        from .pipeline import atomic_json
        coverage = {"start_utc": pd.Timestamp(start).isoformat(), "end_utc": pd.Timestamp(end).isoformat()}
        directory = self.root/digest(identity)/digest(coverage)
        directory.mkdir(parents=True, exist_ok=True)
        source = digest({"identity": identity, "coverage": coverage, "chunks": chunks})
        with FileLock(str(directory/"publish.lock")):
            atomic_bytes(directory/"metrics.npz", content)
            atomic_json(directory/"receipt.json", {"version": VERSION, "identity": identity, **coverage,
                "source_sha256": source, "chunks": chunks,
                "metrics_index": {"version": metric_index.VERSION, "sha256": hashfile(directory/"metrics.npz"),
                    "source_sha256": source, "full_metrics": full_metrics},
                "scope": "Nominal five-minute physical metrics and aggregated charts; requirements and validation are not preapproved."})
        return directory
