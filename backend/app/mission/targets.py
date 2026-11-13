"""Exact catalog identification; arbitrary coordinates are never snapped to a site."""
import json

from app.core.errors import DomainError
from app.services.lunarsight.catalog import repository_root, site_catalog


def compare_sites() -> dict:
    """Coordinate targets shared by the Compare interface and mission engine."""
    path = repository_root() / "manifests" / "compare-sites.json"
    return {site["id"]: site for site in json.loads(path.read_text(encoding="utf-8"))}


def default_sites() -> dict:
    """Public default selection; archived verification targets stay addressable."""
    return {key: site for key, site in compare_sites().items() if site.get("default_visible", True)}


def coordinates_for_site(site_id):
    catalog = compare_sites()
    site = catalog.get(site_id)
    if site is None and isinstance(site_id, str):
        label = site_id.strip().casefold()
        site = next((candidate for candidate in catalog.values()
                     if label in {value.casefold() for value in
                         [candidate["name"], *candidate.get("aliases", [])]}), None)
    if site:
        return {"latitude_deg": site["lat"], "longitude_e_deg": site["lon"] % 360}
    for feature in site_catalog()["features"]:
        properties = feature["properties"]
        if properties["site_id"] == site_id:
            return {"latitude_deg": properties["lat_deg"], "longitude_e_deg": properties["lon_e_deg"] % 360}
    raise DomainError("UNSUPPORTED_SITE_SCOPE")
