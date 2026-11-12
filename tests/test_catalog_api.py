from pathlib import Path
import math
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1] / "backend"
RAW_SITE01 = Path(__file__).resolve().parents[1] / "data/raw/Site01/Site01_final_adj_5mpp_surf.tif"
RAW_DEM80 = Path(__file__).resolve().parents[1] / "data/raw/global/LDEM_80S_80MPP_ADJ.TIF"
sys.path.insert(0, str(BACKEND))

from app.services.lunarsight.catalog import (  # noqa: E402
    coverage_summary,
    site_analysis,
    site_catalog,
    site_timeline,
)
from app.services.lunarsight.point import (  # noqa: E402
    sample_terrain,
    south_polar_cap,
    terrain_sources,
    terrain_window,
)
from app.services.lunarsight.planning import (  # noqa: E402
    analyze_request,
    load_result,
    result_csv,
    scenarios,
    site_profile,
)

_SOURCES = {source["dataset_id"]: source["path"] for source in terrain_sources()}
RAW_SITE01 = _SOURCES["Site01_dem"]
RAW_SITE06 = _SOURCES["Site06_dem"]
RAW_DEM80 = _SOURCES["dem80"]


def test_site_catalog_has_versioned_provenance():
    catalog = site_catalog()
    assert catalog["type"] == "FeatureCollection"
    assert {feature["id"] for feature in catalog["features"]} == {
        "Site01_P1",
        "Site04_P1",
    }
    assert catalog["provenance"]["dataset_version"] == "v0.3.0"


def test_timeline_is_bounded_and_preserves_state_codes():
    timeline = site_timeline("Site01_P1", max_points=48)
    assert 1 <= len(timeline["points"]) <= 48
    assert timeline["original_interval_count"] > len(timeline["points"])
    assert {point["joint_state"] for point in timeline["points"]} <= {"V", "B", "?"}


def test_coverage_separates_visualization_from_science():
    coverage = coverage_summary()
    assert coverage["global_visualization"]["scientific_analysis"] is False
    assert coverage["analysis"]["scientific_analysis"] is True
    sources = {item["dataset_id"]: item for item in coverage["terrain_sampling"]}
    assert sources["Site01_dem"]["available"] is True
    assert sources["Site01_dem"]["resolution_m"] == 5


def test_site_analysis_uses_native_interval_and_versioned_window():
    analysis = site_analysis("Site01_P1", "2026-11-14T00:00:00Z")
    assert analysis["availability"] == "AVAILABLE"
    assert analysis["scenario_status"] == "PROVISIONAL"
    assert analysis["instant"]["sun"]["state"] in {"V", "B", "?"}
    assert analysis["instant"]["earth"]["state"] in {"V", "B", "?"}
    assert analysis["window_72h"]["decision"] in {"PASS", "FAIL", "INDETERMINATE"}
    assert analysis["window_72h"]["requirements"] == {"min_sunlit_fraction": .8, "min_earth_los_fraction": .8}


def test_site_analysis_refuses_to_extrapolate():
    analysis = site_analysis("Site04_P1", "2030-01-01T00:00:00Z")
    assert analysis["availability"] == "OUTSIDE_EPHEMERIS_RANGE"
    assert "instant" not in analysis


def test_site_analysis_does_not_substitute_nearest_window():
    analysis = site_analysis("Site01_P1", "2026-11-14T00:07:00Z")
    assert analysis["availability"] == "AVAILABLE"
    assert analysis["instant"]["start_utc"] == "2026-11-14T00:05:00Z"
    assert analysis["window_72h"] is None
    assert any("not an exact 15-minute" in warning for warning in analysis["warnings"])


@pytest.mark.skipif(not RAW_SITE01.is_file(), reason="optional raw Site01 DEM is not installed")
def test_point_terrain_uses_best_local_dem_and_refuses_unknown():
    covered = sample_terrain(-89.43892646479243, -137.0959780737777)
    assert covered["coverage_status"] == "COVERED"
    assert covered["terrain"]["dataset_id"] == "Site01_dem"
    assert covered["terrain"]["resolution_m"] == 5
    assert abs(covered["terrain"]["elevation_m"] - 1958.3211669921875) < 1e-6
    assert covered["terrain"]["slope_deg"] is not None
    assert covered["terrain"]["local_3x3_roughness_m"] is not None
    if covered["terrain"]["quality"] is not None:
        assert covered["terrain"]["quality"]["rms_error_m"] > 0
        assert covered["terrain"]["quality"]["lola_spot_count"] == 0

    unknown = sample_terrain(20.0, 20.0)
    assert unknown["coverage_status"] == "UNKNOWN"
    assert unknown["terrain"] is None


@pytest.mark.skipif(not RAW_SITE01.is_file(), reason="optional raw Site01 DEM is not installed")
def test_terrain_window_is_bounded_and_keeps_native_provenance():
    result = terrain_window(-89.43892646479243, -137.0959780737777, 1.0, 65)
    assert result["coverage_status"] == "COVERED"
    assert result["dataset_id"] == "Site01_dem"
    assert result["native_resolution_m"] == 5
    assert result["grid"]["rows"] == 65
    assert len(result["grid"]["elevation_m_row_major"]) == 65 * 65
    assert result["grid"]["valid_fraction"] > 0.99
    assert result["geometry"]["horizontal_scale"] == 1.0
    assert result["geometry"]["vertical_scale"] == 1.0
    assert result["geometry"]["lunar_reference_radius_m"] == 1_737_400.0
    assert math.isfinite(result["geometry"]["center_elevation_m"])
    assert math.isfinite(result["geometry"]["center_x_m"])
    assert math.isfinite(result["geometry"]["center_y_m"])
    assert result["geometry"]["projection"] == "spherical south polar stereographic"
    assert 0 <= result["geometry"]["column_azimuth_deg"] < 360
    assert 0 <= result["geometry"]["row_azimuth_deg"] < 360


@pytest.mark.skipif(not RAW_DEM80.is_file(), reason="optional south-polar DEM is not installed")
def test_regional_terrain_window_uses_continuous_south_polar_dem():
    result = terrain_window(
        -89.43892646479243,
        -137.0959780737777,
        12.0,
        65,
        "regional",
    )
    assert result["coverage_status"] == "COVERED"
    assert result["dataset_id"] == "dem80"
    assert result["native_resolution_m"] == 80
    assert result["detail"] == "regional"
    assert result["grid"]["valid_fraction"] > 0.99


@pytest.mark.skipif(not RAW_DEM80.is_file(), reason="optional south-polar DEM is not installed")
def test_south_polar_cap_preserves_projection_and_site_footprints():
    result = south_polar_cap(257)
    assert result["coverage_status"] == "COVERED"
    assert result["dataset_id"] == "dem80"
    assert result["latitude_limit_deg"] == -80.0
    assert result["grid"]["rows"] == 257
    assert len(result["grid"]["elevation_m_row_major"]) == 257 * 257
    assert result["grid"]["valid_fraction"] > 0.75
    assert result["projection"]["bounds_xy_m"] == [-304000.0, -304000.0, 304000.0, 304000.0]
    if RAW_SITE01.is_file():
        site01 = next(item for item in result["site_footprints"] if item["site_id"] == "Site01")
        assert site01["native_resolution_m"] == 5
        assert len(site01["ring_lon_lat"]) == 5


@pytest.mark.skipif(not RAW_DEM80.is_file(), reason="optional south-polar DEM is not installed")
def test_south_polar_dem_covers_arbitrary_point_at_80m():
    result = sample_terrain(-85.0, 0.0)
    assert result["coverage_status"] == "COVERED"
    assert result["terrain"]["dataset_id"] == "dem80"
    assert result["terrain"]["resolution_m"] == 80
    assert result["terrain"]["quality"]["rms_error_m"] >= 0
    assert result["terrain"]["quality"]["effective_resolution_m"] > 0


@pytest.mark.skipif(not RAW_SITE06.is_file(), reason="optional raw Site06 DEM is not installed")
def test_new_pgda_site_prefers_downloaded_five_metre_dem():
    result = sample_terrain(-85.43810048, 37.36666941)
    assert result["coverage_status"] == "COVERED"
    assert result["terrain"]["dataset_id"] == "Site06_dem"
    assert result["terrain"]["resolution_m"] == 5
    assert result["terrain"]["quality"] is not None


def test_scenario_contract_preserves_fixed_grid_and_heights():
    result = scenarios()
    scenario = result["scenarios"][0]
    assert scenario["scenario_id"] == "south_pole_demo_v1"
    assert scenario["D_hours"] == 72
    assert scenario["start_count"] == 1344
    assert scenario["device_heights_m"] == {"sun_panel": 1, "earth_antenna": 2}


def test_profile_returns_complete_native_horizon():
    profile = site_profile("Site01_P1", "sun")
    assert profile["observer_height_m"] == 1
    assert profile["azimuth_step_deg"] == 0.25
    assert profile["coverage_complete"] is True
    assert len(profile["points"]) == 1440
    assert profile["points"][0]["azimuth_deg"] == 0


def test_exact_analysis_is_reproducible_and_exportable():
    payload = {
        "scenario_id": "south_pole_demo_v1",
        "site_ids": ["Site01_P1", "Site04_P1"],
        "start_index": 0,
        "min_sunlit_fraction": 0.8,
        "min_earth_los_fraction": 0.8,
        "constraints": {
            "max_darkness_hours": 12,
            "max_earth_blackout_hours": 6,
        },
        "scan_grid": True,
    }
    result = analyze_request(payload)
    assert result["overall_decision"] == "FAIL"
    assert {site["site_id"] for site in result["sites"]} == {"Site01_P1", "Site04_P1"}
    assert all(site["start_utc"] == "2026-11-14T00:00:00Z" for site in result["sites"])
    assert all(site["events"] for site in result["sites"])
    assert all(site["constraint_states"]["min_earth_los_fraction"] == "FAIL" for site in result["sites"])
    assert all(site["decisive_event"] is None for site in result["sites"])
    assert all(site["sensitivity"]["status"] == "STABLE_DECISION" for site in result["sites"])
    assert result["sites"][1]["sensitivity"]["max_duration_difference_minutes"] <= 2.01
    assert sum(result["grid_summary"]["Site01_P1"]["counts"].values()) == 1344

    restored = load_result(result["result_id"])
    assert restored == result
    exported = result_csv(result)
    assert exported.count("\n") == 3
    assert "Site01_P1" in exported and "Site04_P1" in exported


@pytest.mark.parametrize(
    "patch",
    [
        {"start_index": 0.5},
        {"start_index": 1344},
        {"constraints": {"max_darkness_hours": 12, "max_earth_blackout_hours": float("nan")}},
        {"site_ids": ["Site99"]},
        {"D_hours": 48},
        {"panel_height_m": 5},
        {"constraints": {"max_darkness_hours": 12, "max_earth_blackout_hours": 6, "score": 1}},
    ],
)
def test_analysis_rejects_unsupported_configuration(patch):
    payload = {
        "scenario_id": "south_pole_demo_v1",
        "site_ids": ["Site01_P1"],
        "start_index": 0,
        "constraints": {
            "max_darkness_hours": 12,
            "max_earth_blackout_hours": 6,
        },
    }
    payload.update(patch)
    with pytest.raises(ValueError, match="UNSUPPORTED_CONFIG"):
        analyze_request(payload)
