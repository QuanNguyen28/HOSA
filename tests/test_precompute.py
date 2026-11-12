"""Portable product contracts; synthetic sphere fixtures are test data only."""
from pathlib import Path
import gzip
import sys

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
from app.core.errors import DomainError
from app.precompute.store import Store, coordinate_key, mesh_key, json_bytes
from app.precompute.geometry import prepared_terrain, encode_profile, FINE_STEP, SHORT_STEP
from app.precompute import display
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.point_analysis.geometry import METHOD_VERSION
from app.services.lunarsight import point
from app.services.lunarsight.horizon import ray_positions, ray_elevation


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setenv("HOSA_PRECOMPUTE_ROOT", str(tmp_path/"package"))
    monkeypatch.setenv("HOSA_DISPLAY_CACHE_ROOT", str(tmp_path/"runtime"))
    monkeypatch.setattr(point, "terrain_sources", lambda: [])
    return Store()


@pytest.fixture
def sphere(package):
    site = {"site_id": "coordinate", "lon_e_deg": 17., "lat_deg": -88., "dem_z_m": 100., "dem_sha256": "fixture"}
    record = {"site": site, "observer_source": {"dataset_id": "synthetic-sphere", "resolution_m": 80},
        "geometry_method": METHOD_VERSION, "heights_m": [1., 2.], "source_inventory": [],
        "datasets": [], "seams": [{"passed": False}], "profiles": {}}
    for label, step, radius in (("fine", FINE_STEP, 400000), ("short", SHORT_STEP, 300000)):
        az = np.arange(0, 360, step)
        lon, lat = ray_positions(17., -88., az, 1000.)
        for height in (1., 2.):
            profile = pd.DataFrame({"site_id": "coordinate", "height_m": height, "az_deg": az,
                "az_step_deg": step, "horizon_deg": ray_elevation(100., 100., height, 1000.),
                "blocker_distance_m": 1000., "blocker_z_m": 100., "blocker_lon_e_deg": lon.ravel() % 360,
                "blocker_lat_deg": lat.ravel(), "scan_radius_m": radius, "coverage_complete": True,
                "missing_samples": 0, "valid_samples": 1})
            profile.loc[0, "coverage_complete"] = False
            record["profiles"][f"{label}_h{height:g}"] = package.put(encode_profile(profile), "npz")
    package.publish(coordinate_key(-88., 17.), record)
    return record


def request(**updates):
    return MissionRequest(**{"latitude_deg": -88., "longitude_e_deg": 17., "start_utc": "2026-11-17T00:00:00Z", **updates})


def test_exact_coordinates_heights_and_source_changes(package, sphere, tmp_path, monkeypatch):
    assert prepared_terrain(request()) is not None
    assert prepared_terrain(request(latitude_deg=-88.00001)) is None
    assert prepared_terrain(request(panel_height_m=3.)) is None
    # A changed/new installed dataset requires a fresh build, even at the same coordinate.
    raw = tmp_path/"dem.tif"
    raw.write_bytes(b"new-source")
    raw.with_name(raw.name+".receipt.json").write_text('{"sha256":"changed"}')
    monkeypatch.setattr(point, "terrain_sources", lambda: [{"dataset_id": "new", "path": raw}])
    assert prepared_terrain(request()) is None


def test_prepared_geometry_without_raw_dem_preserves_unknowns_and_validation(package, sphere, tmp_path, monkeypatch):
    import app.point_analysis.pipeline as module
    def forbidden(*args, **kwargs):
        raise AssertionError("Precomputed observer must not scan raw DEM")
    monkeypatch.setattr(module, "TerrainInputs", forbidden)
    monkeypatch.setattr(module, "scan_horizons", forbidden)
    pipeline = PointAnalysisPipeline(tmp_path/"analysis")
    stages = []
    with pipeline.terrain(request()) as terrain:
        fine, short, seams, receipt = pipeline.geometry(terrain, [1., 2.], stages.append)
        assert "precomputed_horizon" in stages
        assert not fine[1.].coverage_complete.iloc[0]
        assert not seams[0]["passed"]
        np.testing.assert_array_equal(fine[1.].az_deg, np.arange(0, 360, .125))
        assert short[2.].az_step_deg.eq(.25).all()
        second = pipeline.geometry(terrain, [1., 2.], stages.append)
        np.testing.assert_allclose(second[0][1.].horizon_deg, fine[1.].horizon_deg, atol=1e-12)
        assert stages[-1] == "cached_horizon"
        # Every refinement level uses a strict subset, without interpolating horizons.
        for step in (.0625, .03125):
            refined, _, _ = terrain.profiles([1., 2.], step)
            assert len(refined[1.]) == round(360/step)


def test_artifact_integrity_and_path_confinement(package):
    reference = package.put(b"original", "npz")
    assert package.read(reference) == b"original"
    (package.root/reference["file"]).write_bytes(b"tampered")
    with pytest.raises(DomainError, match="PRECOMPUTE_INTEGRITY_FAILED"):
        package.read(reference)
    with pytest.raises(DomainError, match="PRECOMPUTE_INTEGRITY_FAILED"):
        package.read({**reference, "file": "../../private"})


def test_profile_grid_and_independent_enu_fail_closed(package, sphere):
    prepared = prepared_terrain(request())
    prepared.record = sphere
    reference = sphere["profiles"]["fine_h1"]
    from app.precompute.geometry import decode_profile
    frame = decode_profile(package.read(reference))
    frame.loc[0, "height_m"] = 3.
    sphere["profiles"]["fine_h1"] = package.put(encode_profile(frame), "npz")
    with pytest.raises(DomainError, match="PRECOMPUTE_GRID_MISMATCH"):
        prepared.profiles([1.], .125)
    frame.loc[0, "height_m"] = 1.
    frame["horizon_deg"] += 1.
    sphere["profiles"]["fine_h1"] = package.put(encode_profile(frame), "npz")
    with pytest.raises(ValueError, match="ENU reference"):
        prepared.profiles([1.], .125)


def test_display_runtime_reuse_and_unknown_not_pinned(package, monkeypatch):
    count = []
    def compute():
        count.append(1)
        return {"coverage_status": "COVERED", "grid": [1, None, 2]}
    first = display.cached_display("mesh", compute, method="test")
    second = display.cached_display("mesh", compute, method="test")
    assert first[0] == second[0] and not first[2] and second[2] and len(count) == 1
    monkeypatch.setattr(display, "source_signature", lambda: ["updated"])
    assert not display.cached_display("mesh", compute, method="test")[2]
    unknown = lambda: {"coverage_status": "UNKNOWN", "grid": None}
    assert not display.cached_display("unknown", unknown, method="test")[2]
    assert not display.cached_display("unknown", unknown, method="test")[2]


def test_packaged_display_and_http_conditional_encoding(package, monkeypatch):
    from app.main import app
    payload = {"coverage_status": "COVERED", "grid": [1, None, 2]}
    reference = package.put(gzip.compress(json_bytes(payload), mtime=0), "json.gz")
    key = mesh_key(-88., 17., 6., 257, "best")
    package.publish_meshes({key: {**reference, "display_method": point.METHOD_VERSION, "source_inventory": []}})
    def forbidden(*args, **kwargs):
        raise AssertionError("Packaged display must not read raw DEM")
    monkeypatch.setattr(point, "_terrain_window_uncached", forbidden)
    with TestClient(app) as client:
        path = "/api/lunar/point/terrain-window?latitude=-88&longitude=17&radius_km=6&samples=257"
        response = client.get(path, headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200 and response.json() == payload
        assert response.headers["Content-Encoding"] == "gzip"
        assert response.headers["X-Terrain-Cache"] == "HIT"
        etag = response.headers["ETag"]
        assert client.get(path, headers={"If-None-Match": etag, "Accept-Encoding": "gzip"}).status_code == 304
        plain = client.get(path, headers={"Accept-Encoding": "gzip;q=0"})
        assert plain.json() == payload and "Content-Encoding" not in plain.headers
        assert plain.headers["ETag"] != etag
        assert "max-age=300" in plain.headers["Cache-Control"]
        assert client.get(path.replace("samples=257", "samples=256")).status_code == 400


def test_invalid_manifest_fails_closed(package):
    package.root.mkdir(parents=True, exist_ok=True)
    (package.root/"manifest.json").write_text('{"schema_version":"site-precompute-1.0"}')
    with pytest.raises(DomainError, match="PRECOMPUTE_MANIFEST_INVALID"):
        package.manifest()
