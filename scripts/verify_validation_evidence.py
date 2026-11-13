#!/usr/bin/env python3
"""Verify real-data threshold reuse and 5/1-minute hard rejection, without LLM."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline


def measured(pipeline, request):
    started = perf_counter()
    result = pipeline.run(request, display=True)
    return result, {"elapsed_seconds": perf_counter()-started, "decision": result["decision"],
        "result_id": result["result_id"], "execution": result["execution"]}


def verify():
    report = {"passed": False, "live_llm_calls": 0, "cases": []}
    request = MissionRequest(site_id="Site04_P1", start_utc="2026-03-01T00:00:00Z", duration_hours=72.,
        panel_height_m=20., antenna_height_m=20., min_sunlit_fraction=.1, min_earth_los_fraction=.1,
        resolve_indeterminate=True, evaluation_policy="complete")
    with TemporaryDirectory(prefix="hosa-evidence-verify-") as directory:
        root = Path(directory)
        first, timing = measured(PointAnalysisPipeline(root/"reused"), request)
        assert first["decision"] == "PASS"
        report["cases"].append({"name": "prepare_evidence", **timing})
        stricter = request.model_copy(update={"min_earth_los_fraction": .99, "resolve_indeterminate": False})
        # A new pipeline object tests persistent evidence rather than memory reuse.
        pipeline = PointAnalysisPipeline(root/"reused")
        with patch.object(pipeline, "ephemerides", side_effect=AssertionError("Astronomy recomputed")), \
             patch.object(pipeline, "visible", side_effect=AssertionError("Visibility recomputed")), \
             patch("app.mission.mission_path.path_evidence", side_effect=AssertionError("Envelope recomputed")):
            second, timing = measured(pipeline, stricter)
            assert second["decision"] == "FAIL" and second["execution"]["validation_evidence_cache_hit"]
            report["cases"].append({"name": "stricter_requirement", "astronomy_and_visibility_calls": 0, **timing})
            third, timing = measured(pipeline, request.model_copy(update={"min_earth_los_fraction": .2}))
            assert third["decision"] == "PASS" and third["execution"]["validation_evidence_cache_hit"]
            report["cases"].append({"name": "relaxed_requirement", "astronomy_and_visibility_calls": 0, **timing})
        independent, timing = measured(PointAnalysisPipeline(root/"independent"), stricter)
        assert independent["metrics_hours"] == second["metrics_hours"]
        assert independent["constraint_checks"] == second["constraint_checks"]
        assert independent["decision"] == second["decision"]
        report["cases"].append({"name": "fresh_evidence_matches_reused", **timing})
        failure = MissionRequest(site_id="example-b", start_utc="2026-11-24T00:00:00Z", duration_hours=72.,
            panel_height_m=20., antenna_height_m=20., min_sunlit_fraction=.8)
        result, timing = measured(PointAnalysisPipeline(root/"hard-fail"), failure)
        assert result["decision"] == "FAIL"
        assert result["hard_failure"]["confirmed_sampling_minutes"] == [5, 1]
        assert result["hard_failure"]["sampling_minutes"] == 1
        assert result["validation"]["temporal_confirmation"]["confirmed"]
        report["cases"].append({"name": "hard_fail_confirmed", "confirmation": result["validation"]["temporal_confirmation"], **timing})
    pipeline = PointAnalysisPipeline(ROOT/"data/cache/point-analysis")
    century = MissionRequest(site_id="Site04_P1", start_utc="2000-01-01T00:00:00Z", end_utc="2101-01-01T00:00:00Z",
        panel_height_m=20., antenna_height_m=20.)
    started = perf_counter()
    result = pipeline.indexed_metrics(century)
    assert result["decision"] is None and result["execution"]["metrics_index_hit"] and len(result["timeline"]) == 800
    report["prepared_century_metrics"] = {"elapsed_seconds": perf_counter()-started, "display_intervals": 800,
        "evaluation_stages": result["evaluation_stages"]}
    report.update(passed=True, scope="Selected real NASA/SPICE windows, isolated result/evidence caches and zero LLM calls. Local timings; no full-century validation or continuous-time certificate.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
