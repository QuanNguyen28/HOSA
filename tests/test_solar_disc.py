"""New illumination semantics; synthetic fixtures never serve production science."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
from test_point_analysis import pipeline, query
from app.core.errors import DomainError
from app.mission.evaluation import metrics, evaluate
from app.mission.models import MissionRequest
from app.planning.models import CompareRequest, SearchRequest
from app.planning.service import PlanningService
from app.planning.repository import ResultRepository, result_csv
from app.services.lunarsight.shared_ephemeris import SharedEphemeris
from app.services.lunarsight.solar_disc import fractions, SUN_RADIUS_KM
from app.services.lunarsight.visibility import visibility


def bodies(el=0., sun_az=90., earth_az=270.):
    times = pd.date_range("2026-11-17T00:00:00Z", periods=3, freq="30min")
    sun = pd.DataFrame({"az_deg": sun_az, "el_deg": el, "distance_km": 149597870.7, "row_present": True}, index=times)
    earth = pd.DataFrame({"az_deg": earth_az, "el_deg": el, "distance_km": 384400., "row_present": True}, index=times)
    azimuth = np.arange(0, 360, .25)
    profile = pd.DataFrame({"az_deg": azimuth, "az_step_deg": .25, "horizon_deg": 0., "coverage_complete": True})
    return sun, earth, profile


def test_half_disc_all_mission_is_fifty_percent_and_fails_eighty():
    sun, earth, profile = bodies()
    frame = visibility(sun, earth, profile, profile, solar_disc=True)
    assert frame.sun_state.tolist() == ["V", "V"]  # Some sunlight throughout.
    assert metrics(frame)["total_sun_hours"] == pytest.approx([.5, .5])
    request = MissionRequest(latitude_deg=-89., longitude_e_deg=0., start_utc=sun.index[0].isoformat(), duration_hours=1., min_sunlit_fraction=.8)
    result = evaluate(request, frame, {"passed": False})
    assert result["decision"] == "FAIL"  # A failed validation cannot hide a hard failure.
    assert result["metrics_hours"]["longest_dark_hours"] == [0., 0.]


def test_flat_horizon_matches_analytic_circular_segment():
    sun, earth, profile = bodies()
    radius = np.rad2deg(np.arcsin(SUN_RADIUS_KM/149597870.7))
    for ratio in np.linspace(-1, 1, 31):
        sun["el_deg"] = ratio*radius
        actual = fractions(sun, earth, profile)[0][0]
        expected = (np.arccos(-ratio)+ratio*np.sqrt(1-ratio*ratio))/np.pi
        assert actual == pytest.approx(expected, abs=.0015)


def test_total_partial_eclipse_and_no_eclipse():
    sun, earth, profile = bodies(el=5.)
    assert fractions(sun, earth, profile)[0].tolist() == [1., 1., 1.]
    earth["az_deg"] = 90.
    assert fractions(sun, earth, profile)[1].tolist() == [0., 0., 0.]
    earth["az_deg"] = 90.95
    lo, hi = fractions(sun, earth, profile)
    assert (lo > 0).all() and (hi < 1).all() and np.allclose(lo, hi)


def test_missing_terrain_or_earth_stays_bounded_and_never_invents_sun():
    sun, earth, profile = bodies(el=5.)
    profile["coverage_complete"] = False
    profile["horizon_deg"] = np.nan
    lo, hi = fractions(sun, earth, profile)
    assert lo.tolist() == [0.]*3 and hi.tolist() == [1.]*3
    sun, earth, profile = bodies(el=5.)
    earth["row_present"] = False
    assert fractions(sun, earth, profile)[0].tolist() == [0.]*3
    sun["el_deg"] = -5.
    assert fractions(sun, earth, profile)[1].tolist() == [0.]*3
    sun["row_present"] = False
    assert fractions(sun, earth, profile)[1].tolist() == [1.]*3


def test_azimuth_wrap_and_irregular_time_weighting():
    sun, earth, profile = bodies(sun_az=359.99)
    a = fractions(sun, earth, profile)[0]
    sun["az_deg"] = -.01
    assert np.allclose(fractions(sun, earth, profile)[0], a)
    frame = visibility(sun, earth, profile, profile, solar_disc=True)
    frame["start_utc"] = pd.to_datetime(["2026-11-17T00:00Z", "2026-11-17T00:15Z"])
    frame["end_utc"] = pd.to_datetime(["2026-11-17T00:15Z", "2026-11-17T01:00Z"])
    frame["sun_visible_fraction_lower"] = [0., 1.]
    frame["sun_visible_fraction_upper"] = [0., 1.]
    assert metrics(frame)["total_sun_hours"] == [.75, .75]


class SyntheticEphemeris(SharedEphemeris):
    def identity(self):
        return {"method_version": "synthetic-unit-test-only"}

    def exact(self, times, identity=None):
        # A synthetic linear vector field makes interpolation independently exact.
        x = np.asarray((pd.DatetimeIndex(times)-pd.Timestamp("2026-01-01", tz="UTC")).total_seconds())
        return np.column_stack([x+i for i in range(6)])


def test_shared_month_boundary_and_corrupt_cache_are_explicit(tmp_path):
    provider = SyntheticEphemeris(tmp_path)
    times = pd.to_datetime(["2026-11-30T23:55Z", "2026-12-01T00:00Z", "2026-12-01T00:05Z"])
    vectors, receipts = provider.vectors(times, provider.identity())
    assert np.allclose(vectors, provider.exact(times))
    assert [r["month"] for r in receipts] == ["2026-11-01", "2026-12-01"]
    path = next((tmp_path/"tables").glob("*.npy"))
    path.write_bytes(b"tampered")
    with pytest.raises(DomainError, match="EPHEMERIS_INTEGRITY_FAILED"):
        provider.vectors(times, provider.identity())


def test_missing_kernels_never_fall_back_to_fake_or_clamped_positions(tmp_path):
    with pytest.raises(DomainError, match="EPHEMERIS_NOT_PREPARED"):
        SharedEphemeris(tmp_path).identity()
    assert SharedEphemeris(tmp_path).descriptor()["available"] is False


def test_topocentric_vectors_include_observer_parallax_and_height():
    vector = np.array([[1e8, 0., 0., 384400., 0., 0.]])
    site = {"lon_e_deg": 90., "lat_deg": 0., "dem_z_m": 0.}
    az, el, distance = SharedEphemeris.topocentric(vector, site, 2., 399)
    assert az[0] == pytest.approx(270.)
    assert el[0] == pytest.approx(np.rad2deg(np.arctan2(-1737.402, 384400.)))
    assert distance[0] == pytest.approx(np.hypot(1737.402, 384400.))


def test_far_future_is_not_wrapped_into_another_century(tmp_path):
    class CalendarProbe(SyntheticEphemeris):
        def chunk(self, month, identity):
            assert month == "2500-01-01"
            return np.zeros((32*24+1, 6)), {"month": month}
    values, receipts = CalendarProbe(tmp_path).vectors(pd.to_datetime(["2500-01-15T12:30:00Z"]), {})
    assert values.shape == (1, 6) and receipts[0]["month"] == "2500-01-01"


@pytest.fixture
def disc_pipeline(pipeline, monkeypatch):
    # Keep analytic terrain from the older sphere fixture; control only ephemeris.
    class Ephemeris:
        def identity(self):
            return {"method_version": "synthetic-test-ephemeris"}
        def sample(self, site, target, height, start, end, step):
            index = pd.date_range(start, end, freq=f"{step}min")
            frame = pd.DataFrame({"az_deg": 90. if target == 10 else 270., "el_deg": 0.,
                "row_present": True, "distance_km": 149597870.7 if target == 10 else 384400.}, index=index)
            return frame, {"target": target, "step_minutes": step, "missing_timestamps": 0, "missing_angles": 0,
                "interpolation_validation": {"passed": True, "reference": "synthetic unit test"}}
    pipeline.shared_ephemeris = Ephemeris()
    # Flat horizon through the solar centre gives exactly half a disk.
    original = pipeline.geometry
    def geometry(*args, **kwargs):
        fine, short, seams, receipt = original(*args, **kwargs)
        for profile in [*fine.values(), *short.values()]:
            profile["horizon_deg"] = 0.
        return fine, short, seams, receipt
    monkeypatch.setattr(pipeline, "geometry", geometry)
    # Reference geometry validation is independently covered by sphere tests.
    monkeypatch.setattr("app.point_analysis.pipeline.verify_profiles", lambda *args: {"unit-test": {"passed": True}})
    return pipeline


def test_new_default_disc_point_compare_search_csv_agree(disc_pipeline, tmp_path, monkeypatch):
    request = query(evaluation_policy="hard_first", illumination_model="solar_disc", min_sunlit_fraction=.8)
    result = disc_pipeline.run(request)
    assert result["decision"] == "FAIL" and result["metrics_hours"]["total_sun_hours"] == pytest.approx([.5, .5])
    assert result["illumination"]["mean_visible_fraction_bounds"] == pytest.approx([.5, .5])
    repo = ResultRepository()
    monkeypatch.setattr(repo, "directory", lambda: tmp_path/"planning")
    planner = PlanningService(results=repo, point_pipeline=disc_pipeline)
    query_data = {"targets": [{"latitude_deg": -89.5, "longitude_e_deg": 220.}], "arrival_utc": request.start_utc,
                  "duration_hours": 1., "min_sunlit_fraction": .8}
    assert CompareRequest(**query_data).illumination_model == "solar_disc"
    compared = planner.compare(CompareRequest(**query_data))
    searched = planner.search(SearchRequest(**query_data, until_utc="2026-11-17T00:05:00Z", start_step_minutes=5))
    for candidate in (compared.candidates[0], searched.candidates[0]):
        assert candidate.metrics == result["metrics_hours"] and candidate.decision == "FAIL"
        assert candidate.analysis_result_id == result["result_id"]
        assert candidate.illumination == result["illumination"]
    assert 'solar_disc' in result_csv(compared)


def test_disc_and_legacy_cache_ids_are_separate_and_thresholds_reuse_geometry(disc_pipeline, monkeypatch):
    request = query(illumination_model="solar_disc", min_sunlit_fraction=.8)
    first = disc_pipeline.run(request)
    assert disc_pipeline.identity(request, __import__('test_point_analysis').SyntheticSphere())["solar_disc_method"]
    monkeypatch.setattr("app.point_analysis.pipeline.scan_horizons", lambda *a, **k: pytest.fail("must reuse horizon"))
    second = disc_pipeline.run(query(illumination_model="solar_disc", min_sunlit_fraction=.4))
    assert second["decision"] == "PASS"
    assert first["result_id"] != second["result_id"]
    assert first["provenance"]["geometry"] == second["provenance"]["geometry"]
    legacy = disc_pipeline.run(query(illumination_model="sun_center", min_sunlit_fraction=.4))
    assert legacy["result_id"] not in (first["result_id"], second["result_id"])


def test_validation_override_never_counts_partial_disc_as_a_whole_disc(disc_pipeline, monkeypatch):
    from test_indeterminate_resolution import angular_failure
    angular_failure(monkeypatch, always=True)
    sample = disc_pipeline.shared_ephemeris.sample
    def partial(*args):
        frame, receipt = sample(*args)
        frame["el_deg"] = .05
        return frame, receipt
    monkeypatch.setattr(disc_pipeline.shared_ephemeris, "sample", partial)
    result = disc_pipeline.run(query(illumination_model="solar_disc", min_sunlit_fraction=.5, resolve_indeterminate=True))
    assert result["nominal_sampled_decision"] == "PASS"
    assert result["decision"] == "INDETERMINATE"
    assert result["validation"]["mission_path"]["metrics_hours"]["total_sun_hours"] == [0., 1.]


def test_full_disc_mission_can_pass_without_global_convergence_but_not_without_ephemeris_validation(disc_pipeline, monkeypatch):
    from test_indeterminate_resolution import angular_failure
    angular_failure(monkeypatch, always=True)
    sample = disc_pipeline.shared_ephemeris.sample
    def full(*args):
        frame, receipt = sample(*args)
        frame["el_deg"] = 5.
        return frame, receipt
    monkeypatch.setattr(disc_pipeline.shared_ephemeris, "sample", full)
    result = disc_pipeline.run(query(illumination_model="solar_disc", min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result["decision"] == "PASS" and not result["validation"]["passed"]
    assert result["validation"]["mission_path"]["passed"]
    def unvalidated(*args):
        frame, receipt = full(*args)
        receipt["interpolation_validation"]["passed"] = False
        return frame, receipt
    monkeypatch.setattr(disc_pipeline.shared_ephemeris, "sample", unvalidated)
    result = disc_pipeline.run(query(illumination_model="solar_disc", min_sunlit_fraction=.9, resolve_indeterminate=True))
    assert result["decision"] == "INDETERMINATE"
    assert "SHARED_EPHEMERIS_VALIDATION_FAILED" in result["validation"]["reason_codes"]
