import csv
import io
import json
from pathlib import Path
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"backend"))

from app.planning.models import CompareRequest, Constraints, SearchRequest
from app.planning.repository import ResultRepository
from app.planning.service import PlanningService
from app.services.lunarsight import planning as legacy
from app.services.lunarsight import sensitivity
from app.mission import snapshot
from app.services.lunarsight.durations import bounds
from app.planning.metrics import assess_soft
from scripts import planning_cli


@pytest.fixture
def planner(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "_result_dir", lambda: tmp_path/"legacy")
    results = ResultRepository()
    monkeypatch.setattr(results, "directory", lambda: tmp_path/"results")
    return PlanningService(results=results)


def query(**updates):
    return CompareRequest(**{"scenario_id": "south_pole_demo_v1", "site_ids": ["Site04_P1"],
        "arrival_utc": "2026-11-14T00:00:00Z",
        "min_sunlit_fraction": 0.8, "min_earth_los_fraction": (72-71.15)/72,
        "constraints": Constraints(max_darkness_hours=12, max_earth_blackout_hours=71.15), **updates})


def test_sensitivity_reassesses_user_threshold_against_real_one_minute_data(planner):
    candidate = planner.compare(query()).candidates[0]
    assert candidate.nominal_sampled_decision == "FAIL" and candidate.decision == "INDETERMINATE"
    sensitivity = candidate.sensitivity
    assert sensitivity["status"] == "REVIEW" and sensitivity["time_sensitive"] is True
    time = sensitivity["comparisons"]["time_5min_vs_1min"]
    assert time["baseline"]["decision"] == "FAIL" and time["alternative"]["decision"] == "PASS"
    assert time["baseline"]["metrics"]["longest_blackout_hours"][0] == pytest.approx(71+10/60)
    assert time["alternative"]["metrics"]["longest_blackout_hours"][0] == pytest.approx(71+8/60)
    assert sensitivity["max_event_shift_minutes"] == 2
    assert sensitivity["scope"]["constraints"]["max_earth_blackout_hours"] == 71.15
    # The same physical samples support a stable decision for another user limit.
    relaxed = planner.compare(query(min_earth_los_fraction=0))
    assert relaxed.candidates[0].sensitivity["status"] == "NOT_EVALUATED"
    assert relaxed.candidates[0].sensitivity["comparisons"]["time_5min_vs_1min"]["status"] == "STABLE_DECISION"
    assert relaxed.result_id != planner.compare(query()).result_id


def test_sensitivity_uses_exact_date_and_never_reuses_another_window(planner):
    result = planner.compare(query(arrival_utc="2026-11-17T00:00:00Z"))
    summary = result.candidates[0].sensitivity
    assert summary["status"] == "NOT_EVALUATED"
    assert summary["comparisons"]["time_5min_vs_1min"]["reason"] == "COMPARISON_WINDOW_NOT_COVERED"
    assert summary["scope"]["start_utc"] == "2026-11-17T00:00:00Z"
    assert summary["max_duration_difference_minutes"] is None


def test_sensitivity_receives_timezone_minimum_sun_and_fixed_hardware(planner):
    result = planner.compare(query(arrival_utc="2026-11-14T07:00:00+07:00", min_sunlit_fraction=1,
        hardware={"sun_panel": 1., "earth_antenna": 2.}))
    summary = result.candidates[0].sensitivity
    assert summary["scope"]["start_utc"] == "2026-11-14T00:00:00Z"
    assert summary["scope"]["min_sunlit_fraction"] == 1
    assert summary["scope"]["device_heights_m"] == {"sun_panel": 1, "earth_antenna": 2}
    assert summary["comparisons"]["time_5min_vs_1min"]["alternative"]["constraint_states"]["min_sunlit_fraction"] == "PASS"


def test_search_does_not_return_unvalidated_starts(planner):
    result = planner.search(SearchRequest(**query(min_earth_los_fraction=0).model_dump(), until_utc="2026-11-14T00:30:00Z", max_results=2,
                                         non_overlapping=False))
    assert result.candidates == [] and result.coverage['indeterminate'] == 2
    assert result.recommended_candidate_id is None


def test_constraint_change_is_visible_even_if_overall_decision_stays_fail(planner, monkeypatch):
    original = snapshot.visibility
    def changed(*args):
        frame = original(*args)
        frame.loc[frame.index[:60], 'sun_state'] = 'B'
        return frame
    monkeypatch.setattr(snapshot, 'visibility', changed)
    result = planner.compare(query(constraints=Constraints(max_darkness_hours=12, max_earth_blackout_hours=6),
                                   min_sunlit_fraction=1, min_earth_los_fraction=0.8))
    time = result.candidates[0].sensitivity["comparisons"]["time_5min_vs_1min"]
    assert time["baseline"]["decision"] == time["alternative"]["decision"] == "FAIL"
    assert time["status"] == "REVIEW"
    assert time["alternative"]["constraint_states"]["min_sunlit_fraction"] == "FAIL"


def test_blackout_constraint_is_longest_continuous_event_not_total():
    values = bounds(list("VVV"), list("BVB"), [2., 1., 2.])
    assert values["longest_blackout_hours"] == [2., 2.]
    assert assess_soft(values, Constraints(max_earth_blackout_hours=2))[0]["max_earth_blackout_hours"] == "PASS"


def flags():
    return ["compare", "--sites", "Site04_P1", "--arrival", "2026-11-14T00:00:00Z",
            "--min-sunlit-fraction", "0.8", "--min-earth-los-fraction", str((72-71.15)/72),
            "--max-darkness-hours", "12", "--max-earth-blackout-hours", "71.15"]


def test_cli_direct_local_json_and_csv_export_without_network(planner, capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Local planning must not call HTTP or an LLM")
    monkeypatch.setattr(httpx, "Client", forbidden)
    assert planning_cli.main(flags(), service=planner) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["sensitivity"]["status"] == "REVIEW"
    assert planning_cli.main(["export", payload["result_id"], "--format", "csv"], service=planner) == 0
    row = next(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert row["sensitivity_status"] == "REVIEW"
    assert json.loads(row["sensitivity_scope_json"])["constraints"]["max_earth_blackout_hours"] == 71.15


def test_cli_reads_json_file_and_stdin(planner, capsys, tmp_path, monkeypatch):
    payload = query().model_dump_json()
    path = tmp_path/"request.json"
    path.write_text(payload)
    assert planning_cli.main(["compare", "--request", str(path)], service=planner) == 0
    first = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert planning_cli.main(["compare", "--request", "-"], service=planner) == 0
    assert json.loads(capsys.readouterr().out)["result_id"] == first["result_id"]


@pytest.mark.parametrize("extra", [
    ["--arrival", "2026-11-14T00:07:00Z"],
    ["--arrival", "2026-11-14T00:00:00"],
    ["--max-earth-blackout-hours", "nan"],
    ["--sun-panel-height-m", "1"],
    ["--duration-hours", "48"],
])
def test_cli_invalid_input_fails_without_result(planner, capsys, extra):
    assert planning_cli.main([*flags(), *extra], service=planner) == 2
    output = capsys.readouterr()
    assert not output.out and json.loads(output.err)["error"]
    assert not planner.results.directory().exists()


def test_cli_remote_posts_structured_inputs_without_local_engine(planner, capsys, monkeypatch):
    expected = planner.compare(query()).model_dump(mode="json")
    requests = []
    def handle(request):
        requests.append(request)
        assert request.url.path == "/api/planning/compare"
        assert json.loads(request.content)["constraints"]["max_earth_blackout_hours"] == 71.15
        return httpx.Response(200, json=expected)
    client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handle)))
    def forbidden():
        raise AssertionError("HTTP mode must not instantiate the local planner")
    monkeypatch.setattr(planning_cli, "PlanningService", forbidden)
    assert planning_cli.main([*flags(), "--base-url", "http://localhost:8000"]) == 0
    assert json.loads(capsys.readouterr().out) == expected
    assert len(requests) == 1


def test_cli_rejects_ambiguous_input_sources(planner, capsys):
    assert planning_cli.main([*flags(), "--request", "unused.json"], service=planner) == 2
    assert "cannot be mixed" in json.loads(capsys.readouterr().err)["detail"]
