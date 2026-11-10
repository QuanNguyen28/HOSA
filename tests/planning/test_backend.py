import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"backend"))

from app.core.errors import DomainError
from app.planning.metrics import assess
from app.planning.models import Candidate, CompareRequest, Constraints, SearchRequest
from app.planning.ranking import rank_candidates
from app.planning.repository import ResultRepository, result_csv
from app.planning.router import get_planning_service
from app.planning.service import PlanningService
from app.services.lunarsight import planning as legacy
from app.main import app


@pytest.fixture
def planner(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "_result_dir", lambda: tmp_path/"legacy")
    results = ResultRepository()
    monkeypatch.setattr(results, "directory", lambda: tmp_path/"planning")
    return PlanningService(results=results)


@pytest.fixture
def query():
    return CompareRequest(scenario_id="south_pole_demo_v1", site_ids=["Site01_P1", "Site04_P1"],
        arrival_utc="2026-11-17T00:00:00Z", constraints=Constraints(max_darkness_hours=12, max_earth_blackout_hours=6))


def search_query(query, **updates):
    return SearchRequest(**{**query.model_dump(), "until_utc": "2026-11-24T00:00:00Z", "max_results": 3, **updates})


def test_comparison_uses_same_metrics_and_events_as_legacy(planner, query):
    result = planner.compare(query)
    original = legacy.analyze_request({"scenario_id": query.scenario_id, "site_ids": query.site_ids,
        "start_index": 288, "constraints": query.constraints.model_dump()})
    assert result.status == "FEASIBLE" and result.apply_allowed
    for candidate, source in zip(result.candidates, original["sites"]):
        assert candidate.metrics == source["metrics"]
        assert candidate.events == source["events"]
    assert "score" not in result.model_dump()
    assert planner.results.load(result.result_id) == result
    csv = result_csv(result)
    assert result.source_hash in csv and csv.count("\n") == 3


def test_uncertainty_ranking_does_not_claim_a_total_order():
    def item(identity, pair):
        return Candidate(site_id=identity, candidate_id=identity, decision="PASS",
            metrics={"longest_dark_hours": pair}, constraint_states={}, decisive_event=None, provenance={})
    ranks = {r.candidate_id: r for r in rank_candidates([item("A", [0,2]), item("B", [1,3]), item("C", [2.5,4])], "longest_dark_hours")}
    assert ranks["A"].rank_min == 1 and ranks["A"].rank_max == 2
    assert ranks["B"].rank_min == 1 and ranks["B"].rank_max == 3
    assert ranks["C"].rank_min == 2 and ranks["C"].rank_max == 3
    assert ranks["A"].tied_with == ["B"]  # Overlap is not transitive.


def test_search_bulk_reads_and_bounded_detail_calls(planner, query, monkeypatch):
    calls, loads = [], []
    original_analyze, original_windows = legacy.analyze_request, planner.repository.windows
    def analyze(payload):
        calls.append(payload)
        return original_analyze(payload)
    def windows(site_id):
        loads.append(site_id)
        return original_windows(site_id)
    monkeypatch.setattr(legacy, "analyze_request", analyze)
    monkeypatch.setattr(planner.repository, "windows", windows)
    result = planner.search(search_query(query))
    assert result.coverage["candidate_total"] == 7*96*2
    assert sum(result.coverage[k] for k in ("pass","fail","indeterminate")) == result.coverage["candidate_total"]
    assert len(loads) == 2 and len(calls) == len(result.candidates) <= 3
    assert result.status == "FEASIBLE" and all(c.decision == "PASS" for c in result.candidates)
    for i, a in enumerate(result.candidates):
        for b in result.candidates[i+1:]:
            if a.site_id == b.site_id:
                assert a.end_utc <= b.start_utc or b.end_utc <= a.start_utc


def test_no_feasible_search_returns_explicit_near_misses(planner, query):
    result = planner.search(search_query(query, arrival_utc="2026-11-14T00:00:00Z", until_utc="2026-11-14T00:15:00Z"))
    assert result.status == "NO_FEASIBLE_IN_EVALUATED_SET" and not result.apply_allowed
    assert all(c.decision == "FAIL" and c.violations for c in result.candidates)
    assert result.recommended_candidate_id.startswith("Site01_P1@")
    assert result.candidates[0].metric_context["longest_blackout_hours"]["touches_window_edge"]


def test_missing_interval_coverage_does_not_turn_into_a_pass(planner, query, monkeypatch):
    original = planner.repository.covered_ranges
    monkeypatch.setattr(planner.repository, "covered_ranges", lambda site: [] if site == "Site04_P1" else original(site))
    result = planner.search(search_query(query, until_utc="2026-11-17T00:15:00Z"))
    assert result.coverage["indeterminate"] == 1
    assert result.status == "FEASIBLE" and all(c.site_id == "Site01_P1" for c in result.candidates)


def test_all_unknown_search_has_no_recommendation(planner, query, monkeypatch):
    monkeypatch.setattr(planner.repository, "covered_ranges", lambda site: [])
    result = planner.search(search_query(query))
    assert result.status == "INSUFFICIENT_DATA" and result.candidates == []
    assert result.recommended_candidate_id is None and not result.apply_allowed


@pytest.mark.parametrize("updates,code", [
    ({"arrival_utc":"2026-11-17T00:07:00Z"}, "OFF_START_GRID"),
    ({"until_utc":"2026-11-17T00:00:00Z"}, "INVALID_SEARCH_RANGE"),
    ({"until_utc":"2026-11-28T00:15:00Z"}, "OUTSIDE_TIME_COVERAGE"),
    ({"duration_hours":48}, "UNSUPPORTED_DURATION"),
    ({"hardware":{"sun_panel":3,"earth_antenna":2}}, "UNSUPPORTED_HARDWARE"),
    ({"site_ids":["Site99"]}, "UNSUPPORTED_SITE_SCOPE"),
    ({"expected_source_hash":"old"}, "STALE_DATASET"),
])
def test_scope_guards(planner, query, updates, code):
    with pytest.raises(DomainError, match=code):
        planner.search(search_query(query, **updates))


def test_request_schema_rejects_duplicates_and_unbounded_results(query):
    with pytest.raises(ValidationError):
        search_query(query, max_results=100)
    with pytest.raises(ValidationError):
        CompareRequest(**{**query.model_dump(), "site_ids":["Site01_P1","Site01_P1"]})


def test_source_changes_during_evaluation_are_rejected(planner, query, monkeypatch):
    original = planner.capabilities
    calls = []
    def capabilities():
        caps = original(); calls.append(1)
        return {**caps, "source_hash":"changed"} if len(calls)>1 else caps
    monkeypatch.setattr(planner, "capabilities", capabilities)
    with pytest.raises(DomainError, match="STALE_DATASET"):
        planner.compare(query)


def test_search_detail_must_agree_with_scanned_metrics(planner, query, monkeypatch):
    original = legacy.analyze_request
    def mismatch(payload):
        result = original(payload)
        result["sites"][0]["metrics"]["longest_dark_hours"] = [1,1]
        return result
    monkeypatch.setattr(legacy, "analyze_request", mismatch)
    with pytest.raises(DomainError, match="SEARCH_DETAIL_MISMATCH"):
        planner.search(search_query(query))


def test_http_endpoints_share_results_and_export(planner, query):
    app.dependency_overrides[get_planning_service] = lambda: planner
    try:
        with TestClient(app) as client:
            assert client.get("/api/planning/capabilities").status_code == 200
            response = client.post("/api/planning/compare", json=query.model_dump())
            assert response.status_code == 200
            result = response.json()
            exported = client.get(f"/api/planning/results/{result['result_id']}")
            assert exported.json() == result
            assert client.get(f"/api/planning/results/{result['result_id']}?format=csv").status_code == 200
            searched = client.post("/api/planning/windows/search", json=search_query(query).model_dump())
            assert searched.status_code == 200 and searched.json()["operation"] == "window_search"
            assert client.get("/api/planning/results/invalid").status_code == 400
            assert client.get("/api/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_identical_results_can_be_persisted_concurrently(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    directory = tmp_path/"concurrent"
    monkeypatch.setattr(legacy, "_result_dir", lambda: directory)
    barrier = Barrier(2)
    original = Path.replace
    temporaries = []
    def replace(path, target):
        if path.parent == directory:
            temporaries.append(str(path))
            barrier.wait(timeout=10)
        return original(path, target)
    monkeypatch.setattr(Path, "replace", replace)
    result = {"result_id": "a"*20, "value": 1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(legacy._persist_result, [result, result]))
    assert len(set(temporaries)) == 2
    assert json.loads((directory/("a"*20+".json")).read_text()) == result
    assert not list(directory.glob("*.tmp"))
