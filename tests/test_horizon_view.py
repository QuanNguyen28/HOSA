"""Horizon view does not evaluate a mission or silently scan new terrain."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from test_point_analysis import pipeline, query
from app.core.errors import DomainError
from app.main import app
from app.point_analysis.horizon_view import profile_view, sky_track
from app.point_analysis.service import get_point_pipeline


def test_profile_never_starts_an_uncached_scan(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline, "geometry", lambda *a: pytest.fail("view started DEM scan"))
    with pytest.raises(DomainError, match="HORIZON_NOT_PREPARED"):
        profile_view(query(), pipeline)


def test_profile_uses_requested_heights_and_preserves_missing_sectors(pipeline, monkeypatch):
    request = query(panel_height_m=10, antenna_height_m=30)
    with pipeline.terrain(request) as terrain:
        pipeline.geometry(terrain, {10., 30.}, lambda _: None)
    original = pipeline.geometry
    def missing(*args):
        fine, short, seams, receipt = original(*args)
        fine[10].loc[0, "horizon_deg"] = np.nan
        fine[10].loc[0, "coverage_complete"] = False
        return fine, short, seams, receipt
    monkeypatch.setattr(pipeline, "geometry", missing)
    monkeypatch.setattr(pipeline, "run", lambda *a: pytest.fail("view evaluated mission"))
    result = profile_view(request, pipeline)
    assert [p["height_m"] for p in result["profiles"]] == [10, 30]
    assert result["profiles"][0]["points"][0]["horizon_deg"] is None
    assert not result["profiles"][0]["coverage_complete"]
    assert result["profiles"][1]["coverage_complete"]
    assert result["profiles"][1]["points"][0]["horizon_deg"] < 0
    json.dumps(result, allow_nan=False)


def fake_vectors(pipeline, monkeypatch):
    provider = pipeline.shared_ephemeris
    calls = []
    monkeypatch.setattr(provider, "identity", lambda: {"fixture": "synthetic-only"})
    def vectors(times, source):
        calls.append(times)
        # Actual ENU/parallax projection still runs on controlled vectors.
        return np.tile([149600000., 0., 0., 384400., 0., 0.], (len(times), 1)), []
    monkeypatch.setattr(provider, "vectors", vectors)
    monkeypatch.setattr(pipeline, "run", lambda *a: pytest.fail("track evaluated mission"))
    return calls


def test_century_uses_bounded_chunks_and_cache_with_exact_end_boundary(pipeline, monkeypatch):
    calls = fake_vectors(pipeline, monkeypatch)
    request = query(start_utc="2000-01-01T00:00:00Z", end_utc="2101-01-01T00:00:00Z",
                    panel_height_m=2, antenna_height_m=30, duration_hours=float((pd.Timestamp("2101-01-01T00:00:00Z")-pd.Timestamp("2000-01-01T00:00:00Z")).total_seconds()/3600))
    first = sky_track(request, pipeline)
    assert first["chunk_count"] > 300 and first["sample_count"] == 120*24+1
    assert first["sampling_seconds"] == 3600
    assert first["start_utc"].startswith("2000-01-01")
    assert len(first["bodies"]["sun"]) == first["sample_count"]
    assert all(len(row) == 3 for row in first["bodies"]["earth"])
    assert sky_track(request, pipeline) == first and len(calls) == 1
    last = sky_track(request, pipeline, first["chunk_count"]-1)
    assert pd.Timestamp(last["end_utc"]) == pd.Timestamp(request.end_utc)
    assert calls[-1][-1] == pd.Timestamp(request.end_utc)
    assert max(map(len, calls)) <= 2881
    with pytest.raises(DomainError, match="OUTSIDE_SKY_TRACK"):
        sky_track(request, pipeline, first["chunk_count"])
    path = next((pipeline.root/"sky-tracks").glob("*.json"))
    envelope = json.loads(path.read_text())
    envelope["payload"]["sample_count"] = 0
    path.write_text(json.dumps(envelope))
    index = 0 if envelope["payload"]["start_utc"] == first["start_utc"] else first["chunk_count"]-1
    with pytest.raises(DomainError, match="SKY_TRACK_INTEGRITY_FAILED"):
        sky_track(request, pipeline, index)


def test_short_track_and_compressed_api_contract(pipeline, monkeypatch):
    calls = fake_vectors(pipeline, monkeypatch)
    request = query(duration_hours=72, panel_height_m=2, antenna_height_m=2)
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            response = client.post("/api/lunar/point/sky-track", json=request.model_dump())
            assert response.status_code == 200
            assert response.headers["content-encoding"] == "gzip"
            result = response.json()
            assert result["sampling_seconds"] == 300 and result["sample_count"] == 865
            assert len(calls) == 1
            invalid = client.post("/api/lunar/point/sky-track?chunk_index=-1", json=request.model_dump())
            assert invalid.status_code == 422
            empty = client.post("/api/lunar/point/horizon-profile", json=request.model_dump())
            assert empty.status_code == 409 and empty.json()["detail"]["code"] == "HORIZON_NOT_PREPARED"
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)
