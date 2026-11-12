import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"backend"))
from app.planning.metrics import assess, assess_soft
from app.planning.models import Candidate, CompareRequest, Constraints, SearchRequest
from app.planning.ranking import display_key
from app.planning.repository import ResultRepository, result_csv
from app.planning.service import PlanningService
from app.services.lunarsight import planning as legacy
from app.services.lunarsight.durations import bounds
from scripts import planning_cli


@pytest.fixture
def planner(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "_result_dir", lambda: tmp_path/"legacy")
    results = ResultRepository()
    monkeypatch.setattr(results, "directory", lambda: tmp_path/"results")
    return PlanningService(results=results)


def request(**updates):
    return CompareRequest(**{"illumination_model": "sun_center", "scenario_id": "south_pole_demo_v1", "site_ids": ["Site01_P1"],
        "arrival_utc": "2026-11-14T00:00:00Z", "min_sunlit_fraction": 0.8, "min_earth_los_fraction": 0.1,
        "constraints": Constraints(max_darkness_hours=0, max_earth_blackout_hours=1), **updates})


def test_unknown_earth_duration_bounds_and_hard_threshold_equality():
    metrics = bounds(list("VVVV"), list("V?BV"), [.5, 1.5, 2.25, .75])
    assert metrics["total_earth_los_hours"] == [1.25, 2.75]
    assert assess(metrics, Constraints(), 1, .25, duration=5)[0] == "PASS"
    assert assess(metrics, Constraints(), 1, .5, duration=5)[0] == "INDETERMINATE"
    assert assess(metrics, Constraints(), 1, .6, duration=5)[0] == "FAIL"


def test_all_nine_states_earth_total_and_joint_bounds():
    for sun in "VB?":
        for earth in "VB?":
            values = bounds([sun], [earth], [2.])
            assert values["total_earth_los_hours"] == [2. if earth == "V" else 0., 0. if earth == "B" else 2.]


def test_soft_failure_and_unknown_do_not_override_hard_pass():
    metrics = bounds(list("VV"), list("V?"), [36., 36.])
    decision, checks, violations = assess(metrics, Constraints(max_earth_blackout_hours=0), 1, .5)
    assert decision == "PASS" and not violations and set(checks) == {"min_sunlit_fraction", "min_earth_los_fraction"}
    assert assess_soft(metrics, Constraints(max_earth_blackout_hours=0))[0]["max_earth_blackout_hours"] == "INDETERMINATE"


def test_real_soft_violation_is_independent_of_validation_gate(planner):
    result = planner.compare(request())
    candidate = result.candidates[0]
    assert result.status == "INSUFFICIENT_DATA" and not result.apply_allowed
    assert candidate.nominal_sampled_decision == "PASS" and candidate.decision == "INDETERMINATE"
    assert candidate.soft_constraint_states["max_earth_blackout_hours"] == "FAIL"
    assert not candidate.violations and candidate.soft_violations
    assert candidate.metrics["total_earth_los_hours"] == pytest.approx([11.25, 11.25])
    row = next(csv.DictReader(io.StringIO(result_csv(result))))
    assert json.loads(row["soft_constraint_states_json"])["max_earth_blackout_hours"] == "FAIL"
    assert float(row["min_earth_los_fraction"]) == .1


def test_main_failure_cannot_be_rescued_by_relaxing_soft_preferences(planner):
    base = request().model_dump()
    base.update(min_earth_los_fraction=.8, constraints=Constraints(max_earth_blackout_hours=72))
    result = planner.compare(CompareRequest(**base))
    candidate = result.candidates[0]
    assert not result.apply_allowed and candidate.nominal_sampled_decision == "FAIL"
    assert candidate.decision == "FAIL"
    assert candidate.validation["passed"] is False
    assert candidate.soft_constraint_states["max_earth_blackout_hours"] == "PASS"
    assert [v["constraint"] for v in candidate.violations] == ["min_earth_los_fraction"]


def test_optional_soft_preferences_can_be_omitted(planner):
    payload = request().model_dump(exclude={"constraints"})
    candidate = planner.compare(CompareRequest(**payload)).candidates[0]
    assert candidate.nominal_sampled_decision == "PASS" and candidate.soft_constraint_states == {} and candidate.soft_violations == []


@pytest.mark.parametrize("missing", ["min_sunlit_fraction", "min_earth_los_fraction"])
def test_each_hard_requirement_can_be_omitted_in_shared_contract(missing):
    payload = request().model_dump()
    payload.pop(missing)
    parsed = CompareRequest(**payload)
    assert getattr(parsed, missing) is None
    legacy_payload = dict(scenario_id="south_pole_demo_v1", site_ids=["Site01_P1"], start_index=0,
        min_sunlit_fraction=.8, min_earth_los_fraction=.1)
    legacy_payload.pop(missing)
    with pytest.raises(ValueError, match=missing):
        legacy.analyze_request(legacy_payload)


def test_primary_metric_precedes_soft_tie_break():
    def item(site, los, soft):
        return Candidate(site_id=site, decision="PASS", metrics={"total_earth_los_hours": [los, los]},
            constraint_states={}, soft_constraint_states={"max_earth_blackout_hours": soft}, decisive_event=None, provenance={})
    better = item("A", 60, "FAIL")
    lesser = item("B", 59, "PASS")
    tie = item("C", 60, "PASS")
    assert display_key(better, "total_earth_los_hours") < display_key(lesser, "total_earth_los_hours")
    assert display_key(tie, "total_earth_los_hours") < display_key(better, "total_earth_los_hours")


def test_soft_sensitivity_change_does_not_claim_hard_decision_changed(planner):
    payload = request().model_dump()
    payload.update(site_ids=["Site04_P1"], min_earth_los_fraction=.01,
                   constraints=Constraints(max_earth_blackout_hours=71.15))
    candidate = planner.compare(CompareRequest(**payload)).candidates[0]
    assert candidate.nominal_sampled_decision == "PASS"
    assert candidate.sensitivity["status"] == "NOT_EVALUATED"
    assert candidate.sensitivity["comparisons"]["time_5min_vs_1min"]["status"] == "STABLE_DECISION"
    assert candidate.sensitivity["soft_preferences_changed"] is True
    comparison = candidate.sensitivity["comparisons"]["time_5min_vs_1min"]
    assert comparison["baseline"]["soft_constraint_states"]["max_earth_blackout_hours"] == "FAIL"
    assert comparison["alternative"]["soft_constraint_states"]["max_earth_blackout_hours"] == "PASS"


def test_search_preserves_soft_violations_without_filtering_passes(planner):
    result = planner.search(SearchRequest(**request().model_dump(), until_utc="2026-11-14T00:15:00Z"))
    assert result.coverage["indeterminate"] == 1 and not result.candidates
    assert planner.compare(request()).candidates[0].soft_violations


def test_cli_requires_both_main_inputs_and_accepts_no_soft_limits(planner, capsys):
    args = ["compare", "--illumination-model", "sun_center", "--sites", "Site01_P1", "--arrival", "2026-11-14T00:00:00Z", "--min-sunlit-fraction", ".8"]
    assert planning_cli.main(args, service=planner) == 2
    assert "min_earth_los_fraction" in capsys.readouterr().err
    assert planning_cli.main([*args, "--min-earth-los-fraction", ".1"], service=planner) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["nominal_sampled_decision"] == "PASS"
    assert payload["candidates"][0]["decision"] == "INDETERMINATE"
    assert not payload["candidates"][0]["soft_constraint_states"]


def test_new_snapshot_preserves_all_source_bytes_and_documents_outputs():
    receipt = json.loads((ROOT/"data/processed/lunarsight/v0.3.0/derivation.json").read_text())
    for path, sha in {**receipt["inputs"], **receipt["outputs"]}.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == sha
