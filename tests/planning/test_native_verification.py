"""Keep JSON display rounding out of authoritative planning verification."""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.core.errors import DomainError
from app.mission.models import MissionRequest
from app.mission.evaluation import evaluate, records, VALIDATION_VERSION
from app.planning.analysis import coordinate_frame, verify_result
from app.point_analysis.transport import write_frame


@pytest.fixture
def annual_result(tmp_path):
    request = MissionRequest(latitude_deg=-80.13, longitude_e_deg=1.44,
        start_utc='2027-11-17T00:00:00Z', end_utc='2028-11-17T00:00:00Z',
        min_sunlit_fraction=.8, min_earth_los_fraction=.8, evaluation_policy='complete')
    grid = pd.date_range(request.start_utc, request.end_utc, freq='5min')
    frame = pd.DataFrame({'start_utc': grid[:-1], 'end_utc': grid[1:],
        'sun_state': 'V', 'earth_state': 'V', 'joint_state': 'V',
        'sun_visible_fraction_lower': np.linspace(.123456789012345, .555555555555555, len(grid)-1),
        'sun_visible_fraction_upper': np.linspace(.123456789012345, .555555555555555, len(grid)-1)})
    validation = {'passed': False, 'policy_version': VALIDATION_VERSION}
    result = {**evaluate(request, frame, validation), 'validation': validation,
        'coordinate': {'latitude_deg': request.latitude_deg, 'longitude_e_deg': request.longitude_e_deg},
        'result_id': 'a'*64, 'timeline': records(frame)}
    directory = tmp_path / 'results' / result['result_id']
    result['provenance'] = {'timeline_artifact': write_frame(directory / 'timeline.npy', frame)}
    return request, result, SimpleNamespace(root=tmp_path)


def test_year_long_json_rounding_does_not_reject_native_science(annual_result):
    request, result, pipeline = annual_result
    display = pd.DataFrame(result['timeline'])
    for key in ('start_utc', 'end_utc'):
        display[key] = pd.to_datetime(display[key], utc=True)
    with pytest.raises(DomainError, match='ENGINE_CONTRACT_ERROR'):
        verify_result(result, request, display)
    verify_result(result, request, coordinate_frame(result, pipeline))


def test_native_verification_still_rejects_changed_metrics(annual_result):
    request, result, pipeline = annual_result
    result['metrics_hours']['total_sun_hours'][0] += .01
    with pytest.raises(DomainError, match='ENGINE_CONTRACT_ERROR'):
        verify_result(result, request, coordinate_frame(result, pipeline))


def test_native_verification_rejects_corrupted_artifact(annual_result):
    _, result, pipeline = annual_result
    path = pipeline.root / 'results' / result['result_id'] / 'timeline.npy'
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        stream.write(b'X')
    with pytest.raises(DomainError, match='TIMELINE_INTEGRITY_FAILED'):
        coordinate_frame(result, pipeline)
