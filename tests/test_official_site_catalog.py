import json
from pathlib import Path

from scripts.build_official_site_catalog import build_catalog


def test_build_catalog_marks_centroid_as_unassessed(tmp_path: Path):
    source = tmp_path / "regions.json"
    source.write_text(
        json.dumps(
            {
                "features": [
                    {
                        "attributes": {"FID": 7, "label": "Test Region"},
                        "geometry": {
                            "rings": [
                                [[-1000, -1000], [1000, -1000], [1000, 1000], [-1000, 1000], [-1000, -1000]]
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog = build_catalog(source)
    feature = catalog["features"][0]
    assert feature["properties"]["assessment_status"] == "UNASSESSED_REGION_CENTROID"
    assert feature["properties"]["anchor_latitude_deg"] == -90.0
    assert feature["id"] == "artemis-07-test-region"
