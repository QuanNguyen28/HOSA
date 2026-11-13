"""Preview instants are bounded native samples, never mission averages."""
import pandas as pd
import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_point_analysis import pipeline, query, SyntheticSphere
from app.main import app
from app.core.errors import DomainError
from app.point_analysis.service import get_point_pipeline


@pytest.mark.parametrize("earth_visible", [False, True])
def test_preview_samples_only_one_interval_and_joint_uses_any_sun(pipeline, monkeypatch, earth_visible):
    monkeypatch.setattr("app.precompute.geometry.prepared_terrain", lambda request: SyntheticSphere(request))
    request = query(illumination_model="solar_disc", duration_hours=20*365*24)
    windows = []
    def ephemerides(sample, site, step):
        windows.append((sample.start_utc, sample.end_utc, step))
        grid = pd.date_range(sample.start_utc, sample.end_utc, freq="5min")
        frame = lambda el, distance: pd.DataFrame({"az_deg": 90., "el_deg": el,
            "distance_km": distance, "row_present": True}, index=grid)
        # Half-disc above an analytic flat horizon; Earth far from the Sun.
        sun, earth = frame(0., 149600000.), frame(5. if earth_visible else -5., 384400.)
        earth["az_deg"] = 270.
        return sun, earth, []
    monkeypatch.setattr(pipeline, "ephemerides", ephemerides)
    original = pipeline.geometry
    def geometry(*args):
        fine, short, seams, receipt = original(*args)
        for profiles in (fine, short):
            for profile in profiles.values():
                profile["horizon_deg"] = 0.
        return fine, short, seams, receipt
    monkeypatch.setattr(pipeline, "geometry", geometry)
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pytest.fail("instant ran full analysis"))
    row = pipeline.prepared_instant(request, "2026-11-17T00:07:30Z")
    assert windows == [("2026-11-17T00:05:00+00:00", "2026-11-17T00:10:00+00:00", 5)]
    assert row["sun_visible_fraction"] == pytest.approx(.5)
    assert row["sun_state"] == "V"
    assert row["earth_state"] == row["joint_state"] == ("V" if earth_visible else "B")
    assert row["evidence_source"] == "prepared_nominal" and row["sampling_minutes"] == 5
    assert not list(pipeline.root.glob("results/*/result.json"))


@pytest.mark.parametrize("stamp,code", [
    ("2026-11-17T00:00:00", "INVALID_INTERVAL_TIME"),
    ("invalid", "INVALID_INTERVAL_TIME"),
    ("2026-11-16T23:59:59Z", "OUTSIDE_MISSION_WINDOW"),
    ("2026-11-17T01:00:00Z", "OUTSIDE_MISSION_WINDOW"),
])
def test_instant_api_rejects_invalid_or_outside_half_open_window(pipeline, stamp, code):
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            result = client.post("/api/lunar/point/instant", params={"at_utc": stamp}, json=query(illumination_model="solar_disc").model_dump())
            assert result.status_code == (400 if code == "INVALID_INTERVAL_TIME" else 409)
            assert result.json()["detail"]["code"] == code
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)


def test_missing_prepared_terrain_does_not_start_dem_scan(pipeline, monkeypatch):
    monkeypatch.setattr("app.precompute.geometry.prepared_terrain", lambda request: None)
    monkeypatch.setattr(pipeline, "geometry", lambda *a: pytest.fail("unexpected terrain scan"))
    with pytest.raises(DomainError, match="INSTANT_NOT_PREPARED"):
        pipeline.prepared_instant(query(illumination_model="solar_disc"), "2026-11-17T00:00:00Z")


def test_visual_sky_api_normalizes_month_in_utc_without_running_analysis(pipeline, monkeypatch):
    provider = pipeline.shared_ephemeris
    identity = {"frame": "MOON_ME", "synthetic_fixture": True}
    monkeypatch.setattr(provider, "identity", lambda: identity)
    seen = []
    def chunk(month, source):
        seen.append((month, source))
        return np.zeros((745, 6)), {"month": month, "sha256": "synthetic-only"}
    monkeypatch.setattr(provider, "chunk", chunk)
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pytest.fail("sky preview ran mission analysis"))
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            result = client.get("/api/lunar/point/sky-vectors", params={"at_utc": "2027-01-01T01:00:00+07:00"})
            assert result.status_code == 200
            data = result.json()
            assert data["start_utc"] == "2026-12-01T00:00:00+00:00"
            assert data["end_utc"] == "2027-01-01T00:00:00+00:00"
            assert data["step_seconds"] == 3600 and len(data["vectors_km"]) == 745
            assert data["identity"] == identity and data["table"]["sha256"] == "synthetic-only"
            assert seen == [("2026-12-01", identity)]
            for bad in ["2026-12-01", "invalid"]:
                invalid = client.get("/api/lunar/point/sky-vectors", params={"at_utc": bad})
                assert invalid.status_code == 400 and invalid.json()["detail"]["code"] == "INVALID_INTERVAL_TIME"
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)
