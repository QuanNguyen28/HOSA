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


def chat_site_ids() -> set[str]:
    """Sites chat may analyse: exactly the 27 listed in Explore/Compare/Best dates."""
    return set(default_sites())


def _site_aliases() -> dict[str, str]:
    """Names, IDs and codes of the 27 tab sites only ("Site01", "site 01", "điểm 01", "R01")."""
    aliases = {}
    for site_id, site in default_sites().items():
        for alias in [site_id, site["name"], *site.get("aliases", [])]:
            aliases[_site_label(alias)] = site_id
            number = re.fullmatch(r"Site(\d+(?:v\d+)?)", alias)
            if number:
                for spelling in (f"Site {number[1]}", f"điểm {number[1]}"):
                    aliases.setdefault(_site_label(spelling), site_id)
    return aliases


def _excluded_aliases() -> dict[str, str]:
    """Known points that are NOT among the 27 tab sites (hidden catalogue entries, P1 observers)."""
    chat = chat_site_ids()
    aliases = {_site_label(alias): site_id for site_id, site in compare_sites().items() if site_id not in chat
               for alias in [site_id, site["name"], *site.get("aliases", [])]}
    for site in available_sites():
        aliases[_site_label(site["site_id"])] = site["site_id"]
    return aliases


def excluded_named_sites(text: str) -> list[str]:
    """Known non-tab points named in text, e.g. 'IM-1' or 'Site01_P1', so chat can say why it cannot use them."""
    normalized = _site_label(text)
    allowed = _site_aliases()
    found = []
    for label, site_id in sorted(_excluded_aliases().items(), key=lambda item: -len(item[0])):
        # Skip labels that are also (part of) a tab-site name, e.g. 'Mons Mouton' inside nothing allowed.
        if label in allowed:
            continue
        if re.search(r"\b" + re.escape(label) + r"\b", normalized):
            found.append(site_id)
            normalized = re.sub(r"\b" + re.escape(label) + r"\b", " ", normalized)
    return list(dict.fromkeys(found))


def site_info(site_id: str) -> dict:
    """Unambiguous label for UI and prose: name, coordinates and what kind of point it is.

    Two catalogue entries can share a region name (Connecting Ridge region centre
    vs the Site01_P1 observer ~0.7 km away) or even coordinates (Leibnitz Beta
    Plateau and its extended-boundary polygon), so a name alone is not enough.
    """
    site = compare_sites().get(site_id)
    if site:
        lat, lon = site["lat"], site["lon"]
        basis = site.get("coordinate_basis") or site.get("kind") or ""
        kind = "region_centre" if "polygon_center" in basis else "landing_site" if site.get("group") == "clps" else "catalog_point"
        name = site["name"]
    else:
        p1 = next((s for s in available_sites() if s["site_id"] == site_id), None)
        if not p1:
            return {"site_id": site_id, "name": site_id, "lat_deg": None, "lon_e_deg": None, "kind": "unknown", "label": site_id}
        lat, lon, kind = p1["lat_deg"], p1["lon_e_deg"], "p1_observer"
        name = f"{site_id} · {p1['region']}"
    lon = ((lon + 180) % 360) - 180
    coords = f"{abs(lat):.4f}°{'S' if lat < 0 else 'N'} {abs(lon):.4f}°{'W' if lon < 0 else 'E'}"
    same_spot = sorted(other for other, item in compare_sites().items() if other != site_id
                       and abs(item["lat"] - lat) < 1e-6 and abs((((item["lon"] + 180) % 360) - 180) - lon) < 1e-6)
    return {"site_id": site_id, "name": name, "lat_deg": lat, "lon_e_deg": lon, "kind": kind,
            "label": f"{name} ({coords})", "same_coordinates_as": same_spot}


def site_display_name(site_id: str) -> str:
    """Human name for prose; P1 observers include their region so they are not mistaken for its centre."""
    return site_info(site_id)["name"]


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
    """Identify one of the 27 tab sites from typed coordinates (within 1 m); never invent a point."""
    matches = []
    for site_id, site in default_sites().items():
        lat, target = radians(point.lat_deg), radians(site["lat"])
        dlon = radians(point.lon_e_deg - site["lon"])
        a = sin((lat-target)/2)**2 + cos(lat)*cos(target)*sin(dlon/2)**2
        distance = 2 * 1737400 * asin(sqrt(min(1, max(0, a))))
        # One metre permits rounded input; this is identification, not a new site.
        if distance <= 1:
            matches.append(site_id)
    if not matches:
        raise AssistantError("UNSUPPORTED_SITE_COORDINATES")
    if len(matches) > 1:
        # e.g. Leibnitz Beta Plateau and its extended-boundary entry share a centre.
        raise AssistantError("AMBIGUOUS_SITE_SELECTION")
    return matches[0]
