"""Published observer identity is shared by UI, requests and offline builders."""
import csv
import hashlib
from pathlib import Path

import pytest

from app.assistant.sites import canonical_site_id
from app.mission.targets import coordinates_for_site, default_sites
from app.services.lunarsight.acquire import parallel_ranged_download
from scripts.precompute_catalog import targets


def test_default_catalog_preserves_every_nasa_published_coordinate():
    root = Path(__file__).resolve().parents[1]
    with (root / "manifests/nasa-south-pole-sites.csv").open(newline="") as stream:
        official = {r["source_code"].split(" or ")[-1]: r for r in csv.DictReader(stream)}
    defaults = default_sites()
    assert len(defaults) == len(official) == 27
    assert len(targets()) == 26
    assert {s["source_code"] for s in defaults.values()} == official.keys()
    for site in defaults.values():
        row = official[site["source_code"]]
        assert site["lat"] == float(row["latitude_deg"])
        assert site["lon"] == float(row["longitude_east_deg"])
        assert site["coordinate_basis"] == "published_polygon_center"
        assert canonical_site_id(site["name"]) == site["id"]
        assert canonical_site_id(site["source_code"]) == site["id"]
        assert coordinates_for_site(site["name"]) == coordinates_for_site(site["id"])
        assert coordinates_for_site(site["source_code"]) == coordinates_for_site(site["id"])
    assert coordinates_for_site("leibnitz-beta-plateau") == coordinates_for_site("leibnitz-beta-plateau-extended")
    assert canonical_site_id("Site04") == "shackleton-rim"
    assert canonical_site_id("Site04_P1") == "Site04_P1"


def test_planning_source_identity_tracks_human_named_observers(monkeypatch):
    from app.mission import targets as target_module
    from app.point_analysis import sources as source_module
    from app.planning.models import CompareRequest
    from app.planning.service import PlanningService
    monkeypatch.setattr(source_module, "installed_sources", lambda: [
        {"dataset_id": "synthetic-only", "sha256": "test", "resolution_m": 5}])
    coordinate = {"latitude_deg": -89.7668, "longitude_e_deg": 188.13}
    monkeypatch.setattr(target_module, "coordinates_for_site", lambda label: coordinate.copy())
    query = CompareRequest(site_ids=["Shackleton Rim"], arrival_utc="2026-11-24T00:00:00Z",
                           data_source="coordinate", illumination_model="sun_center", min_sunlit_fraction=.8)
    planner = PlanningService()
    before = planner.source_capabilities(query)["source_hash"]
    coordinate["latitude_deg"] = -89.7
    assert planner.source_capabilities(query)["source_hash"] != before


@pytest.mark.parametrize("bad", [None, "identity", "range", "truncated"])
def test_parallel_nasa_transfer_checks_joined_bytes_and_source_identity(tmp_path, monkeypatch, bad):
    import requests
    body = b"II*\0" + bytes(range(256)) * 20000
    url = "https://pgda.gsfc.nasa.gov/data/test.tif"
    def get(url, headers, **kwargs):
        first, last = map(int, headers["Range"].removeprefix("bytes=").split("-"))
        last = min(last, len(body)-1)
        response = requests.Response()
        response.status_code = 206
        response.url = url
        response.headers.update({"Content-Range": f"bytes {first}-{last}/{len(body)}", "ETag": "fixed"})
        response._content = body[first:last+1]
        if last > 0 and bad == "identity": response.headers["ETag"] = "changed"
        if last > 0 and bad == "range": response.headers["Content-Range"] = f"bytes {first+1}-{last}/{len(body)}"
        if last > 0 and bad == "truncated": response._content = response._content[:-1]
        return response
    monkeypatch.setattr(requests, "get", get)
    path = tmp_path / "test.part"
    if bad:
        with pytest.raises(ValueError): parallel_ranged_download(url, path, 6_000_000, 3)
    else:
        receipt = parallel_ranged_download(url, path, 6_000_000, 3)
        assert path.read_bytes() == body
        assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
        assert receipt["bytes"] == len(body)
