from pathlib import Path

import pytest

from scripts.acquire_full_product_data import (
    load_manifest,
    selected_datasets,
    validate_payload,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests/lunarsight/full_product_sources.json"


def test_manifest_is_valid_and_uses_official_hosts():
    manifest = load_manifest(MANIFEST)
    ids = {item["id"] for item in manifest["datasets"]}
    assert "spice_de440s" in ids
    assert "lola_dem_83s_10m" in ids
    assert "pgda_earth_visibility_85s_60m" in ids


def test_core_selects_windowed_and_download_sources():
    manifest = load_manifest(MANIFEST)
    selected = selected_datasets(manifest, {"core"}, set())
    modes = {item["access_mode"] for item in selected}
    assert modes == {"download", "windowed_cog"}


def test_only_rejects_unknown_id():
    manifest = load_manifest(MANIFEST)
    with pytest.raises(ValueError, match="Unknown dataset"):
        selected_datasets(manifest, {"core"}, {"not-a-dataset"})


def test_payload_validation_rejects_html_disguised_as_tiff(tmp_path):
    payload = tmp_path / "bad.tif"
    payload.write_text("<!DOCTYPE html><title>Not Found</title>", encoding="utf-8")
    with pytest.raises(ValueError, match="HTML error payload"):
        validate_payload(payload, {"id": "bad", "media_type": "image/tiff"})


def test_payload_validation_rejects_api_error_json(tmp_path):
    payload = tmp_path / "bad.json"
    payload.write_text('{"error": {"message": "service unavailable"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Upstream API error"):
        validate_payload(payload, {"id": "bad", "media_type": "application/json"})
