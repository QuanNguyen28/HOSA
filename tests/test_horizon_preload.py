"""Automatic horizon preparation must not invoke mission evaluation or astronomy."""
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.point_analysis.horizon_preload import HorizonPreloads, get_horizon_preloads
from app.point_analysis.service import get_point_pipeline
from test_point_analysis import pipeline, query


def test_preload_deduplicates_time_and_requirement_changes_then_reuses_geometry(pipeline, monkeypatch):
    preloads = HorizonPreloads()
    gate, entered = Event(), Event()
    original = pipeline.geometry
    def blocked(*args):
        entered.set()
        assert gate.wait(10)
        return original(*args)
    monkeypatch.setattr(pipeline, "geometry", blocked)
    monkeypatch.setattr(pipeline, "run", lambda *args: pytest.fail("preload evaluated a mission"))
    monkeypatch.setattr(pipeline, "ephemerides", lambda *args: pytest.fail("terrain preload computed astronomy"))
    try:
        first = preloads.ensure(query(panel_height_m=10, antenna_height_m=30), pipeline)
        assert first["status"] == "preparing" and entered.wait(3)
        other = preloads.ensure(query(panel_height_m=30, antenna_height_m=10,
            start_utc="2028-01-01T00:00:00Z", min_sunlit_fraction=.1), pipeline)
        assert first["preparation_id"] == other["preparation_id"]
        assert len(preloads.pending) == 1
        gate.set()
        preloads.pending[first["preparation_id"]].result(timeout=10)
        ready = preloads.ensure(query(panel_height_m=10, antenna_height_m=30), pipeline)
        assert ready["status"] == "ready"
        assert [p["height_m"] for p in ready["profile"]["profiles"]] == [10, 30]
        assert len(preloads.pending) == 1
    finally:
        gate.set()
        preloads.close()


def test_preload_api_returns_ready_after_background_geometry(pipeline, monkeypatch):
    gate, entered = Event(), Event()
    preloads = HorizonPreloads()
    original = pipeline.geometry
    def blocked(*args):
        entered.set()
        assert gate.wait(10)
        return original(*args)
    monkeypatch.setattr(pipeline, "geometry", blocked)
    monkeypatch.setattr("app.point_analysis.horizon_preload.get_horizon_preloads", lambda: preloads)
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        # No lifespan here: it is unrelated to the dependency-injected worker.
        client = TestClient(app)
        response = client.post("/api/lunar/point/horizon-profile/preload", json=query().model_dump())
        assert response.status_code == 202 and response.headers["Retry-After"] == "1"
        assert entered.wait(3)
        gate.set()
        preloads.pending[response.json()["preparation_id"]].result(timeout=10)
        ready = client.post("/api/lunar/point/horizon-profile/preload", json=query().model_dump())
        assert ready.status_code == 200 and ready.json()["status"] == "ready"
    finally:
        gate.set()
        preloads.close()
        app.dependency_overrides.pop(get_point_pipeline, None)
