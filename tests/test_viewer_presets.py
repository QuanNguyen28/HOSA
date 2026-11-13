"""Viewer heights share the coordinate contract; archived targets remain explicit-only."""
import pytest
from pydantic import ValidationError

from app.assistant.sites import canonical_site_id, coordinate_sites_for_prompt
from app.mission.models import MissionRequest
from app.mission.targets import coordinates_for_site, default_sites


@pytest.mark.parametrize("height", [2., 10., 20., 30.])
def test_viewer_height_is_supported_by_coordinate_request(height):
    request = MissionRequest(latitude_deg=-89., longitude_e_deg=20.,
        start_utc="2026-11-24T00:00:00Z", panel_height_m=height, antenna_height_m=height)
    assert request.panel_height_m == request.antenna_height_m == height


@pytest.mark.parametrize("field", ["panel_height_m", "antenna_height_m"])
def test_viewer_contract_rejects_height_outside_supported_geometry(field):
    with pytest.raises(ValidationError):
        MissionRequest(site_id="haworth", start_utc="2026-11-24T00:00:00Z", **{field: 30.01})


def test_archived_examples_are_removed_from_defaults_but_keep_api_compatibility():
    hidden = {"Site01_P1", "Site04_P1", "example-a", "example-b"}
    assert len(default_sites()) == 27
    assert not hidden & default_sites().keys()
    assert {s["site_id"] for s in coordinate_sites_for_prompt()} == default_sites().keys()
    for site_id in hidden:
        assert set(coordinates_for_site(site_id)) == {"latitude_deg", "longitude_e_deg"}
        assert canonical_site_id(site_id) == site_id
