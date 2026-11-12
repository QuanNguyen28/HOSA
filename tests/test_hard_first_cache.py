"""Hard-first decisions and requirement-independent cache on explicit synthetic data."""
from pathlib import Path
import csv
import io
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
from test_point_analysis import pipeline, query
from app.core.errors import DomainError
from app.main import app
from app.point_analysis.physics_cache import PhysicalSeriesCache
from app.point_analysis.service import PointAnalysisJobs, get_point_jobs


def test_hard_failure_stops_before_one_minute_validation_and_soft(pipeline, monkeypatch):
    import app.point_analysis.pipeline as module
    old, calls = pipeline.ephemerides, []
    def no_sun(request, site, step, **kwargs):
        calls.append(step)
        assert step == 5, "Hard failure must not compute 1-minute ephemerides"
        sun, earth, receipts = old(request, site, step, **kwargs)
        sun["el_deg"] = -10.
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, "ephemerides", no_sun)
    monkeypatch.setattr(module, "validate", lambda *a, **k: pytest.fail("validation ran after hard fail"))
    monkeypatch.setattr(module, "assess_soft", lambda *a, **k: pytest.fail("soft evaluation ran after hard fail"))
    result = pipeline.run(query(evaluation_policy="hard_first", min_sunlit_fraction=.8,
        min_earth_los_fraction=.8, constraints={"max_darkness_hours": 0.}))
    assert calls == [5] and result["decision"] == "FAIL"
    assert result["constraint_checks"] == {"min_sunlit_fraction": "FAIL"}
    assert result["soft_constraint_checks"] == {}
    assert result["evaluation_stages"]["validation"] == "skipped_hard_failure"
    assert result["hard_failure"]["observed_bounds"] == [0, 0]
    assert result["hard_failure"]["shortfall_hours_bounds"] == [.8, .8]
    assert result["hard_failure"]["evidence_intervals"][0]["start_utc"].startswith("2026-11-17T00:00")


def test_unknown_upper_bound_is_not_a_hard_rejection(pipeline, monkeypatch):
    old, calls = pipeline.ephemerides, []
    def unknown(request, site, step, **kwargs):
        calls.append(step)
        sun, earth, receipts = old(request, site, step, **kwargs)
        sun["row_present"] = False
        receipts[0]["missing_timestamps"] = len(sun)
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, "ephemerides", unknown)
    result = pipeline.run(query(evaluation_policy="hard_first", min_sunlit_fraction=.8))
    assert 1 in calls and result["decision"] == "INDETERMINATE"
    assert result["metrics_hours"]["total_sun_hours"] == [0, 1]
    assert result["evaluation_stages"]["validation"] == "complete"


def test_soft_checks_run_after_validation_and_do_not_fail_hard_requirements(pipeline, monkeypatch):
    import app.point_analysis.pipeline as module
    old, assess, stages = pipeline.ephemerides, module.assess_soft, []
    def earth_blocked(*args, **kwargs):
        sun, earth, receipts = old(*args, **kwargs)
        earth["el_deg"] = -5.
        return sun, earth, receipts
    def soft(*args):
        assert stages[-1] == "soft_preferences"
        return assess(*args)
    monkeypatch.setattr(pipeline, "ephemerides", earth_blocked)
    monkeypatch.setattr(module, "assess_soft", soft)
    request = query(evaluation_policy="hard_first", min_sunlit_fraction=.8,
        constraints={"max_earth_blackout_hours": 0.})
    result = pipeline.run(request, stages.append)
    assert result["decision"] == "PASS"
    assert result["soft_constraint_checks"]["max_earth_blackout_hours"] == "FAIL"
    for diagnostic in result["validation"]["sensitivity"].values():
        if "metrics_hours" in diagnostic:
            assert diagnostic["soft_constraint_checks"] == assess(diagnostic["metrics_hours"], request.constraints)[0]
    assert stages.index("hard_requirements") < stages.index("scientific_validation") < stages.index("soft_preferences")


def test_persistent_physics_supports_exact_subwindows_and_invalidates_new_sources(tmp_path):
    cache = PhysicalSeriesCache(tmp_path)
    starts = pd.date_range("2026-11-17T00:00:00Z", periods=24, freq="5min")
    frame = pd.DataFrame({"start_utc": starts, "end_utc": starts+pd.Timedelta(minutes=5),
        "sun_state": "V", "earth_state": "B", "joint_state": "B", "sun_visible_fraction_lower": .5,
        "sun_visible_fraction_upper": .5, "sun_el_deg": 0., "sun_ephem_valid": True})
    identity = {"terrain_hash": "A", "kernel_hash": "B", "height": 20}
    cache.save(identity, frame, [{"source": "synthetic-only"}])
    other_process = PhysicalSeriesCache(tmp_path)
    subset = other_process.load(identity, starts[3], starts[9])
    assert len(subset) == 6 and subset.attrs["physical_series_cache_hit"]
    assert subset.sun_state.eq("V").all() and subset.sun_visible_fraction_lower.eq(.5).all()
    assert other_process.load({**identity, "height": 10}, starts[3], starts[9]) is None
    assert other_process.load({**identity, "terrain_hash": "new"}, starts[3], starts[9]) is None
    assert other_process.load(identity, starts[3]+pd.Timedelta(minutes=1), starts[9]) is None
    assert other_process.load(identity, starts[0], starts[-1]+pd.Timedelta(hours=1)) is None
    path = next(cache.root.glob("*/*/timeline.npy"))
    path.write_bytes(b"tampered")
    with pytest.raises(DomainError, match="TIMELINE_INTEGRITY_FAILED"):
        other_process.load(identity, starts[3], starts[9])


def test_csv_is_generated_only_when_requested(pipeline):
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline)
    app.dependency_overrides[get_point_jobs] = lambda: jobs
    try:
        with TestClient(app) as client:
            submitted = client.post("/api/lunar/point/analyses", json=query().model_dump()).json()
            jobs.close()
            result = jobs.result(submitted["job_id"], display=True)
            assert not (pipeline.root/"results"/result["result_id"]/"intervals.csv").exists()
            response = client.get(f'/api/lunar/point/analyses/{submitted["job_id"]}/intervals.csv')
            assert response.status_code == 200
            rows = list(csv.DictReader(io.StringIO(response.text)))
            assert len(rows) == 12 and rows[0]["sun_state"] == "V"
            assert rows[-1]["end_utc"].startswith("2026-11-17T01:00")
    finally:
        jobs.close()
        app.dependency_overrides.pop(get_point_jobs, None)


def test_failure_evidence_jumps_to_largest_deficit_instead_of_nearly_full_sun():
    from app.point_analysis.hard_first import failure
    starts = pd.date_range("2026-11-17T00:00:00Z", periods=12, freq="5min")
    frame = pd.DataFrame({"start_utc": starts, "end_utc": starts+pd.Timedelta(minutes=5),
        "sun_visible_fraction_upper": [.9999, 1, 1, .1, .2, 1, .99, 1, 1, 1, 1, 1]})
    proof = failure(query(min_sunlit_fraction=1.), {"total_sun_hours": [.8, .8]}, frame, "min_sunlit_fraction")
    assert proof["evidence_intervals"][0]["start_utc"] == starts[3].isoformat()
    assert proof["evidence_intervals"][0]["at_utc"] == starts[3].isoformat()
