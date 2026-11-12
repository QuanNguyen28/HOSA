#!/usr/bin/env python3
"""Exercise real ten-year progressive delivery; no full timeline download or LLM."""
import argparse
import json
from pathlib import Path
import time
from datetime import datetime, timezone

import httpx


def verify(base_url, job_id=None):
    request = {"site_id": "Site04_P1", "start_utc": "2026-11-24T00:00:00Z", "end_utc": "2036-11-24T00:00:00Z",
        "panel_height_m": 20., "antenna_height_m": 20., "min_sunlit_fraction": .8,
        "contact_requirements": {"min_contact_minutes": 30., "setup_minutes": 5., "required_windows": 1, "first_contact_deadline_minutes": 120.},
        "constraints": {"max_darkness_hours": 12., "max_earth_blackout_hours": 6.}, "resolve_indeterminate": True}
    started = time.perf_counter()
    report = {"passed": False, "live_llm_calls": 0, "created_utc": datetime.now(timezone.utc).isoformat(),
        "monitoring_existing_job": job_id is not None, "stages": []}
    with httpx.Client(base_url=base_url, timeout=120) as client:
        if job_id is None:
            response = client.post("/api/lunar/point/analyses", json=request)
            response.raise_for_status()
            job_id = response.json()["job_id"]
        report["job_id"] = job_id
        base = f"/api/lunar/point/analyses/{job_id}"
        previous, preview = None, None
        while time.perf_counter()-started < 1200:
            response = client.get(base)
            response.raise_for_status()
            state = response.json()
            if state["stage"] != previous:
                item = {"stage": state["stage"], "seconds_since_monitor_started": time.perf_counter()-started}
                report["stages"].append(item)
                print(json.dumps(item), flush=True)
                previous = state["stage"]
            if state.get("preview_url") and preview is None:
                response = client.get(base+"/preview")
                response.raise_for_status()
                preview = response.json()
                assert preview["evaluation_status"] == "pending" and preview["decision"] is None
                assert not preview["validation"]["passed"] and not preview["constraint_checks"]
                assert len(preview["timeline"]) <= 800
                report["preview"] = {"observed_while_running": state["status"] == "running", "bytes": len(response.content),
                    "evaluation_status": preview["evaluation_status"], "metrics_hours": preview["metrics_hours"], "joint_hours": preview["joint_hours"],
                    "seconds_since_monitor_started": time.perf_counter()-started}
            if state["status"] == "failed":
                raise AssertionError(state)
            if state["status"] == "succeeded":
                break
            time.sleep(1)
        else:
            raise AssertionError("Job did not finish within the acceptance wait window")
        response = client.get(base+"/result", params={"view": "display"})
        response.raise_for_status()
        result = response.json()
        assert result["evaluation_status"] == "complete"
        assert result["request"]["duration_hours"] == 87672
        assert result["timeline_transport"]["source_intervals"] == 1052064
        assert len(result["timeline"]) <= 800 and len(response.content) < 3_000_000
        hours = result["request"]["duration_hours"]
        integrated = {body: [0., 0.] for body in ("sun", "earth", "joint")}
        for row in result["timeline"]:
            dt = (datetime.fromisoformat(row["end_utc"])-datetime.fromisoformat(row["start_utc"])).total_seconds()/3600
            for body in integrated:
                for k, bound in enumerate(("lower", "upper")):
                    integrated[body][k] += row[f"{body}_visible_fraction_{bound}"]*dt
        for body, pair in integrated.items():
            expected = result["joint_hours"] if body == "joint" else result["metrics_hours"]["total_sun_hours" if body == "sun" else "total_earth_los_hours"]
            assert max(abs(a-b) for a, b in zip(pair, expected)) < 1e-7
        instants = []
        for at in ("2026-11-24T00:00:00Z", "2031-11-24T00:02:00Z", "2036-11-23T23:59:59Z"):
            response_at = client.get(base+"/interval", params={"at_utc": at})
            response_at.raise_for_status()
            row = response_at.json()
            assert not row.get("aggregated", False)
            stamp = datetime.fromisoformat(at)
            assert datetime.fromisoformat(row["start_utc"]) <= stamp < datetime.fromisoformat(row["end_utc"])
            instants.append({"at_utc": at, "interval": row})
        assert client.get(base+"/interval", params={"at_utc": result["end_utc"]}).status_code == 409
        report["result"] = {"result_id": result["result_id"], "decision": result["decision"], "request": result["request"],
            "display_response_bytes": len(response.content), "timeline_transport": result["timeline_transport"],
            "metrics_hours": result["metrics_hours"], "joint_hours": result["joint_hours"], "validation": result["validation"],
            "resolution": result["resolution"], "display_integrals_equal_native_metrics": True, "exact_instants": instants}
    report["passed"] = True
    report["monitor_elapsed_seconds"] = time.perf_counter()-started
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--job-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.base_url, args.job_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"passed": report["passed"], "decision": report["result"]["decision"],
        "display_bytes": report["result"]["display_response_bytes"]}, indent=2), flush=True)
