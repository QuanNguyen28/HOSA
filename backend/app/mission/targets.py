"""Exact catalog identification; arbitrary coordinates are never snapped to a site."""
from app.core.errors import DomainError
from app.services.lunarsight.catalog import site_catalog


def coordinates_for_site(site_id):
    for feature in site_catalog()["features"]:
        properties = feature["properties"]
        if properties["site_id"] == site_id:
            return {"latitude_deg": properties["lat_deg"], "longitude_e_deg": properties["lon_e_deg"] % 360}
    raise DomainError("UNSUPPORTED_SITE_SCOPE")
