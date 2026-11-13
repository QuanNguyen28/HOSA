#!/usr/bin/env python3
"""Use NASA's published polygon centres as the named default observer catalog.

Source: ACD-50044 Revision A, Table A2-2, pages 57–58. Coordinates are
preserved at the published precision; no highest-point search or snapping.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "manifests/nasa-south-pole-sites.csv"
CATALOG = ROOT / "manifests/compare-sites.json"


def nasa_sites(source=SOURCE):
    with Path(source).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    result = []
    for row in rows:
        code = row["source_code"].split(" or ")[-1]
        name = row["name"]
        if code in {"Haworth", "Shoemaker"}:
            name = code
        if code == "Site20v2":
            name = "Leibnitz Beta Plateau (extended boundaries)"
        site_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        site_id = {"Site20v2": "leibnitz-beta-plateau-extended", "Site42": "de-gerlache-kocher",
                   "NPC": "idelson-l-crater-1"}.get(code, site_id)
        result.append({
            "id": site_id, "name": name, "group": "nasa", "kind": "exact",
            "lat": float(row["latitude_deg"]), "lon": float(row["longitude_east_deg"]),
            "point": "Centre of the original region polygon, published by NASA in Table A2-2; not an optimized landing point.",
            "source": "NASA Lunar Surface Data Book, ACD-50044 Revision A, Table A2-2",
            "url": row["source_url"] + "#page=" + row["source_page"],
            "source_code": code, "source_page": int(row["source_page"]),
            "coordinate_basis": "published_polygon_center",
            "location_group": "leibnitz-beta-plateau" if code in {"Site20", "Site20v2"} else site_id,
            "aliases": [code, *([row["source_code"].split(" or ")[0]] if " or " in row["source_code"] else [])],
        })
    # Preserve the familiar first two choices while keeping all source entries.
    order = ["Site01", "Site04", "Site06", "Site07", "Site11", "Site20", "Site20v2", "Site23", "Site42",
             "Haworth", "Shoemaker", "DM1", "DM2", "SL2", "SL3", "NPA", "NPB", "NPC", "NPD",
             *[f"LM{i}" for i in range(1, 9)]]
    assert len(result) == len({s["id"] for s in result}) == 27
    assert {s["source_code"] for s in result} == set(order)
    return sorted(result, key=lambda site: order.index(site["source_code"]))


def build():
    defaults = nasa_sites()
    old = json.loads(CATALOG.read_text())
    ids = {site["id"] for site in defaults}
    # Old mission/example targets remain explicitly addressable, outside defaults.
    archived = [{**site, "default_visible": False} for site in old if site["id"] not in ids]
    CATALOG.write_text(json.dumps(defaults + archived, ensure_ascii=False, indent=2) + "\n")
    print(f"Published {len(defaults)} named defaults, 26 coordinates; retained {len(archived)} archived targets.")


if __name__ == "__main__":
    build()
