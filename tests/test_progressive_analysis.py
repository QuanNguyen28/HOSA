"""Progressive delivery must not publish an unvalidated decision or alter science."""
import json
from pathlib import Path
import sys
from threading import Event

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
from test_point_analysis import pipeline, query, SyntheticSphere
from app.main import app
from app.core.errors import DomainError
from app.point_analysis.service import PointAnalysisJobs, get_point_jobs, get_point_pipeline
from app.point_analysis.transport import display_timeline, write_frame, exact_interval, read_array, frame_from_array
from app.mission.evaluation import records


@pytest.mark.parametrize("failure", [False, True])
def test_preview_arrives_before_validation_and_survives_failure(pipeline, monkeypatch, failure):
    entered, release = Event(), Event()
    original = pipeline.evaluate_geometry
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        if failure:
            raise DomainError("TEST_VALIDATION_UNAVAILABLE", 503)
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline, "evaluate_geometry", delayed)
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline)
    app.dependency_overrides[get_point_jobs] = lambda: jobs
    try:
        with TestClient(app) as client:
            submitted = client.post("/api/lunar/point/analyses", json=query(min_sunlit_fraction=.8).model_dump())
            identifier = submitted.json()["job_id"]
            assert entered.wait(5)
            state = client.get(f"/api/lunar/point/analyses/{identifier}").json()
            assert state["status"] == "running" and state["preview_url"]
            preview = client.get(state["preview_url"])
            assert preview.status_code == 200
            preview = preview.json()
            assert preview["evaluation_status"] == "pending"
            assert preview["decision"] is None and preview["nominal_sampled_decision"] is None
            assert not preview["validation"]["passed"] and preview["constraint_checks"] == {}
            assert preview["metrics_hours"]["total_sun_hours"] == [1, 1]
            assert preview["joint_hours"] == [1, 1]
            assert not (pipeline.root/"results"/preview["result_id"]/"receipt.json").exists()
            exact = client.get(f"/api/lunar/point/analyses/{identifier}/interval", params={"at_utc": "2026-11-17T00:02:00Z"})
            assert exact.status_code == 200 and exact.json()["sun_state"] == "V"
            release.set()
            jobs.close()
            state = client.get(f"/api/lunar/point/analyses/{identifier}").json()
            if failure:
                assert state["status"] == "failed"
                assert client.get(state["preview_url"]).json()["evaluation_status"] == "pending"
                assert client.get(f"/api/lunar/point/analyses/{identifier}/result").status_code == 409
            else:
                assert state["status"] == "succeeded"
                result = client.get(state["result_url"], params={"view": "display"}).json()
                assert result["evaluation_status"] == "complete" and result["decision"] == "PASS"
                assert result["metrics_hours"] == preview["metrics_hours"]
                assert result["joint_hours"] == preview["joint_hours"]
    finally:
        release.set()
        jobs.close()
        app.dependency_overrides.pop(get_point_jobs, None)


def test_display_result_is_bounded_and_full_api_still_has_native_rows(pipeline):
    request = query(duration_hours=96., min_sunlit_fraction=.8)
    preview = []
    compact = pipeline.run(request, preview=lambda result, frame: preview.append(result), display=True)
    assert compact["timeline_transport"]["source_intervals"] == 1152
    assert compact["timeline_transport"]["mode"] == "aggregated" and len(compact["timeline"]) == 800
    full = pipeline.run(request)
    assert len(full["timeline"]) == 1152 and full["timeline_transport"]["mode"] == "native"
    assert compact["metrics_hours"] == full["metrics_hours"]
    assert compact["validation"] == full["validation"] and compact["decision"] == full["decision"]
    assert compact["joint_hours"] == full["joint_hours"] == [96, 96]
    assert pipeline.lookup_cached(request, display=True)["timeline"] == compact["timeline"]
    directory = pipeline.root/"results"/full["result_id"]
    artifact = compact["provenance"]["timeline_artifact"]
    assert exact_interval(directory, artifact, "2026-11-17T00:05:00Z") == full["timeline"][1]
    with pytest.raises(DomainError, match="OUTSIDE_MISSION_WINDOW"):
        exact_interval(directory, artifact, request.end_utc)
    with pytest.raises(DomainError, match="INVALID_INTERVAL_TIME"):
        exact_interval(directory, artifact, "2026-11-17T00:00:00")
    (directory/artifact["file"]).write_bytes(b"corrupt")
    with pytest.raises(DomainError, match="TIMELINE_INTEGRITY_FAILED"):
        exact_interval(directory, artifact, request.start_utc)


def test_weighted_display_does_not_present_a_mixed_bin_as_an_instant(tmp_path):
    starts = pd.to_datetime(["2026-11-17T00:00:00Z", "2026-11-17T00:01:00Z"])
    ends = pd.to_datetime(["2026-11-17T00:01:00Z", "2026-11-17T00:04:00Z"])
    frame = pd.DataFrame({"start_utc": starts, "end_utc": ends, "sun_state": ["V", "B"],
        "earth_state": ["?", "V"], "joint_state": ["?", "B"],
        "sun_visible_fraction_lower": [.5, 0], "sun_visible_fraction_upper": [.5, 0],
        "sun_el_deg": [np.nan, -1.], "sun_ephem_valid": [False, True]})
    rows, metadata = display_timeline(frame, limit=1)
    assert metadata["source_intervals"] == 2 and rows[0]["aggregated"]
    assert rows[0]["sun_state"] == rows[0]["earth_state"] == "?"
    assert rows[0]["sun_visible_fraction"] == .125
    assert rows[0]["earth_visible_fraction_lower"] == .75
    assert rows[0]["earth_visible_fraction_upper"] == 1.
    reference = write_frame(tmp_path/"timeline.npy", frame)
    assert records(frame_from_array(read_array(tmp_path, reference), reference)) == records(frame)
    assert exact_interval(tmp_path, reference, "2026-11-17T00:01:00Z")["sun_state"] == "B"


def test_native_artifact_small_json_can_represent_ten_years_without_string_overflow(pipeline):
    # Transport regression only. Synthetic fixture does not claim lunar science.
    native = pd.DataFrame({"start_utc": pd.date_range("2026-01-01", "2036-01-01", freq="5min", inclusive="left", tz="UTC")})
    native["end_utc"] = native.start_utc+pd.Timedelta(minutes=5)
    for body in ("sun", "earth", "joint"):
        native[f"{body}_state"] = "V"
    rows, metadata = display_timeline(native)
    assert metadata["source_intervals"] > 1_000_000 and len(rows) == 800
    assert len(json.dumps(rows)) < 1_000_000
    assert rows[-1]["end_utc"].startswith("2036-01-01")


@pytest.mark.parametrize("blocked_step", ["display_timeline", "write_frame"])
def test_metrics_publish_before_native_preview_serialization(pipeline, monkeypatch, blocked_step):
    import app.point_analysis.service as module
    entered, release = Event(), Event()
    write = getattr(module, blocked_step)
    def blocked(*args):
        entered.set()
        assert release.wait(10)
        return write(*args)
    monkeypatch.setattr(module, blocked_step, blocked)
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline)
    app.dependency_overrides[get_point_jobs] = lambda: jobs
    try:
        with TestClient(app) as client:
            identifier = client.post("/api/lunar/point/analyses", json=query().model_dump()).json()["job_id"]
            assert entered.wait(5)
            state = client.get(f"/api/lunar/point/analyses/{identifier}").json()
            preview = client.get(state["preview_url"]).json()
            assert preview["metrics_hours"]["total_sun_hours"] == [1, 1]
            assert preview["joint_hours"] == [1, 1] and preview["decision"] is None
            assert bool(preview["timeline"]) == (blocked_step == "write_frame")
            assert preview["timeline_transport"]["exact_intervals_ready"] is False
            assert "timeline_artifact" not in preview["provenance"]
            assert client.get(f"/api/lunar/point/analyses/{identifier}/interval", params={"at_utc": query().start_utc}).status_code == 409
    finally:
        release.set()
        jobs.close()
        app.dependency_overrides.pop(get_point_jobs, None)


def test_indexed_metrics_publish_before_any_native_cache_read(pipeline, monkeypatch):
    request = query()
    result = pipeline.run(request, display=True)
    frame = frame_from_array(read_array(pipeline.root/"results"/result["result_id"], result["provenance"]["timeline_artifact"]), result["provenance"]["timeline_artifact"])
    source = {"synthetic_test": True}
    pipeline.physics.save(source, frame, [], index=True)
    monkeypatch.setattr(pipeline, "initial_source", lambda *args: source)
    entered, release = Event(), Event()
    load = pipeline.physics.load
    def blocked(*args):
        entered.set()
        assert release.wait(10)
        return load(*args)
    monkeypatch.setattr(pipeline.physics, "load", blocked)
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline)
    app.dependency_overrides[get_point_jobs] = lambda: jobs
    try:
        with TestClient(app) as client:
            identifier = client.post("/api/lunar/point/analyses", json=query(min_sunlit_fraction=.7).model_dump()).json()["job_id"]
            assert entered.wait(5)
            status = client.get(f"/api/lunar/point/analyses/{identifier}").json()
            preview = client.get(status["preview_url"]).json()
            assert preview["execution"]["metrics_index_hit"]
            assert preview["metrics_hours"] == result["metrics_hours"]
            assert preview["joint_hours"] == result["joint_hours"]
            assert preview["decision"] is None and preview["timeline"]
            assert preview["timeline_transport"]["exact_intervals_ready"] is False
    finally:
        release.set()
        jobs.close()
        app.dependency_overrides.pop(get_point_jobs, None)


@pytest.mark.parametrize("storage", ["physical", "compact"])
def test_metrics_endpoint_reads_only_prepared_index_and_never_schedules_analysis(pipeline, monkeypatch, storage):
    request = query()
    result = pipeline.run(request, display=True)
    reference = result["provenance"]["timeline_artifact"]
    frame = frame_from_array(read_array(pipeline.root/"results"/result["result_id"], reference), reference)
    source = {"synthetic_endpoint": True}
    if storage == "physical":
        pipeline.physics.save(source, frame, [], index=True)
    else:
        from app.point_analysis import metric_index
        from app.point_analysis.prepared_metrics import PreparedMetrics
        content, full = metric_index.build(frame)
        PreparedMetrics(pipeline.root).publish(source, frame.start_utc.iloc[0], frame.end_utc.iloc[-1], content, full, [{"synthetic": True}])
    monkeypatch.setattr("app.precompute.geometry.prepared_terrain", lambda _: SyntheticSphere())
    monkeypatch.setattr(pipeline, "initial_source", lambda *args: source)
    monkeypatch.setattr(pipeline.physics, "load", lambda *a: pytest.fail("native timeline read"))
    monkeypatch.setattr(pipeline, "ephemerides", lambda *a, **k: pytest.fail("ephemerides computed"))
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pytest.fail("analysis ran"))
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            response = client.post("/api/lunar/point/metrics", json=request.model_dump())
            assert response.status_code == 200
            body = response.json()
            assert body["metrics_hours"] == result["metrics_hours"]
            assert body["joint_hours"] == result["joint_hours"]
            assert body["decision"] is None and body["timeline"]
            assert body["timeline_transport"]["exact_intervals_ready"] is False
            assert body["evaluation_stages"]["validation"] == "not_started"
            assert body["execution"]["physical_series_cache_hit"] == (storage == "physical")
            assert not (pipeline.root/"jobs").exists()
            missing = client.post("/api/lunar/point/metrics", json=query(duration_hours=2).model_dump())
            assert missing.status_code == 409 and missing.json()["detail"]["code"] == "METRICS_NOT_PREPARED"
            monkeypatch.setattr("app.precompute.geometry.prepared_terrain", lambda _: None)
            assert client.post("/api/lunar/point/metrics", json=request.model_dump()).status_code == 409
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)
