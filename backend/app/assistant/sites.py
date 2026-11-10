"""Resolve coordinates only to processed catalog points, never extrapolate science."""
from math import asin, cos, radians, sin, sqrt

from app.services.lunarsight.catalog import site_catalog
from .models import SiteCoordinates
from .provider import AssistantError


def available_sites() -> list[dict]:
    return [{"site_id": f["properties"]["site_id"],
             "lat_deg": f["properties"]["lat_deg"],
             "lon_e_deg": f["properties"]["lon_e_deg"]}
            for f in site_catalog()["features"]]


def resolve_coordinates(point: SiteCoordinates) -> str:
    matches = []
    for site in available_sites():
        lat, target = radians(point.lat_deg), radians(site["lat_deg"])
        dlon = radians(point.lon_e_deg - site["lon_e_deg"])
        a = sin((lat-target)/2)**2 + cos(lat)*cos(target)*sin(dlon/2)**2
        distance = 2 * 1737400 * asin(sqrt(min(1, max(0, a))))
        # One metre permits rounded input; this is identification, not a new site.
        if distance <= 1:
            matches.append(site["site_id"])
    if len(matches) != 1:
        raise AssistantError("UNSUPPORTED_SITE_COORDINATES")
    return matches[0]
