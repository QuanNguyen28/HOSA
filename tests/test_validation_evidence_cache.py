"""Numerical evidence reuse must recheck thresholds, contacts and provenance."""
import json

import pytest

from test_point_analysis import pipeline, query
from test_solar_disc import disc_pipeline
from app.core.errors import DomainError


@pytest.fixture
def cached_disc(disc_pipeline, monkeypatch):
    provider = disc_pipeline.shared_ephemeris
    sample = provider.sample
    def with_source(*args, **kwargs):
        frame, receipt = sample(*args, **kwargs)
        if args[1] == 399:
            frame["el_deg"] = 5.  # Explicit synthetic Earth LOS above flat horizon.
        return frame, {**receipt, "identity": provider.identity()}
    monkeypatch.setattr(provider, "sample", with_source)
    return disc_pipeline


def request(**changes):
    return query(illumination_model="solar_disc", min_sunlit_fraction=.4,
                 contact_requirements={"min_contact_minutes": 30.}, **changes)


def test_changed_thresholds_reuse_evidence_without_ephemeris_or_visibility(cached_disc, monkeypatch):
    first = cached_disc.run(request())
    assert first["decision"] == "PASS"
    assert not first["execution"]["validation_evidence_cache_hit"]
    monkeypatch.setattr(cached_disc, "ephemerides", lambda *a, **k: pytest.fail("Recomputed astronomy for new threshold"))
    monkeypatch.setattr(cached_disc, "visible", lambda *a, **k: pytest.fail("Recomputed visibility for new threshold"))
    # Use the same inputs but stricter sunlight; a cached PASS must not leak.
    stricter = request().model_copy(update={"min_sunlit_fraction": .6})
    second = cached_disc.run(stricter)
    assert second["decision"] == "FAIL"
    assert second["execution"]["validation_evidence_cache_hit"]
    assert second["metrics_hours"] == first["metrics_hours"]
    # Contact checks must also be computed using the new request, including
    # each cached alternative's lossless Earth-state runs.
    contact = request().model_dump()
    contact["contact_requirements"] = {"min_contact_minutes": 70.}
    third = cached_disc.run(type(stricter).model_validate(contact))
    assert third["decision"] == "FAIL"
    for diagnostic in third["validation"]["sensitivity"].values():
        assert diagnostic["constraint_checks"]["contact.min_contact_minutes"] == "FAIL"
    assert len({r["result_id"] for r in (first, second, third)}) == 3
    evidence = json.loads(next(cached_disc.validation_evidence.root.glob("*/evidence.json")).read_text())
    assert "decision" not in json.dumps(evidence) and "constraint_checks" not in json.dumps(evidence)


def test_source_and_time_changes_invalidate_numerical_evidence(cached_disc, monkeypatch):
    first = cached_disc.run(request())
    old = cached_disc.shared_ephemeris.identity
    monkeypatch.setattr(cached_disc.shared_ephemeris, "identity", lambda: {**old(), "kernel_revision": "new"})
    changed = cached_disc.run(request())
    assert changed["result_id"] != first["result_id"]
    assert not changed["execution"]["validation_evidence_cache_hit"]
    other_window = request().model_dump(exclude={"end_utc", "duration_hours"})
    other_window["start_utc"] = "2026-11-18T00:00:00Z"
    other_window["duration_hours"] = 1.
    shifted = cached_disc.run(type(request()).model_validate(other_window))
    assert not shifted["execution"]["validation_evidence_cache_hit"]


def test_corrupt_numerical_evidence_is_never_trusted(cached_disc):
    cached_disc.run(request())
    next(cached_disc.validation_evidence.root.glob("*/evidence.json")).write_text("{}")
    changed = request().model_copy(update={"min_sunlit_fraction": .45})
    with pytest.raises(DomainError, match="VALIDATION_EVIDENCE_INTEGRITY_FAILED"):
        cached_disc.run(changed)


def test_mission_path_bounds_are_reused_but_live_seam_gate_is_never_bypassed(cached_disc, monkeypatch):
    from test_indeterminate_resolution import angular_failure
    angular_failure(monkeypatch, always=True)
    provider = cached_disc.shared_ephemeris
    sample = provider.sample
    def full_sun(*args, **kwargs):
        frame, receipt = sample(*args, **kwargs)
        frame["el_deg"] = 5.
        return frame, receipt
    monkeypatch.setattr(provider, "sample", full_sun)
    first = cached_disc.run(request().model_copy(update={"resolve_indeterminate": True}))
    assert first["decision"] == "PASS" and first["validation"]["mission_path"]["passed"]
    monkeypatch.setattr(cached_disc, "ephemerides", lambda *a, **k: pytest.fail("Recomputed ephemeris for saved envelope"))
    monkeypatch.setattr("app.mission.mission_path.path_evidence", lambda *a, **k: pytest.fail("Recomputed saved envelope"))
    second = cached_disc.run(request().model_copy(update={"resolve_indeterminate": True, "min_sunlit_fraction": .8}))
    assert second["decision"] == "PASS"
    assert second["execution"]["validation_evidence_cache_hit"]
    assert second["execution"]["mission_path_evidence_cache_hit"]
    geometry = cached_disc.geometry
    def failed_seam(*args, **kwargs):
        fine, short, _, receipt = geometry(*args, **kwargs)
        return fine, short, [{"passed": False}], receipt
    monkeypatch.setattr(cached_disc, "geometry", failed_seam)
    third = cached_disc.run(request().model_copy(update={"resolve_indeterminate": True, "min_sunlit_fraction": .7}))
    assert third["decision"] == "INDETERMINATE"
    assert "DEM_SEAM_FAILED" in third["validation"]["reason_codes"]
    assert not third["validation"]["mission_path"]["passed"]
