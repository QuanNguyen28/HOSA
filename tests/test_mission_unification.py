"""Contract and cross-route consistency; synthetic science lives only in tmp_path."""
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from test_point_analysis import pipeline  # Explicit synthetic sphere/JPL fixture.
from app.core.errors import DomainError
from app.main import app
from app.mission.models import MissionRequest, MissionTarget
from app.mission.evaluation import VALIDATION_VERSION
from app.mission.snapshot import SnapshotProvider
from app.point_analysis.service import get_point_pipeline
from app.point_analysis.models import PointAnalysisRequest
from app.planning.models import CompareRequest, SearchRequest
from app.planning.service import PlanningService
from app.planning.repository import ResultRepository
from app.planning.router import get_planning_service
from app.services.lunarsight.catalog import site_catalog


def mission(**updates):
    return MissionRequest(**{'illumination_model': 'sun_center', 'latitude_deg': -89.5, 'longitude_e_deg': 220,
        'start_utc': '2026-11-17T00:00:00Z', 'duration_hours': 1, 'min_sunlit_fraction': .8,
        'contact_requirements': {'min_contact_minutes': 30, 'setup_minutes': 5, 'required_windows': 1,
            'first_contact_deadline_minutes': 40}, **updates})


def comparison(request, **updates):
    data = request.model_dump()
    if "duration_hours" in updates and "end_utc" not in updates:
        data.pop("end_utc", None)
    point = {key: data.pop(key) for key in ('site_id', 'latitude_deg', 'longitude_e_deg')}
    point = {k: v for k, v in point.items() if v is not None}
    start = data.pop('start_utc')
    heights = {'sun_panel': data.pop('panel_height_m'), 'earth_antenna': data.pop('antenna_height_m')}
    return CompareRequest(**{**data, 'targets': [point], 'data_source': 'coordinate',
        'arrival_utc': start, 'hardware': heights, **updates})


@pytest.fixture
def planner(pipeline, tmp_path, monkeypatch):
    results = ResultRepository()
    monkeypatch.setattr(results, 'directory', lambda: tmp_path/'planning-results')
    return PlanningService(results=results, point_pipeline=pipeline)


@pytest.mark.parametrize('target', [{}, {'latitude_deg': -89}, {'site_id': 'Site01_P1', 'latitude_deg': -89, 'longitude_e_deg': 20},
    {'latitude_deg': True, 'longitude_e_deg': 20}, {'site_id': ''}])
def test_targets_are_explicit_and_unambiguous(target):
    with pytest.raises(ValidationError):
        MissionTarget(**target)


def test_catalog_resolution_is_exact_and_site04_stays_site04():
    catalog = site_catalog()
    props = next(f['properties'] for f in catalog['features'] if f['properties']['site_id'] == 'Site04_P1')
    req = MissionRequest(site_id='Site04_P1', start_utc='2026-11-17T00:00:00Z')
    result = req.resolved()
    assert result.latitude_deg == props['lat_deg'] and result.longitude_e_deg == props['lon_e_deg']
    assert result.site_id is None
    raw = mission()
    assert raw.resolved().latitude_deg == raw.latitude_deg
    with pytest.raises(DomainError, match='UNSUPPORTED_SITE_SCOPE'):
        MissionRequest(site_id='Site99', start_utc=raw.start_utc).resolved()


def test_direct_compare_search_agree_including_contact_and_validation(pipeline, planner):
    req = mission()
    direct = pipeline.run(req)
    query = comparison(req)
    candidate = planner.compare(query).candidates[0]
    found = planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-17T00:05:00Z', start_step_minutes=5))
    assert found.coverage == {'candidate_total': 1, 'pass': 1, 'fail': 0, 'indeterminate': 0, 'returned': 1, 'not_returned': 0}
    for item in (candidate, found.candidates[0]):
        assert item.decision == direct['decision'] == 'PASS'
        assert item.nominal_sampled_decision == direct['nominal_sampled_decision']
        assert item.metrics == direct['metrics_hours']
        assert item.constraint_states == direct['constraint_checks']
        assert item.validation == direct['validation']
        assert item.analysis_result_id == direct['result_id']
        assert item.contact_analysis['metrics'] == direct['contact_analysis']['metrics']
    assert planner.results.load(found.result_id) == found


def test_failed_validation_is_never_recommended_in_compare_or_search(pipeline, planner, monkeypatch):
    monkeypatch.setattr('app.point_analysis.pipeline.seam_checks', lambda _: [{'passed': False}])
    req = mission()
    direct = pipeline.run(req)
    compared = planner.compare(comparison(req))
    searched = planner.search(SearchRequest(**comparison(req).model_dump(), until_utc='2026-11-17T00:15:00Z'))
    assert direct['nominal_sampled_decision'] == compared.candidates[0].nominal_sampled_decision == 'PASS'
    assert direct['decision'] == compared.candidates[0].decision == 'INDETERMINATE'
    assert compared.candidates[0].validation['policy_version'] == VALIDATION_VERSION
    assert not compared.apply_allowed and compared.recommended_candidate_id is None
    assert searched.coverage['indeterminate'] == 1 and searched.candidates == [] and not searched.apply_allowed


def test_fail_is_retained_but_never_applied(pipeline, planner):
    req = mission(contact_requirements={'min_contact_minutes': 70})
    direct = pipeline.run(req)
    compared = planner.compare(comparison(req))
    searched = planner.search(SearchRequest(**comparison(req).model_dump(), until_utc='2026-11-17T00:15:00Z'))
    assert direct['decision'] == compared.candidates[0].decision == searched.candidates[0].decision == 'FAIL'
    assert compared.candidates[0].constraint_states['contact.min_contact_minutes'] == 'FAIL'
    assert not compared.apply_allowed and not searched.apply_allowed


def test_multiple_starts_match_individual_analysis(pipeline, planner):
    query = comparison(mission())
    result = planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-17T00:30:00Z',
        max_results=2, non_overlapping=False))
    assert result.coverage['pass'] == 2
    for candidate in result.candidates:
        req = mission(start_utc=candidate.start_utc)
        direct = pipeline.run(req)
        assert candidate.analysis_result_id == direct['result_id']
        assert candidate.metrics == direct['metrics_hours']


def test_http_uses_same_pipeline_and_accepts_contact_only(pipeline, planner):
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    app.dependency_overrides[get_planning_service] = lambda: planner
    try:
        with TestClient(app) as client:
            req = mission(min_sunlit_fraction=None)
            direct = client.post('/api/lunar/point/analyze', json=req.model_dump())
            compare = client.post('/api/planning/compare', json=comparison(req).model_dump())
            assert direct.status_code == compare.status_code == 200
            assert compare.json()['candidates'][0]['analysis_result_id'] == direct.json()['result_id']
            bad = comparison(req).model_dump()
            bad['targets'] = [{'latitude_deg': -89.5}]
            assert client.post('/api/planning/compare', json=bad).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_search_limits_are_checked_before_computation(planner, monkeypatch):
    monkeypatch.setattr('app.planning.service.analyze_candidate', lambda *a, **kw: pytest.fail('must reject before computation'))
    q = comparison(mission())
    with pytest.raises(DomainError, match='SEARCH_TOO_LARGE'):
        planner.search(SearchRequest(**q.model_dump(), until_utc='2026-11-19T00:00:00Z'))
    with pytest.raises(DomainError, match='INVALID_SEARCH_RANGE'):
        planner.search(SearchRequest(**q.model_dump(), until_utc='2026-11-17T00:20:00Z'))


def test_snapshot_full_coverage_does_not_bypass_common_gate():
    target = MissionTarget(site_id='Site01_P1')
    req = MissionRequest(illumination_model='sun_center', site_id=target.site_id, start_utc='2026-11-17T00:00:00Z', min_sunlit_fraction=.8)
    provider = SnapshotProvider()
    result = provider.analyze(target, req)
    assert result['nominal_sampled_decision'] == 'PASS'
    assert result['decision'] == 'INDETERMINATE'
    assert result['validation']['policy_version'] == VALIDATION_VERSION
    assert any('COMPARISON_EVIDENCE_MISSING' in reason for reason in result['validation']['reason_codes'])
    assert not result['validation']['sensitivity']['time_5min_vs_1min']['passed']
