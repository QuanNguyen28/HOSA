#!/usr/bin/env python3
"""Real-data before/after execution policies with isolated completed-result caches."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from verify_compute_and_resolution import seed, SOURCE


def measured(root, request):
    pipeline = PointAnalysisPipeline(root)
    started, stages, previews = perf_counter(), [], []
    def progress(stage):
        stages.append({"stage": stage, "seconds": perf_counter()-started})
    def preview(result, frame):
        previews.append({"seconds": perf_counter()-started, "physical_cache_hit": result["execution"].get("physical_series_cache_hit", False),
            "metrics_hours": result["metrics_hours"], "joint_hours": result["joint_hours"]})
    result = pipeline.run(request, progress, preview=preview, display=True)
    seconds = perf_counter()-started
    assert not result["execution"]["result_cache_hit"]
    directory = root/"results"/result["result_id"]
    assert not (directory/"intervals.csv").exists()
    commit = next(s["seconds"] for s in stages if s["stage"] == "commit_artifacts")
    return result, {"seconds": seconds, "preview": previews[0], "stages": stages,
        "commit_seconds": seconds-commit, "interval_csv_written": False,
        "decision": result["decision"], "result_id": result["result_id"], "metrics_hours": result["metrics_hours"]}


def verify(long=True):
    report = {"passed": False, "cases": [], "live_llm_calls": 0,
        "scope": "Local timings; isolated completed-result caches, installed verified terrain/kernel data. Physical cache is persistent. complete includes numerical validation; hard_first skips full validation only after the SAME hard requirement fails 5/1-minute grids. Final hard-fail metrics use 1-minute samples. Neither path writes CSV automatically."}
    with TemporaryDirectory(prefix="hard-first-acceptance-", dir=SOURCE) as temporary:
        root = Path(temporary)
        seed(root)
        (root/"physical-series").symlink_to(SOURCE/"physical-series", target_is_directory=True)
        cases = [("Haworth-72h", {"site_id": "haworth", "start_utc": "2026-11-17T00:00:00Z", "duration_hours": 72., "min_sunlit_fraction": .8})]
        if long:
            cases.append(("Site04-10years", {"site_id": "Site04_P1", "start_utc": "2026-11-24T00:00:00Z", "end_utc": "2036-11-24T00:00:00Z", "min_sunlit_fraction": .99}))
        for name, data in cases:
            request = MissionRequest(**data, panel_height_m=20., antenna_height_m=20., offline=True, resolve_indeterminate=True)
            before, baseline = measured(root, request.model_copy(update={"evaluation_policy": "complete"}))
            after, optimized = measured(root, request)
            assert before["decision"] == after["decision"] == "FAIL"
            confirmation = after["validation"]["temporal_confirmation"]
            assert confirmation["confirmed"] and confirmation["sampling_minutes"] == [5, 1]
            assert before["metrics_hours"] == confirmation["metrics_5min_hours"]
            assert after["metrics_hours"] == confirmation["metrics_1min_hours"]
            assert after["validation"]["status"] == "skipped_hard_failure" and after["hard_failure"]
            assert not any(s["stage"] in ("scientific_validation", "soft_preferences") for s in optimized["stages"])
            case = {"name": name, "request": request.model_dump(), "complete": baseline, "hard_first": optimized,
                "same_coarse_metrics_and_confirmed_decision": True, "hard_failure": after["hard_failure"], "speedup": baseline["seconds"]/optimized["seconds"]}
            report["cases"].append(case)
            print(json.dumps({"case": name, "complete_seconds": baseline["seconds"], "hard_first_seconds": optimized["seconds"],
                "preview_seconds": optimized["preview"]["seconds"], "speedup": case["speedup"]}), flush=True)
            if name == "Haworth-72h":
                changed = request.model_copy(update={"min_sunlit_fraction": .9})
                result, timing = measured(root, changed)
                assert result["execution"]["physical_series_cache_hit"] and result["decision"] == "FAIL"
                subwindow = MissionRequest(site_id="haworth", start_utc="2026-11-18T00:00:00Z", duration_hours=24.,
                    min_sunlit_fraction=.8, panel_height_m=20., antenna_height_m=20., offline=True)
                result, subset = measured(root, subwindow)
                assert result["execution"]["physical_series_cache_hit"] and result["decision"] == "FAIL"
                case["changed_requirement"] = timing
                case["subwindow"] = subset
        report["passed"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-long", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(not args.skip_long)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
