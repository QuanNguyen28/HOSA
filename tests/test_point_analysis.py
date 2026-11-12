"""Coordinate API and science integration. Synthetic fixtures stay in pytest tmp dirs."""
from pathlib import Path
import json
import sys
from threading import Event

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.main import app
from app.core.errors import DomainError
from app.point_analysis.models import JobStatus, PointAnalysisRequest
from app.point_analysis.pipeline import PointAnalysisPipeline, atomic_json
from app.point_analysis.service import PointAnalysisJobs, get_point_jobs
from app.point_analysis import sources as source_module
from app.point_analysis.sources import TerrainInputs, verified_source
from app.point_analysis.geometry import scan_horizons, verify_profiles
from app.services.lunarsight.acquire import hashfile, sources
from app.services.lunarsight.horizon import ray_elevation


def query(**changes):
    return PointAnalysisRequest(**{'illumination_model': 'sun_center', 'latitude_deg': -89.5, 'longitude_e_deg': 220,
        'start_utc': '2026-11-17T00:00:00Z', 'duration_hours': 1, **changes})


@pytest.mark.parametrize('changes', [
    {'latitude_deg': 90}, {'latitude_deg': float('nan')}, {'longitude_e_deg': 361},
    {'start_utc': '2026-11-17T00:01:00Z'}, {'start_utc': '2026-11-17T00:00:00'},
    {'duration_hours': 0}, {'duration_hours': True}, {'panel_height_m': 0},
    {'duration_hours': 1.01}, {'min_sunlit_fraction': 1.1}])
def test_request_validation(changes):
    with pytest.raises(ValidationError):
        query(**changes)


def test_normalized_longitude_and_utc():
    a = query(longitude_e_deg=-140, start_utc='2026-11-17T07:00:00+07:00')
    assert a.longitude_e_deg == 220 and a.start_utc == '2026-11-17T00:00:00Z'
    assert a.end_utc == '2026-11-17T01:00:00Z'


@pytest.fixture
def raw_source(tmp_path):
    path = tmp_path / 'synthetic.tif'
    crs = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +type=crs'
    with rasterio.open(path, 'w', driver='GTiff', height=10, width=10, count=1,
        dtype='float32', crs=crs, transform=from_origin(-1200, 1200, 240, 240), nodata=-9999) as dataset:
        dataset.write(np.full((10, 10), 100, dtype='float32'), 1)
    record = next(s for s in sources() if s['id'] == 'dem240')
    atomic_json(path.with_name(path.name + '.receipt.json'), {**record, 'status': 'VERIFIED_BYTES',
        'bytes': path.stat().st_size, 'sha256': hashfile(path)})
    return {'dataset_id': 'dem240', 'path': path, 'resolution_m': 240, 'coverage_label': 'synthetic fixture'}


def test_source_integrity_and_coordinate_sampling(raw_source, monkeypatch):
    record = verified_source(raw_source)
    monkeypatch.setattr(source_module, 'installed_sources', lambda: [record])
    with TerrainInputs(query(latitude_deg=-89.99, longitude_e_deg=0)) as terrain:
        assert terrain.site['dem_z_m'] == 100
        assert terrain.provenance()[0]['sha256'] == hashfile(raw_source['path'])
    with raw_source['path'].open('ab') as handle:
        handle.write(b'tamper')
    with pytest.raises(DomainError, match='DEM_INTEGRITY_FAILED'):
        verified_source(raw_source)


def test_no_dem_and_no_coordinate_coverage(raw_source, monkeypatch):
    monkeypatch.setattr(source_module, 'installed_sources', lambda: [])
    with pytest.raises(DomainError, match='DEM_NOT_INSTALLED'):
        with TerrainInputs(query()):
            pass
    monkeypatch.setattr(source_module, 'installed_sources', lambda: [verified_source(raw_source)])
    with pytest.raises(DomainError, match='OUTSIDE_DEM_COVERAGE'):
        with TerrainInputs(query(latitude_deg=-80)):
            pass


class SyntheticSphere:
    def __init__(self, request=None, missing=False):
        self.site = {'site_id': 'synthetic', 'lon_e_deg': 220, 'lat_deg': -89.5,
                     'dem_z_m': 0, 'dem_sha256': 'synthetic-only'}
        self.observer_source = {'dataset_id': 'synthetic', 'resolution_m': 240}
        self.layers = []
        self.missing = missing

    def sample(self, lon, lat, minimum_resolution_m=0):
        value = np.full(np.shape(lon), np.nan if self.missing else 0.)
        return value, np.zeros(value.shape, dtype=int)

    def provenance(self):
        return [{'dataset_id': 'synthetic-only', 'sha256': 'test'}]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_real_scanner_sphere_geometry_and_missing_data():
    terrain = SyntheticSphere()
    profiles = scan_horizons(terrain, {1, 2}, radius=300000, az_step=90)
    verify_profiles(profiles, terrain.site)
    for profile in profiles.values():
        assert profile.coverage_complete.all() and (profile.horizon_deg < 0).all()
        assert profile.horizon_deg.max() - profile.horizon_deg.min() < 1e-10
    unknown = scan_horizons(SyntheticSphere(missing=True), {1}, radius=300000, az_step=90)[1]
    assert unknown.horizon_deg.isna().all() and not unknown.coverage_complete.any()


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    from app.point_analysis import pipeline as module
    monkeypatch.setattr(module, 'TerrainInputs', SyntheticSphere)
    # Cheap analytically constructed horizon. The actual scanner is tested above.
    def analytic(terrain, heights, radius=400000, az_step=.125):
        output = {}
        from app.services.lunarsight.horizon import ray_positions
        for height in heights:
            azimuths = np.arange(0, 360, az_step)
            distance = np.sqrt(2 * 1737400 * height)
            lon, lat = ray_positions(220, -89.5, azimuths, [distance])
            output[height] = pd.DataFrame({'az_deg': azimuths, 'az_step_deg': az_step,
                'height_m': height, 'horizon_deg': ray_elevation(0, 0, height, distance),
                'coverage_complete': True, 'blocker_distance_m': distance, 'blocker_z_m': 0,
                'blocker_lon_e_deg': lon[:, 0], 'blocker_lat_deg': lat[:, 0]})
        return output
    monkeypatch.setattr(module, 'scan_horizons', analytic)
    monkeypatch.setattr(module, 'seam_checks', lambda terrain: [])
    def fetch(root, site, target, height, start, end, step, *args, **kwargs):
        grid = pd.date_range(start, end, freq=f'{step}min')
        df = pd.DataFrame({'az_deg': 90., 'el_deg': 5., 'row_present': True}, index=grid)
        return df, {'missing_timestamps': 0, 'missing_angles': 0, 'target': target, 'step_minutes': step}
    monkeypatch.setattr(module, 'fetch', fetch)
    return PointAnalysisPipeline(tmp_path)


def test_pipeline_numbers_boundaries_and_cache(pipeline, monkeypatch):
    request = query(min_sunlit_fraction=.8, min_earth_los_fraction=.8)
    stages = []
    result = pipeline.run(request, stages.append)
    assert result['decision'] == 'PASS' and result['validation']['passed']
    assert result['metrics_hours']['total_sun_hours'] == [1, 1]
    assert result['metrics_hours']['longest_dark_hours'] == [0, 0]
    assert len(result['timeline']) == 12  # Terminal sample must not add an interval.
    assert len(result['provenance']['ephemerides']) == 4
    monkeypatch.setattr('app.point_analysis.pipeline.fetch', lambda *a, **k: pytest.fail('cache missed'))
    assert pipeline.run(request)['result_id'] == result['result_id']
    location = pipeline.root / 'results' / result['result_id'] / 'result.json'
    location.write_text('{}')
    with pytest.raises(DomainError, match='RESULT_CACHE_INTEGRITY_FAILED'):
        pipeline.run(request)


def test_validation_gate_downgrades_nominal_pass(pipeline, monkeypatch):
    monkeypatch.setattr('app.point_analysis.pipeline.seam_checks', lambda terrain: [{'passed': False}])
    result = pipeline.run(query(min_sunlit_fraction=.8))
    assert result['nominal_sampled_decision'] == 'PASS'
    assert result['decision'] == 'INDETERMINATE' and not result['validation']['passed']


def test_soft_preferences_do_not_reject_point(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    original = module.fetch
    def blocked(*args, **kwargs):
        df, meta = original(*args, **kwargs)
        df['el_deg'] = -5
        return df, meta
    monkeypatch.setattr(module, 'fetch', blocked)
    result = pipeline.run(query(constraints={'max_darkness_hours': 0}))
    assert result['decision'] is None
    assert result['soft_constraint_checks']['max_darkness_hours'] == 'FAIL'
    assert result['metrics_hours']['longest_dark_hours'] == [1, 1]


def test_missing_ephemeris_preserves_unknown_bounds(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    original = module.fetch
    def missing(*args, **kwargs):
        df, meta = original(*args, **kwargs)
        df.loc[df.index[1:-1], ['az_deg', 'el_deg']] = np.nan
        df.loc[df.index[1:-1], 'row_present'] = False
        meta['missing_timestamps'] = len(df)-2
        return df, meta
    monkeypatch.setattr(module, 'fetch', missing)
    result = pipeline.run(query(min_sunlit_fraction=.8))
    low, high = result['metrics_hours']['total_sun_hours']
    assert low < high and high == 1
    assert result['decision'] == 'INDETERMINATE'
    assert not result['coverage']['ephemeris_complete']


def test_offline_miss_is_explicit(pipeline, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError('no exact query')
    monkeypatch.setattr('app.point_analysis.pipeline.fetch', missing)
    with pytest.raises(DomainError, match='HORIZONS_CACHE_MISS'):
        pipeline.run(query(offline=True))


def test_http_request_to_job_and_result(pipeline, tmp_path):
    jobs = PointAnalysisJobs(tmp_path / 'jobs-root', pipeline=pipeline)
    # Job result reader expects the pipeline's result directory.
    jobs.root = pipeline.root
    app.dependency_overrides[get_point_jobs] = lambda: jobs
    try:
        with TestClient(app) as client:
            response = client.post('/api/lunar/point/analyses', json=query(min_sunlit_fraction=.8).model_dump())
            assert response.status_code == 202
            identifier = response.json()['job_id']
            assert response.headers['location'].endswith(identifier)
            jobs.close()  # Deterministically wait for background completion.
            status = client.get(f'/api/lunar/point/analyses/{identifier}').json()
            assert status['status'] == 'succeeded'
            result = client.get(status['result_url'])
            assert result.status_code == 200 and result.json()['metrics_hours']['total_earth_los_hours'] == [1, 1]
            assert client.get('/api/lunar/point/analyses/not-a-job').status_code == 404
            invalid = client.post('/api/lunar/point/analyses', json={'latitude_deg': 100})
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(get_point_jobs, None)
        jobs.close()


def test_job_queue_bound_and_failure(tmp_path):
    release = Event()
    class Failure:
        root = tmp_path
        def run(self, request, progress):
            release.wait(5)
            raise DomainError('DEM_NOT_INSTALLED', 503)
    jobs = PointAnalysisJobs(tmp_path, pipeline=Failure(), max_pending=1)
    try:
        job = jobs.submit(query())
        with pytest.raises(DomainError, match='POINT_ANALYSIS_BUSY'):
            jobs.submit(query(min_sunlit_fraction=.5))
        with pytest.raises(DomainError, match='POINT_RESULT_NOT_READY'):
            jobs.result(job.job_id)
    finally:
        release.set()
        jobs.close()
    assert jobs.status(job.job_id).error_code == 'DEM_NOT_INSTALLED'


def test_changing_threshold_reuses_horizon_without_replaying_scan(pipeline, monkeypatch):
    first = pipeline.run(query(min_sunlit_fraction=.8))
    monkeypatch.setattr('app.point_analysis.pipeline.scan_horizons',
                        lambda *a, **k: pytest.fail('horizon cache missed'))
    second = pipeline.run(query(min_sunlit_fraction=.9))
    assert second['result_id'] != first['result_id']
    assert second['metrics_hours'] == first['metrics_hours']
    assert second['provenance']['geometry'] == first['provenance']['geometry']


def test_offline_reuses_exact_result(pipeline, monkeypatch):
    online = pipeline.run(query())
    monkeypatch.setattr('app.point_analysis.pipeline.fetch', lambda *a, **k: pytest.fail('unexpected network'))
    offline = pipeline.run(query(offline=True))
    assert offline['result_id'] == online['result_id']
    assert offline['request']['offline'] is True
    assert offline['execution'] == {'result_cache_hit': True, 'offline': True}


def test_horizon_cache_corruption_is_rejected(pipeline):
    first = pipeline.run(query())
    identity = first['provenance']['geometry']['identity']
    from app.planning.repository import digest
    path = pipeline.root / 'geometry' / digest(identity) / 'fine_h1.csv'
    path.write_text('corrupted')
    with pytest.raises(DomainError, match='HORIZON_CACHE_INTEGRITY_FAILED'):
        pipeline.run(query(min_sunlit_fraction=.9))


def test_abandoned_owner_is_reported_interrupted(tmp_path):
    jobs = PointAnalysisJobs(tmp_path)
    identifier = 'a'*32
    jobs.write(JobStatus(
        job_id=identifier, status='queued', stage='queued'))
    assert jobs.status(identifier).status == 'queued'
    jobs.close()
    assert jobs.status(identifier).error_code == 'POINT_JOB_INTERRUPTED'


def test_direct_api_returns_numbers_in_one_request(pipeline):
    from app.point_analysis.service import get_point_pipeline
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            response = client.post('/api/lunar/point/analyze', json=query(
                min_sunlit_fraction=.8, min_earth_los_fraction=.8).model_dump())
            assert response.status_code == 200
            result = response.json()
            assert result['decision'] == 'PASS'
            assert result['validation']['passed'] is True
            assert result['metrics_hours']['total_sun_hours'] == [1, 1]
            assert result['metrics_hours']['total_earth_los_hours'] == [1, 1]
            assert result['metrics_hours']['longest_dark_hours'] == [0, 0]
            assert 'job_id' not in result
            assert len(result['timeline']) == 12
            assert client.post('/api/lunar/point/analyze', json=query(latitude_deg=0).model_dump()
                | {'duration_hours': 1.01}).status_code == 422
            schema = client.get('/openapi.json').json()
            assert schema['paths']['/api/lunar/point/analyze']['post']['requestBody']['content']['application/json']['schema']['$ref'].endswith('/PointAnalysisRequest')
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)


def test_direct_api_busy_and_data_error_are_explicit(pipeline, monkeypatch):
    from filelock import FileLock
    from app.mission.identity import digest
    from app.point_analysis.service import get_point_pipeline
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            locks = pipeline.root / 'request-locks'
            locks.mkdir(exist_ok=True)
            key = digest(query().resolved().model_dump(exclude={'offline'}))
            with FileLock(str(locks / f'{key}.lock')):
                response = client.post('/api/lunar/point/analyze', json=query().model_dump())
                assert response.status_code == 429
                assert response.json()['detail']['code'] == 'POINT_ANALYSIS_BUSY'
            def missing(*args, **kwargs):
                raise DomainError('DEM_NOT_INSTALLED', 503)
            monkeypatch.setattr(pipeline, 'run', missing)
            response = client.post('/api/lunar/point/analyze', json=query().model_dump())
            assert response.status_code == 503 and response.json()['detail']['code'] == 'DEM_NOT_INSTALLED'
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)


def contact_query(**updates):
    return query(**{'min_sunlit_fraction': .8,
        'contact_requirements': {'min_contact_minutes': 20, 'setup_minutes': 5,
            'required_windows': 1, 'first_contact_deadline_minutes': 30}, **updates})


def earth_visible_after(monkeypatch, minutes):
    from app.point_analysis import pipeline as module
    original = module.fetch
    def delayed(*args, **kwargs):
        frame, meta = original(*args, **kwargs)
        if args[2] == 399:
            frame['el_deg'] = np.where(frame.index >= frame.index[0]+pd.Timedelta(minutes=minutes), 5., -5.)
        return frame, meta
    monkeypatch.setattr(module, 'fetch', delayed)


def test_contact_and_sun_are_primary_in_direct_api(pipeline):
    from app.point_analysis.service import get_point_pipeline
    app.dependency_overrides[get_point_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            response = client.post('/api/lunar/point/analyze', json=contact_query().model_dump())
            assert response.status_code == 200
            result = response.json()
            assert result['decision'] == 'PASS'
            assert result['requirement_policy'] == 'availability-and-contact-windows-v1'
            assert result['constraint_checks']['min_sunlit_fraction'] == 'PASS'
            assert result['constraint_checks']['contact.first_contact_deadline_minutes'] == 'PASS'
            assert 'min_earth_los_fraction' not in result['constraint_checks']
            assert result['contact_analysis']['metrics']['qualified_windows_count'] == 1
            assert result['contact_analysis']['metrics']['longest_contact_minutes_bounds'] == [60, 60]
            assert result['contact_analysis']['requirements']['decision'] == 'PASS'
    finally:
        app.dependency_overrides.pop(get_point_pipeline, None)


def test_contact_deadline_fails_even_with_positive_total_los(pipeline, monkeypatch):
    earth_visible_after(monkeypatch, 40)
    result = pipeline.run(contact_query())
    assert result['validation']['passed'] is True
    assert result['metrics_hours']['total_earth_los_hours'][0] > 0
    assert result['constraint_checks']['contact.first_contact_deadline_minutes'] == 'FAIL'
    assert result['decision'] == 'FAIL'


def test_contact_pass_and_sun_fail_is_overall_fail(pipeline, monkeypatch):
    from app.point_analysis import pipeline as module
    original = module.fetch
    def dark(*args, **kwargs):
        frame, meta = original(*args, **kwargs)
        if args[2] == 10:
            frame['el_deg'] = -5
        return frame, meta
    monkeypatch.setattr(module, 'fetch', dark)
    result = pipeline.run(contact_query())
    assert result['contact_analysis']['requirements']['decision'] == 'PASS'
    assert result['constraint_checks']['min_sunlit_fraction'] == 'FAIL'
    assert result['decision'] == 'FAIL'


def test_soft_blackout_failure_does_not_reject_contact_and_sun(pipeline, monkeypatch):
    earth_visible_after(monkeypatch, 40)
    result = pipeline.run(contact_query(contact_requirements={'min_contact_minutes': 10,
        'first_contact_deadline_minutes': 60}, constraints={'max_earth_blackout_hours': 0}))
    assert result['validation']['passed'] is True
    assert result['soft_constraint_checks']['max_earth_blackout_hours'] == 'FAIL'
    assert result['decision'] == 'PASS'


def test_contact_deadline_is_included_in_sensitivity_gate(pipeline, monkeypatch):
    earth_visible_after(monkeypatch, 1)
    result = pipeline.run(contact_query(contact_requirements={'min_contact_minutes': 20,
        'first_contact_deadline_minutes': 22}))
    diagnostics = result['validation']['sensitivity']['time_5min_vs_1min']
    assert result['constraint_checks']['contact.first_contact_deadline_minutes'] == 'FAIL'
    assert diagnostics['constraint_checks']['contact.first_contact_deadline_minutes'] == 'PASS'
    assert diagnostics['passed'] is False
    assert result['decision'] == 'FAIL'  # Hard rejection is retained despite numerical disagreement.
    assert result['contact_analysis']['requirements']['decision'] == 'FAIL'


@pytest.mark.parametrize('contact', [
    {}, {'min_contact_minutes': 0}, {'min_contact_minutes': True},
    {'min_contact_minutes': 10, 'setup_minutes': -1},
    {'min_contact_minutes': 10, 'required_windows': 0},
    {'min_contact_minutes': 10, 'first_contact_deadline_minutes': 61}])
def test_contact_schema_rejects_invalid_requirements(contact):
    with pytest.raises(ValidationError):
        contact_query(contact_requirements=contact)
