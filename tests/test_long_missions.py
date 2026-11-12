"""Long mission windows, exact native JPL chunk joins and bounded decisions."""
from pathlib import Path
import sys

import pandas as pd
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from test_point_analysis import pipeline, query
from test_indeterminate_resolution import angular_failure
from app.core.errors import DomainError
from app.mission.models import MissionRequest
from app.planning.models import CompareRequest, SearchRequest
from app.planning.repository import ResultRepository
from app.planning.service import PlanningService


def point(**changes):
    return MissionRequest(latitude_deg=-89.5, longitude_e_deg=220,
                          start_utc='2026-11-17T00:00:00Z', min_sunlit_fraction=.8, **changes)


@pytest.mark.parametrize('hours', [73, 240+1/12, 17520, 1_000_000])
def test_no_application_maximum_for_duration_or_preferences(hours):
    request = point(duration_hours=hours, constraints={'max_darkness_hours':hours})
    assert request.duration_hours == hours
    assert (pd.Timestamp(request.end_utc)-pd.Timestamp(request.start_utc)).total_seconds()/3600 == hours
    assert 'maximum' not in MissionRequest.model_json_schema()['properties']['duration_hours']
    assert 'maximum' not in CompareRequest.model_json_schema()['properties']['duration_hours']


def test_target_end_date_is_an_equivalent_exact_mission_window():
    end = point(end_utc='2026-11-27T07:05:00+07:00')
    hours = point(duration_hours=240+1/12)
    assert end.model_dump() == hours.model_dump()
    compare = CompareRequest(targets=[{'latitude_deg': -89.5, 'longitude_e_deg':220}], data_source='coordinate',
        arrival_utc=end.start_utc, end_utc=end.end_utc, min_sunlit_fraction=.8)
    assert compare.duration_hours == hours.duration_hours
    assert compare.mission(compare.targets[0]).model_dump() == hours.model_dump()


@pytest.mark.parametrize('kwargs', [
    {'end_utc':'2026-11-17T00:00:00Z'},
    {'end_utc':'2026-11-16T00:00:00Z'},
    {'end_utc':'2026-11-27T00:01:00Z'},
    {'end_utc':'2026-11-27T00:00:00'},
    {'end_utc':'2026-11-27T00:00:00Z','duration_hours':72},
    {'duration_hours':float('inf')}, {'duration_hours':1.01}, {'duration_hours':1e308},
])
def test_invalid_or_conflicting_time_windows_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        point(**kwargs)


def test_long_pipeline_joins_native_chunks_once_and_caches_equivalent_end_date(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    old_fetch, calls = module.fetch, []
    def fetch(*args, **kwargs):
        calls.append((args[2], args[4], args[5], args[6]))
        return old_fetch(*args, **kwargs)
    monkeypatch.setattr(module, 'fetch', fetch)
    request = point(end_utc='2026-12-25T00:05:00Z')
    result = pipeline.run(request)
    assert result['decision'] == 'PASS'
    assert len(calls) == 6  # 1 batch at 5 min + 2 batches at 1 min, for each target.
    assert all(pd.Timestamp(stop)-pd.Timestamp(start) <= pd.Timedelta(minutes=step*40000) for _, start, stop, step in calls)
    assert result['metrics_hours']['total_sun_hours'] == pytest.approx([request.duration_hours]*2)
    assert len(result['timeline']) == 10945 and result['timeline'][-1]['end_utc'].startswith('2026-12-25T00:05:00')
    repeated = pipeline.run(point(duration_hours=request.duration_hours))
    assert repeated['result_id'] == result['result_id'] and repeated['execution']['result_cache_hit']
    assert len(calls) == 6


def test_native_chunk_boundary_mismatch_is_not_silently_spliced(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    old_fetch = module.fetch
    def bad(*args, **kwargs):
        frame, receipt = old_fetch(*args, **kwargs)
        if pd.Timestamp(args[4]) > pd.Timestamp('2026-11-17T00:00:00Z'):
            frame.iloc[0, frame.columns.get_loc('el_deg')] += .01
        return frame, receipt
    monkeypatch.setattr(module, 'fetch', bad)
    with pytest.raises(DomainError, match='HORIZONS_CHUNK_BOUNDARY_MISMATCH'):
        pipeline.ephemerides(point(duration_hours=24*40), {'site_id':'test', 'lon_e_deg':220,
            'lat_deg':-89.5, 'dem_z_m':0, 'dem_sha256':'test'}, 1)


@pytest.mark.parametrize('threshold, expected', [(.7, 'PASS'), (.8, 'INDETERMINATE')])
def test_some_uncertain_sun_samples_can_pass_only_when_pessimistic_requirement_passes(pipeline, monkeypatch, threshold, expected):
    angular_failure(monkeypatch, always=True)
    old = pipeline.ephemerides
    def near(*args, **kwargs):
        sun, earth, receipts = old(*args, **kwargs)
        sun.loc[sun.index < sun.index[0]+pd.Timedelta(minutes=15), 'el_deg'] = .01
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, 'ephemerides', near)
    result = pipeline.run(query(min_sunlit_fraction=threshold, resolve_indeterminate=True))
    assert result['nominal_sampled_decision'] == 'PASS' and not result['validation']['passed']
    proof = result['validation']['mission_path']
    assert result['decision'] == expected
    assert proof['metrics_hours']['total_sun_hours'] == [.75, 1]
    assert proof['constraint_checks']['min_sunlit_fraction'] == ('PASS' if expected == 'PASS' else 'INDETERMINATE')
    assert proof['targets']['sun']['state_counts_1min']['?'] == 15


def test_time_sensitivity_can_be_resolved_by_requirement_bounds_without_extra_geometry(pipeline, monkeypatch):
    old = pipeline.ephemerides
    def sensitive(*args, **kwargs):
        sun, earth, receipts = old(*args, **kwargs)
        if args[-1] == 1:
            sun.loc[sun.index[::2], 'el_deg'] = -5
        return sun, earth, receipts
    monkeypatch.setattr(pipeline, 'ephemerides', sensitive)
    result = pipeline.run(query(min_sunlit_fraction=.1, resolve_indeterminate=True))
    assert result['decision'] == 'PASS' and not result['validation']['passed']
    assert not result['validation']['sensitivity']['time_5min_vs_1min']['passed']
    assert result['validation']['mission_path']['constraint_checks']['min_sunlit_fraction'] == 'PASS'
    assert result['resolution']['refinement_rounds'] == 0


def test_long_default_planning_uses_coordinate_engine_and_shifts_same_duration_in_search(pipeline, tmp_path, monkeypatch):
    repo = ResultRepository()
    monkeypatch.setattr(repo, 'directory', lambda:tmp_path/'planning')
    planner = PlanningService(results=repo, point_pipeline=pipeline)
    query = CompareRequest(targets=[{'latitude_deg':-89.5, 'longitude_e_deg':220}],
        arrival_utc='2026-11-17T00:00:00Z', end_utc='2026-11-21T00:00:00Z', min_sunlit_fraction=.8)
    direct = pipeline.run(point(duration_hours=96))
    compared = planner.compare(query)
    searched = planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-17T00:10:00Z', start_step_minutes=5, non_overlapping=False))
    assert compared.request['data_source'] == 'coordinate'
    assert compared.candidates[0].analysis_result_id == direct['result_id']
    assert len(searched.candidates) == 2
    for candidate in searched.candidates:
        assert (pd.Timestamp(candidate.end_utc)-pd.Timestamp(candidate.start_utc)).total_seconds()/3600 == 96
        assert candidate.decision == 'PASS'
