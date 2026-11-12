"""Revalidation policy tests; synthetic science is confined to pytest temp fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from test_point_analysis import pipeline, query
from app.core.errors import DomainError
from app.mission.evaluation import TOLERANCES
from app.mission.models import MissionTarget
from app.mission.resolution import can_recompute
from app.planning.models import CompareRequest, SearchRequest
from app.planning.analysis import analyze_candidate
from app.planning.service import PlanningService
from app.mission.snapshot import SnapshotProvider


def angular_failure(monkeypatch, always=False):
    from app.point_analysis import pipeline as module
    original = module.angle_difference
    def difference(base, alternative):
        step = float(next(iter(alternative.values())).az_step_deg.iloc[0])
        base_step = float(next(iter(base.values())).az_step_deg.iloc[0])
        if step != base_step and (step == .125 or always and step in (.0625, .03125)):
            return {str(h): {'comparable': len(profile), 'max_abs_deg': .2} for h, profile in alternative.items()}
        return original(base, alternative)
    monkeypatch.setattr(module, 'angle_difference', difference)


def test_refinement_resolves_feasible_and_preserves_cache(pipeline, monkeypatch):
    contact, expected = None, 'PASS'
    angular_failure(monkeypatch)
    # Exercise the fallback when existing mission bounds cannot certify it.
    monkeypatch.setattr('app.point_analysis.pipeline.validate_mission_path', lambda *args: {'passed': False})
    before_tolerances = deepcopy(TOLERANCES)
    baseline = pipeline.run(query(min_sunlit_fraction=.8, contact_requirements=contact))
    assert baseline['decision'] == 'INDETERMINATE'
    request = query(min_sunlit_fraction=.8, contact_requirements=contact, resolve_indeterminate=True)
    stages = []
    result = pipeline.run(request, stages.append)
    assert result['decision'] == expected and result['validation']['passed'] is True
    assert result['resolution']['status'] == 'resolved'
    assert result['resolution']['refinement_rounds'] == 1
    assert result['resolution']['attempts'][0]['decision'] == 'INDETERMINATE'
    assert result['resolution']['attempts'][1]['fine_az_step_deg'] == .0625
    assert result['validation']['configuration']['coarse_az_step_deg'] == .125
    assert 'azimuth_0.125_vs_0.0625' in result['validation']['sensitivity']
    assert TOLERANCES == before_tolerances
    assert result['result_id'] != baseline['result_id']
    assert 'refining_horizon_0.0625deg' in stages
    repeated = pipeline.run(request)
    assert repeated['execution']['result_cache_hit'] is True
    assert repeated['resolution'] == result['resolution']
    assert result['request']['contact_requirements'] == request.model_dump()['contact_requirements']


def test_refinement_has_a_hard_two_round_limit(pipeline, monkeypatch):
    angular_failure(monkeypatch, always=True)
    monkeypatch.setattr('app.point_analysis.pipeline.validate_mission_path', lambda *args: {'passed': False})
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result['decision'] == 'INDETERMINATE'
    assert result['resolution']['refinement_rounds'] == 2
    assert len(result['resolution']['attempts']) == 3
    assert result['resolution']['remaining_reason_codes'] == ['azimuth_0.0625_vs_0.03125:SENSITIVITY_FAILED']


def test_hard_contact_failure_does_not_wait_for_global_validation_or_refinement(pipeline, monkeypatch):
    angular_failure(monkeypatch, always=True)
    for enabled in (False, True):
        result = pipeline.run(query(min_sunlit_fraction=.8, contact_requirements={'min_contact_minutes': 70},
                                    resolve_indeterminate=enabled))
        assert result['decision'] == 'FAIL'
        assert result['validation']['passed'] is False
        assert result['contact_analysis']['requirements']['decision'] == 'FAIL'
        assert result['resolution']['refinement_rounds'] == 0


@pytest.mark.parametrize('missing', [False, True])
def test_no_sun_is_rejected_but_missing_sun_evidence_stays_unknown(pipeline, monkeypatch, missing):
    original = pipeline.ephemerides
    def ephemerides(*args, **kwargs):
        sun, earth, receipts = original(*args, **kwargs)
        sun['el_deg'] = -10
        if missing:
            sun['row_present'] = False
            receipts[0]['missing_timestamps'] = len(sun)
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, 'ephemerides', ephemerides)
    monkeypatch.setattr('app.point_analysis.pipeline.seam_checks', lambda _: [{'passed': False}])
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result['metrics_hours']['total_sun_hours'] == ([0, 1] if missing else [0, 0])
    assert result['constraint_checks']['min_sunlit_fraction'] == ('INDETERMINATE' if missing else 'FAIL')
    assert result['decision'] == ('INDETERMINATE' if missing else 'FAIL')
    assert not result['validation']['passed'] and 'DEM_SEAM_FAILED' in result['validation']['reason_codes']
    assert result['resolution']['refinement_rounds'] == 0


def test_full_sun_can_pass_for_mission_without_claiming_global_horizon_convergence(pipeline, monkeypatch):
    angular_failure(monkeypatch, always=True)
    baseline = pipeline.run(query(min_sunlit_fraction=.8))
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert baseline['decision'] == 'INDETERMINATE'
    assert result['metrics_hours']['total_sun_hours'] == [1, 1]
    assert result['decision'] == 'PASS' and not result['validation']['passed']
    mission = result['validation']['mission_path']
    assert mission['passed'] and mission['targets']['sun']['state'] == 'V'
    assert mission['targets']['sun']['min_clearance_beyond_envelope_deg'] > 0
    assert result['resolution']['refinement_rounds'] == 0
    assert result['validation']['configuration']['fine_az_step_deg'] == .125
    assert result['validation']['reason_codes']  # The global failure is retained.


def test_existing_bounds_avoid_expensive_refinement_and_version_cache_separately(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    angular_failure(monkeypatch, always=True)
    original_scan = module.scan_horizons
    def scan(*args, **kwargs):
        assert kwargs['az_step'] >= .125, 'Proven mission must not request additional rays'
        return original_scan(*args, **kwargs)
    monkeypatch.setattr(module, 'scan_horizons', scan)
    stages = []
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True), stages.append)
    assert result['decision'] == 'PASS' and result['validation']['mission_path']['passed']
    assert result['resolution']['refinement_rounds'] == 0
    assert result['resolution']['policy_version'] == 'indeterminate-resolution-2.1'
    assert 'checking_mission_bounds' in stages
    assert not any(s.startswith('refining_horizon_') for s in stages)


@pytest.mark.parametrize('case', ['near_horizon', 'missing', 'temporal', 'seam'])
def test_mission_path_cannot_rescue_missing_near_boundary_or_other_science_failures(pipeline, monkeypatch, case):
    import numpy as np
    angular_failure(monkeypatch, always=True)
    original = pipeline.ephemerides
    def ephemerides(*args, **kwargs):
        sun, earth, receipts = original(*args, **kwargs)
        if case == 'near_horizon':
            sun['el_deg'] = .01  # Visible, but inside the widened numerical envelope.
        elif case == 'missing':
            sun.loc[sun.index[0], 'el_deg'] = np.nan
            receipts[0]['missing_angles'] = 1
        elif case == 'temporal' and args[-1] == 1:
            sun.loc[sun.index[::2], 'el_deg'] = -5
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, 'ephemerides', ephemerides)
    if case == 'seam':
        monkeypatch.setattr('app.point_analysis.pipeline.seam_checks', lambda _: [{'passed': False}])
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result['decision'] == 'INDETERMINATE'
    assert not result['validation'].get('mission_path', {}).get('passed')


def test_bad_seams_are_not_retried_or_bypassed(pipeline, monkeypatch):
    monkeypatch.setattr('app.point_analysis.pipeline.seam_checks', lambda _: [{'passed': False}])
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result['decision'] == 'INDETERMINATE'
    assert result['resolution']['refinement_rounds'] == 0
    assert 'DEM_SEAM_FAILED' in result['validation']['reason_codes']
    assert not can_recompute(result['validation'])


def test_no_extra_geometry_for_already_conclusive_result(pipeline):
    result = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    assert result['decision'] == 'PASS'
    assert result['resolution']['status'] == 'not_needed'
    assert result['resolution']['refinement_rounds'] == 0


def test_switch_is_strict_and_propagates_to_shared_mission():
    with pytest.raises(ValidationError):
        query(resolve_indeterminate='yes')
    q = CompareRequest(site_ids=['Site01_P1'], arrival_utc='2026-11-17T00:00:00Z', min_sunlit_fraction=.8, resolve_indeterminate=True)
    assert q.mission(q.mission_targets()[0]).resolve_indeterminate is True


def test_snapshot_recomputation_preserves_target_and_origin(pipeline, monkeypatch):
    point = pipeline.run(query(min_sunlit_fraction=.8, resolve_indeterminate=True))
    # Tests only: map the synthetic point to a synthetic snapshot target.
    monkeypatch.setattr(MissionTarget, 'resolved', lambda self: query())
    monkeypatch.setattr('app.point_analysis.service.calculate', lambda request, _: deepcopy(point))
    snapshot = {'decision': 'INDETERMINATE', 'nominal_sampled_decision': 'PASS',
        'validation': {'passed': False, 'reason_codes': ['time_5min_vs_1min:COMPARISON_EVIDENCE_MISSING']},
        'provenance': {'provider': 'snapshot'}, 'timeline_frame': None, 'sensitivity': {}}
    monkeypatch.setattr(SnapshotProvider, 'analyze', lambda *args: deepcopy(snapshot))
    q = CompareRequest(site_ids=['Site01_P1'], arrival_utc=query().start_utc, duration_hours=1,
        min_sunlit_fraction=.8, resolve_indeterminate=True)
    candidate = analyze_candidate(q, 0, snapshot=SnapshotProvider(), point_pipeline=pipeline)
    assert candidate.decision == 'PASS' and candidate.site_id == 'Site01_P1'
    assert candidate.resolution['status'] == 'resolved'
    assert candidate.resolution['origin']['provider'] == 'snapshot'
    assert candidate.resolution['initial_reason_codes'] == snapshot['validation']['reason_codes']
    assert candidate.analysis_result_id == point['result_id']


def test_snapshot_missing_cache_keeps_original_unknown_evidence(pipeline, monkeypatch):
    import pandas as pd
    snapshot = pipeline.run(query(min_sunlit_fraction=.8))
    snapshot['decision'] = 'INDETERMINATE'
    snapshot['validation'] = {**snapshot['validation'], 'passed': False,
        'reason_codes': ['time_5min_vs_1min:COMPARISON_EVIDENCE_MISSING']}
    snapshot['timeline_frame'] = pd.DataFrame(snapshot['timeline'])
    for key in ('start_utc', 'end_utc'):
        snapshot['timeline_frame'][key] = pd.to_datetime(snapshot['timeline_frame'][key], utc=True)
    snapshot['sensitivity'] = {}
    monkeypatch.setattr(SnapshotProvider, 'analyze', lambda *args: deepcopy(snapshot))
    monkeypatch.setattr(MissionTarget, 'resolved', lambda self: query())
    def missing(*args): raise DomainError('HORIZONS_CACHE_MISS', 503)
    monkeypatch.setattr('app.point_analysis.service.calculate', missing)
    q = CompareRequest(site_ids=['Site01_P1'], arrival_utc=query().start_utc, duration_hours=1,
        min_sunlit_fraction=.8, resolve_indeterminate=True, offline=True)
    candidate = analyze_candidate(q, 0, snapshot=SnapshotProvider(), point_pipeline=pipeline)
    assert candidate.decision == 'INDETERMINATE'
    assert candidate.metrics == snapshot['metrics_hours']
    assert candidate.resolution['status'] == 'unresolved'
    assert candidate.resolution['error_code'] == 'HORIZONS_CACHE_MISS'
    assert candidate.validation['passed'] is False


def test_resolution_search_budget_checked_before_any_candidate(monkeypatch):
    planner = PlanningService()
    monkeypatch.setattr(planner, 'source_capabilities', lambda q: {'scenario': {'scenario_id': 'south_pole_demo_v1',
        'site_ids': ['Site01_P1'], 'D_hours': 72, 'device_heights_m': {'sun_panel': 1., 'earth_antenna': 2.},
        'A_utc': '2026-11-14T00:00:00Z', 'B_utc': '2026-11-28T00:00:00Z', 'start_step_minutes': 15}})
    monkeypatch.setattr(planner, 'analyzer', lambda _: pytest.fail('budget must be checked first'))
    q = SearchRequest(site_ids=['Site01_P1'], arrival_utc='2026-11-14T00:00:00Z', until_utc='2026-11-16T00:00:00Z',
        min_sunlit_fraction=.8, resolve_indeterminate=True)
    with pytest.raises(DomainError, match='SEARCH_TOO_LARGE'):
        planner.search(q)


def test_resolved_result_is_identical_through_direct_compare_search_and_export(pipeline, monkeypatch, tmp_path):
    from app.planning.repository import ResultRepository, result_csv
    angular_failure(monkeypatch)
    request = query(min_sunlit_fraction=.8, resolve_indeterminate=True)
    direct = pipeline.run(request)
    results = ResultRepository()
    monkeypatch.setattr(results, 'directory', lambda: tmp_path/'planning')
    planner = PlanningService(results=results, point_pipeline=pipeline)
    q = CompareRequest(targets=[{'latitude_deg': request.latitude_deg, 'longitude_e_deg': request.longitude_e_deg}],
        data_source='coordinate', arrival_utc=request.start_utc, duration_hours=1,
        min_sunlit_fraction=.8, resolve_indeterminate=True)
    compared = planner.compare(q)
    searched = planner.search(SearchRequest(**q.model_dump(), until_utc='2026-11-17T00:05:00Z', start_step_minutes=5))
    for result in (compared, searched):
        c = result.candidates[0]
        assert result.apply_allowed and c.decision == 'PASS'
        assert c.analysis_result_id == direct['result_id']
        assert c.validation == direct['validation']
        assert c.resolution == direct['resolution']
        assert results.load(result.result_id) == result
        assert 'resolution_json' in result_csv(result)
