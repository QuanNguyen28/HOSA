"""Regression cases found while reviewing unified mission entry points."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from test_mission_unification import pipeline, planner, mission, comparison
from app.core.errors import DomainError
from app.mission.snapshot import SnapshotProvider
from app.planning.models import SearchRequest
from app.mission.models import MissionRequest
from app.planning.models import CompareRequest
from app.planning.repository import SnapshotRepository
from app.services.lunarsight import planning as legacy
from app.services.lunarsight.visibility import visibility


def test_coordinate_candidate_id_is_stable_between_compare_and_search(planner):
    query = comparison(mission())
    compared = planner.compare(query).candidates[0]
    searched = planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-17T00:15:00Z'))
    assert searched.candidates[0].candidate_id == compared.candidate_id
    assert searched.candidates[0].start_index is None  # No snapshot grid index for coordinates.


def test_snapshot_missing_files_are_unknown_in_compare_and_search(planner, monkeypatch):
    def missing(*args):
        raise FileNotFoundError('test-only missing snapshot')
    monkeypatch.setattr(SnapshotProvider, 'prepare', missing)
    query = comparison(mission(), data_source='snapshot', targets=[{'site_id': 'Site01_P1'}], duration_hours=72)
    compared = planner.compare(query)
    searched = planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-17T00:15:00Z'))
    assert compared.coverage['indeterminate'] == searched.coverage['indeterminate'] == 1
    assert searched.status == 'INSUFFICIENT_DATA' and searched.candidates == []


def test_snapshot_source_hash_includes_catalog_coordinates(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, 'repository_root', lambda: tmp_path)
    processed = tmp_path/'data/processed/test'
    processed.mkdir(parents=True)
    monkeypatch.setattr(legacy, 'processed_root', lambda: processed)
    monkeypatch.setattr(legacy, 'scenarios', lambda: {'scenarios': [{}], 'dataset_version': 'test-only', 'warnings': []})
    catalog = processed/'site_catalog.geojson'
    catalog.write_text('first test-only coordinates')
    first = SnapshotRepository().capabilities()['source_hash']
    catalog.write_text('different test-only coordinates')
    second = SnapshotRepository().capabilities()['source_hash']
    assert first != second


@pytest.mark.parametrize('present,elevation', [(False, 5.), (True, np.inf), (True, -np.inf)])
def test_invalid_ephemeris_never_becomes_visible_or_blocked(present, elevation):
    times = pd.date_range('2026-11-17T00:00:00Z', periods=2, freq='5min')
    sun = pd.DataFrame({'az_deg': 90., 'el_deg': elevation, 'row_present': present}, index=times)
    earth = pd.DataFrame({'az_deg': 90., 'el_deg': 5., 'row_present': True}, index=times)
    profile = pd.DataFrame({'az_deg': [0., 90., 180., 270.], 'az_step_deg': 90., 'horizon_deg': 0., 'coverage_complete': True})
    result = visibility(sun, earth, profile, profile)
    assert result.sun_state.tolist() == ['?']
    assert not result.sun_ephem_valid.any()
    assert result.sun_coverage_flag.tolist() == ['missing_ephemeris']


def test_search_rejects_out_of_range_last_mission_before_computing(planner, monkeypatch):
    monkeypatch.setattr('app.planning.service.analyze_candidate', lambda *a, **kw: pytest.fail('search must reject before first analysis'))
    query = comparison(mission(start_utc='2026-11-17T00:00:00Z'))
    with pytest.raises(DomainError, match='INVALID_SEARCH_RANGE'):
        planner.search(SearchRequest(**query.model_dump(), until_utc='2026-11-16T00:00:00Z'))


@pytest.mark.parametrize('operation,model', [('compare', CompareRequest), ('search', SearchRequest)])
@pytest.mark.parametrize('position,name', [(0, 'pass'), (1, 'fail')])
def test_documented_requests_describe_identical_missions(operation, model, position, name):
    examples = Path(__file__).resolve().parents[1]/'docs/examples'
    point = MissionRequest.model_validate_json((examples/f'point-analysis-outside-{name}-request.json').read_text())
    planning = model.model_validate_json((examples/f'planning-{operation}-coordinate-request.json').read_text())
    assert planning.mission(planning.mission_targets()[position]).model_dump() == point.model_dump()
