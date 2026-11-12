import pytest

from scripts.materialize_dem_windows import TO_POLAR, parse_point, snapped_bounds


def test_south_pole_projects_to_origin():
    x, y = TO_POLAR.transform(0.0, -90.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_near_window_is_40_km_square_on_grid():
    bounds = snapped_bounds(123.4, -456.7, "near10")
    assert bounds == (-19880.0, -20460.0, 20130.0, 19550.0)


def test_point_parser_normalizes_east_longitude():
    point = parse_point("Connecting Ridge,-89.44,-137.17")
    assert point["lon"] == pytest.approx(222.83)
