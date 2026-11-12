#!/usr/bin/env python3
"""Audit a HOSA release candidate without mutating scientific products."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.2.0"
SCENARIO_ID = "south_pole_demo_v1"
SITES = ("Site01", "Site04")


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []

    def check(self, check_id: str, ok: bool, detail: str) -> None:
        self.checks.append(
            {"id": check_id, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    def file(self, relative: str) -> Path:
        path = ROOT / relative
        exists = path.is_file()
        self.check(f"file:{relative}", exists, "present" if exists else "missing")
        if exists:
            self.artifacts.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
        return path


def audit_csv(audit: Audit, site: str, kind: str, expected_rows: int) -> None:
    relative = f"data/processed/lunarsight/{VERSION}/visibility/{site}_{kind}.csv"
    path = audit.file(relative)
    if not path.is_file():
        return

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    audit.check(
        f"rows:{site}_{kind}",
        len(rows) == expected_rows,
        f"expected {expected_rows}; found {len(rows)}",
    )
    if not rows:
        return

    expected_site_id = f"{site}_P1"
    audit.check(
        f"identity:{site}_{kind}",
        all(
            row.get("site_id") == expected_site_id
            and row.get("scenario_status") == "PROVISIONAL"
            for row in rows
        ),
        f"site={expected_site_id}; scenario_status=PROVISIONAL",
    )

    if kind == "intervals":
        valid = True
        previous_end: datetime | None = None
        for row in rows:
            start, end = utc(row["start_utc"]), utc(row["end_utc"])
            if end - start != timedelta(minutes=5) or (
                previous_end is not None and start != previous_end
            ):
                valid = False
                break
            previous_end = end
        audit.check(
            f"grid:{site}_{kind}",
            valid,
            "continuous half-open 5-minute intervals",
        )
    else:
        valid = True
        first_start = utc(rows[0]["start_utc"])
        for index, row in enumerate(rows):
            start, end = utc(row["start_utc"]), utc(row["end_utc"])
            if (
                int(row["start_index"]) != index
                or start != first_start + timedelta(minutes=15 * index)
                or end - start != timedelta(hours=72)
            ):
                valid = False
                break
        audit.check(
            f"grid:{site}_{kind}",
            valid,
            "indices 0..1343; exact 15-minute starts; fixed 72-hour windows",
        )


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
        ).stdout.strip()

    try:
        status = run("status", "--porcelain")
        return {
            "commit": run("rev-parse", "HEAD"),
            "branch": run("branch", "--show-current"),
            "dirty": bool(status),
            "changed_path_count": len(status.splitlines()) if status else 0,
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"error": str(exc)}


def run_audit() -> dict[str, Any]:
    audit = Audit()
    scenario_path = audit.file("manifests/lunarsight/config/scenario.json")
    geometry_path = audit.file("manifests/lunarsight/config/geometry_config.json")
    source_path = audit.file("manifests/lunarsight/source_manifest.json")

    if scenario_path.is_file():
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        expected = {
            "scenario_id": SCENARIO_ID,
            "status": "PROVISIONAL",
            "D_hours": 72,
            "model_step_minutes": 5,
            "start_step_minutes": 15,
            "site_ids": ["Site01_P1", "Site04_P1"],
        }
        audit.check(
            "scenario:locked_fields",
            all(scenario.get(key) == value for key, value in expected.items()),
            json.dumps(expected, ensure_ascii=False, sort_keys=True),
        )
        audit.check(
            "scenario:domain",
            utc(scenario["B_utc"]) - utc(scenario["A_utc"]) == timedelta(days=14)
            and utc(scenario["end_utc"]) - utc(scenario["B_utc"]) == timedelta(hours=72),
            "14-day start domain plus 72-hour tail",
        )

    if geometry_path.is_file():
        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
        expected_geometry = {
            "panel_height_m": 1,
            "antenna_height_m": 2,
            "tol_horizon_deg": 0.1,
            "tol_event_minutes": 5,
            "tol_duration_minutes": 10,
        }
        audit.check(
            "geometry:locked_fields",
            all(geometry.get(key) == value for key, value in expected_geometry.items()),
            json.dumps(expected_geometry, sort_keys=True),
        )

    if source_path.is_file():
        source = json.loads(source_path.read_text(encoding="utf-8"))
        records = source.get("records", [])
        allowed = {"PASS", "VERIFIED_BYTES"}
        audit.check(
            "provenance:records",
            bool(records) and all(record.get("status") in allowed for record in records),
            f"{len(records)} records; allowed statuses {sorted(allowed)}",
        )

    for site in SITES:
        audit_csv(audit, site, "intervals", 4896)
        audit_csv(audit, site, "windows", 1344)

    sensitivity = audit.file(
        f"docs/validation/lunarsight/{VERSION}/reports/sensitivity.json"
    )
    site04_sensitivity = audit.file(
        f"docs/validation/lunarsight/{VERSION}/reports/Site04_sensitivity.json"
    )
    if sensitivity.is_file():
        payload = json.loads(sensitivity.read_text(encoding="utf-8"))
        audit.check(
            "sensitivity:Site01",
            payload.get("time_5min_vs_1min", {}).get("decision_5min")
            == payload.get("time_5min_vs_1min", {}).get("decision_1min"),
            "5-minute and 1-minute decisions agree",
        )
    if site04_sensitivity.is_file():
        payload = json.loads(site04_sensitivity.read_text(encoding="utf-8"))
        audit.check(
            "sensitivity:Site04",
            payload.get("gate") == "PASS"
            and payload.get("time_5min_vs_1min", {}).get("decision_5min")
            == payload.get("time_5min_vs_1min", {}).get("decision_1min"),
            "independent 1-minute gate PASS and decisions agree",
        )

    required_files = (
        "data/processed/lunarsight/v0.2.0/site_catalog.geojson",
        "frontend/public/assets/nasa/lroc_color_2k.jpg",
        "frontend/public/assets/nasa/ldem_3_8bit.jpg",
        "docs/validation/lunarsight/v0.2.0/reports/scientific_validation.md",
        "docs/validation/lunarsight/v0.2.0/reports/application_acceptance.md",
        "docs/demo/lunarsight-demo-script.md",
        "docs/approvals/g0-signoff.md",
        "docs/submission/project-description-en.md",
        "docs/submission/2026-official-requirements.md",
        "docs/submission/media-shot-list.md",
        "docs/handover/release-handover.md",
        "docs/validation/lunarsight/v0.2.0/user_test_results.md",
    )
    for relative in required_files:
        audit.file(relative)

    failures = [item for item in audit.checks if item["status"] == "FAIL"]
    return {
        "schema_version": "lunarsight-release-audit-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "release": {"dataset_version": VERSION, "scenario_id": SCENARIO_ID},
        "technical_status": "PASS" if not failures else "FAIL",
        "external_gates": [
            {
                "id": "G0_APPROVAL",
                "status": "PENDING",
                "evidence": "docs/approvals/g0-signoff.md",
            },
            {
                "id": "OPEN_SOURCE_LICENSE",
                "status": "PENDING",
                "evidence": "docs/submission/2026-official-requirements.md",
            },
            {
                "id": "USER_TEST_3_TO_5",
                "status": "NOT_RUN",
                "evidence": (
                    "docs/validation/lunarsight/v0.2.0/user_test_results.md"
                ),
            },
            {
                "id": "EVENT_SUBMISSION",
                "status": "PENDING",
                "evidence": "docs/release-checklist.md",
            },
        ],
        "git": git_state(),
        "summary": {
            "checks": len(audit.checks),
            "passed": len(audit.checks) - len(failures),
            "failed": len(failures),
        },
        "checks": audit.checks,
        "artifacts": audit.artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    args = parser.parse_args()
    report = run_audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = args.output if args.output.is_absolute() else ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

