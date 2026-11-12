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
from app.mission.snapshot import SnapshotProvider


@pytest.fixture
def planner(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "_result_dir", lambda: tmp_path/"legacy")
    results = ResultRepository()
    monkeypatch.setattr(results, "directory", lambda: tmp_path/"planning")
    return PlanningService(results=results)


@pytest.fixture
def query():
    return CompareRequest(scenario_id="south_pole_demo_v1", site_ids=["Site01_P1", "Site04_P1"],
        arrival_utc="2026-11-17T00:00:00Z", constraints=Constraints(max_darkness_hours=12, max_earth_blackout_hours=6),
        min_sunlit_fraction=0.8, min_earth_los_fraction=0.8)


def search_query(query, **updates):
    data = query.model_dump()
    if ("arrival_utc" in updates or "duration_hours" in updates) and "end_utc" not in updates:
        data.pop("end_utc", None)
    return SearchRequest(**{**data, "until_utc": "2026-11-24T00:00:00Z", "max_results": 3, **updates})


def test_comparison_uses_same_metrics_and_events_as_legacy(planner, query):
    result = planner.compare(query)
    original = legacy.analyze_request({"scenario_id": query.scenario_id, "site_ids": query.site_ids,
        "start_index": 288, "constraints": query.constraints.model_dump(),
        "min_sunlit_fraction": query.min_sunlit_fraction, "min_earth_los_fraction": query.min_earth_los_fraction})
    assert result.status == "INSUFFICIENT_DATA" and not result.apply_allowed
    for candidate, source in zip(result.candidates, original["sites"]):
        for metric, pair in source["metrics"].items():
            assert candidate.metrics[metric] == pytest.approx(pair)
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


def test_search_prefilters_failed_validation_without_loading_details(planner, query, monkeypatch):
    calls = []
    original = SnapshotProvider.prepare
    def prepare(self, site_id):
        if site_id not in self.prepared:
            calls.append(site_id)
        return original(self, site_id)
    monkeypatch.setattr(SnapshotProvider, "prepare", prepare)
    monkeypatch.setattr(SnapshotProvider, "analyze", lambda *args: pytest.fail("static gate already failed"))
    result = planner.search(search_query(query))
    assert result.coverage["candidate_total"] == 7*96*2
    assert result.coverage["indeterminate"] == result.coverage["candidate_total"]
    assert calls == ["Site01_P1", "Site04_P1"]
    assert result.status == "INSUFFICIENT_DATA" and not result.candidates


def test_search_hard_failure_is_not_hidden_by_validation_preflight(planner, query):
    result = planner.search(search_query(query, arrival_utc="2026-11-14T00:00:00Z", until_utc="2026-11-14T00:15:00Z"))
    assert result.status == "NO_FEASIBLE_IN_EVALUATED_SET" and not result.apply_allowed
    assert result.coverage['fail'] == 2 and result.coverage['indeterminate'] == 0
    assert all(c.decision == 'FAIL' and c.validation['passed'] is False for c in result.candidates)
    assert result.recommended_candidate_id is not None  # A rejected near miss, never applicable.


def test_missing_interval_coverage_does_not_turn_into_a_pass(planner, query, monkeypatch):
    original = SnapshotProvider.prepare
    def missing(self, site):
        evidence = original(self, site)
        if site == 'Site04_P1':
            evidence['base'] = evidence['base'].iloc[:0]
        return evidence
    monkeypatch.setattr(SnapshotProvider, 'prepare', missing)
    result = planner.compare(query)
    assert result.candidates[1].issue == 'INCOMPLETE_TIMELINE'
    assert result.candidates[1].decision == 'INDETERMINATE' and not result.apply_allowed


def test_all_unknown_search_has_no_recommendation(planner, query, monkeypatch):
    monkeypatch.setattr(SnapshotProvider, "preflight_failure", lambda *args: "INCOMPLETE_TIMELINE")
    result = planner.search(search_query(query))
    assert result.status == "INSUFFICIENT_DATA" and result.candidates == []
    assert result.recommended_candidate_id is None and not result.apply_allowed


@pytest.mark.parametrize("updates,code", [
    ({"arrival_utc":"2026-11-17T00:05:00Z"}, "OFF_START_GRID"),
    ({"until_utc":"2026-11-17T00:00:00Z"}, "INVALID_SEARCH_RANGE"),
    ({"until_utc":"2026-11-28T00:15:00Z"}, "OUTSIDE_TIME_COVERAGE"),
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


def test_provider_metrics_must_agree_with_native_timeline(planner, query, monkeypatch):
    original = SnapshotProvider.analyze
    def mismatch(self, target, request):
        result = original(self, target, request)
        result['metrics_hours']['longest_dark_hours'] = [1,1]
        return result
    monkeypatch.setattr(SnapshotProvider, 'analyze', mismatch)
    with pytest.raises(DomainError, match='ENGINE_CONTRACT_ERROR'):
        planner.compare(query)


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


def test_result_persistence_retries_transient_windows_replace_denial(tmp_path, monkeypatch):
    directory=tmp_path/"transient"
    monkeypatch.setattr(legacy,"_result_dir",lambda:directory)
    real_replace=legacy.os.replace
    calls=[]
    def replace(source,target):
        calls.append((source,target))
        if len(calls)==1:
            raise PermissionError("transient sharing violation")
        return real_replace(source,target)
    monkeypatch.setattr(legacy.os,"replace",replace)
    monkeypatch.setattr(legacy.time,"sleep",lambda _:None)
    result={"result_id":"b"*20,"value":1}
    legacy._persist_result(result)
    assert len(calls)==2
    assert json.loads((directory/("b"*20+".json")).read_text())==result
    assert not list(directory.glob("*.tmp"))


def test_result_persistence_does_not_hide_permanent_replace_denial(tmp_path, monkeypatch):
    directory=tmp_path/"permanent"
    monkeypatch.setattr(legacy,"_result_dir",lambda:directory)
    def denied(*args):
        raise PermissionError("permanent denial")
    monkeypatch.setattr(legacy.os,"replace",denied)
    monkeypatch.setattr(legacy.time,"sleep",lambda _:None)
    with pytest.raises(PermissionError):
        legacy._persist_result({"result_id":"c"*20})
    assert not list(directory.glob("*.tmp"))
    assert not list(directory.glob("*.json"))
