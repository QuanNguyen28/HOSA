#!/usr/bin/env python3
"""Create a reproducible source archive from a clean, committed Git revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout.strip() if text else result.stdout


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="committed Git ref to archive")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("release-packages"),
        help="destination directory (default: release-packages)",
    )
    args = parser.parse_args()

    status = git("status", "--porcelain")
    if status:
        raise SystemExit(
            "Refusing to package a dirty worktree. Commit the release candidate, "
            "rerun make release-check, then package that exact commit."
        )

    commit = str(git("rev-parse", f"{args.ref}^{{commit}}"))
    short = commit[:12]
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = f"HOSA-{short}"
    archive = output_dir / f"{stem}.zip"
    manifest = output_dir / f"{stem}.manifest.json"
    checksum = output_dir / f"{stem}.zip.sha256"

    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--prefix={stem}/",
            f"--output={archive}",
            commit,
        ],
        cwd=ROOT,
        check=True,
    )
    archive_sha = sha256(archive)
    checksum.write_text(f"{archive_sha}  {archive.name}\n", encoding="utf-8")

    payload = {
        "schema_version": "lunarsight-source-package-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_ref_requested": args.ref,
        "git_commit": commit,
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_sha,
        "scope": "tracked files at the committed Git revision",
        "excluded_by_design": [
            "untracked files",
            "ignored raw NASA rasters",
            "virtual environments",
            "node_modules",
            "build output",
            "credentials and local environment files",
        ],
        "required_companion": (
            "NASA raw-data release/receipts referenced by README and manifests"
        ),
    }
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

