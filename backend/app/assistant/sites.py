"""Resolve named targets from the same catalog the Compare interface uses."""
from math import asin, cos, radians, sin, sqrt
import re
import unicodedata

from app.mission.targets import compare_sites, default_sites
from app.services.lunarsight.catalog import site_catalog
from .models import SiteCoordinates
from .provider import AssistantError


def available_sites() -> list[dict]:
    return [{"site_id": f["properties"]["site_id"],
             "region": f["properties"]["region"],
             "lat_deg": f["properties"]["lat_deg"],
             "lon_e_deg": f["properties"]["lon_e_deg"]}
            for f in site_catalog()["features"]]


def coordinate_sites_for_prompt() -> list[dict]:
    return [{"site_id": site_id, "name": site["name"], "aliases": site.get("aliases", [])}
            for site_id, site in default_sites().items()]


def _site_label(text: str) -> str:
    plain = "".join(char for char in unicodedata.normalize("NFKD", text.casefold())
                    if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", plain))


def _site_aliases() -> dict[str, str]:
    aliases = {_site_label(alias): site_id for site_id, site in compare_sites().items()
               for alias in [site_id, site["name"], *site.get("aliases", [])]}
    for site in available_sites():
        site_id = site["site_id"]
        aliases[_site_label(site_id)] = site_id
        aliases[_site_label(f"{site_id} · {site['region']}")] = site_id
        number = re.fullmatch(r"Site(\d+)_P1", site_id)
        if number:
            suffix = number[1]
            for alias in (f"Site{suffix}", f"Site {suffix}", f"điểm {suffix}"):
                aliases[_site_label(alias)] = site_id
    return aliases


def canonical_site_id(label: str) -> str:
    return _site_aliases().get(_site_label(label), label)


def named_sites(text: str) -> list[str]:
    normalized = _site_label(text)
    aliases = _site_aliases()
    if not aliases:
        return []
    # Prefer the full label when one site name is a prefix of another.
    pattern = "|".join(re.escape(label) for label in sorted(aliases, key=len, reverse=True))
    return list(dict.fromkeys(aliases[match[0]] for match in re.finditer(r"\b(?:" + pattern + r")\b", normalized)))


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
