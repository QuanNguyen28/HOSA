"""Performance paths must preserve integrity and exact sampled-model outputs."""
import json
from pathlib import Path
import sys

import pandas as pd
from filelock import FileLock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from test_point_analysis import pipeline, query
from app.point_analysis.service import calculate, PointAnalysisJobs
from app.point_analysis.ephemeris_plan import segments
from app.mission.evaluation import frame_contacts, records
from app.mission.models import ContactRequirements
from app.services.lunarsight.contact_windows import analyze_contacts
from app.services.lunarsight.horizons import request_params, ADAPTER_VERSION
from app.services.lunarsight.acquire import JPL
from app.services.lunarsight.terrain import R


def test_cached_direct_and_queued_requests_bypass_busy_compute_worker(pipeline, monkeypatch):
    from app.mission.identity import digest
    request = query(min_sunlit_fraction=.8)
    expected = pipeline.run(request)
    monkeypatch.setattr(pipeline, 'run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('cache must bypass computation')))
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline, max_pending=0)
    try:
        locks = pipeline.root/'request-locks'
        locks.mkdir(exist_ok=True)
        key = digest(request.resolved().model_dump(exclude={'offline'}))
        with FileLock(str(locks/f'{key}.lock')):
            direct = calculate(request, pipeline)
            status = jobs.submit(request)
        assert direct['result_id'] == expected['result_id'] and direct['execution']['result_cache_hit']
        assert status.status == 'succeeded' and status.stage == 'cached'
        assert jobs.result(status.job_id)['metrics_hours'] == expected['metrics_hours']
        assert jobs.result(status.job_id)['execution']['result_cache_hit']
    finally:
        jobs.close()


def test_short_mission_completes_while_multiyear_job_is_running(pipeline, monkeypatch):
    from threading import Event
    import time
    entered, release = Event(), Event()
    original = pipeline.run
    def run(request, progress):
        if request.duration_hours > 168:
            entered.set()
            assert release.wait(10)
            return {'result_id': 'synthetic-bulk-job'}
        return original(request, progress)
    monkeypatch.setattr(pipeline, 'run', run)
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline)
    try:
        long = jobs.submit(query(duration_hours=17520.))
        assert entered.wait(5)
        short = jobs.submit(query(min_sunlit_fraction=.8))
        deadline = time.monotonic()+5
        while jobs.status(short.job_id).status in {'queued', 'running'} and time.monotonic()<deadline:
            time.sleep(.01)
        assert jobs.status(short.job_id).status == 'succeeded'
        assert jobs.status(long.job_id).status == 'running'
        assert jobs.result(short.job_id)['decision'] == 'PASS'
    finally:
        release.set()
        jobs.close()


def test_concurrent_missions_share_one_integrity_checked_geometry_build(pipeline, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from app.point_analysis import pipeline as module
    counts, guard, start = [], Lock(), Barrier(2)
    scanner = module.scan_horizons
    def scan(*args, **kwargs):
        with guard:
            counts.append((kwargs.get('radius', 400000), kwargs['az_step']))
        return scanner(*args, **kwargs)
    monkeypatch.setattr(module, 'scan_horizons', scan)
    def run(threshold):
        start.wait(timeout=5)
        return calculate(query(min_sunlit_fraction=threshold), pipeline)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, threshold) for threshold in (.5, .8)]
        results = [future.result(timeout=10) for future in futures]
    assert all(result['decision'] == 'PASS' for result in results)
    assert sorted(counts) == [(300000, .25), (400000, .125)]


def test_concurrent_identical_jpl_queries_download_once_and_preserve_receipt(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    import requests
    from test_science import fixture
    from app.services.lunarsight.horizons import fetch
    from app.services.lunarsight.acquire import hashfile
    payload = fixture('2026-Nov-14 00:00:00,*, , 359.95, 2,\n'
                      '2026-Nov-14 00:05:00,*, , 0, 2,\n'
                      '2026-Nov-14 00:10:00,*, , 0.05, 2,')
    body = json.dumps(payload).encode()
    barrier, guard, calls = Barrier(2), Lock(), []
    class Response:
        url = JPL
        headers = {'Content-Type':'application/json'}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def raise_for_status(self): pass
        def iter_content(self,size): yield body
    def get(*args, **kwargs):
        with guard:
            calls.append(1)
        return Response()
    monkeypatch.setattr(requests, 'get', get)
    site = {'site_id':'synthetic','lon_e_deg':220.,'lat_deg':-89.5,
            'dem_z_m':1000.,'dem_sha256':'synthetic-only'}
    def run():
        barrier.wait(timeout=5)
        return fetch(tmp_path,site,10,1.,'2026-11-14T00:00:00Z',
                     '2026-11-14T00:10:00Z',5,R,R)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert len(calls) == 1
    pd.testing.assert_frame_equal(results[0][0],results[1][0])
    for _,receipt in results:
        assert receipt['sha256'] == hashfile(tmp_path/receipt['raw_file'])
        assert receipt['missing_timestamps'] == receipt['missing_angles'] == 0


def test_fast_contact_run_coalescing_matches_full_normalizer_with_unknowns_and_boundaries(pipeline):
    request = query(contact_requirements={'min_contact_minutes': 10, 'setup_minutes': 2,
        'required_windows':2, 'first_contact_deadline_minutes':40})
    result = pipeline.run(request)
    frame = pd.DataFrame(result['timeline'])
    for key in ('start_utc', 'end_utc'):
        frame[key] = pd.to_datetime(frame[key], utc=True)
    frame['earth_state'] = list('VV??BBVVVVBB')
    payload = {'request':request.model_dump(), 'end_utc':request.end_utc,
               'validation':{'passed':True}, 'timeline':records(frame)}
    reference = analyze_contacts(payload, **request.contact_requirements.model_dump())
    assert frame_contacts(request, frame, payload) == reference


def test_ephemeris_plan_reuses_overlapping_spans_only_for_exact_observer(tmp_path):
    site = {'site_id':'coordinate','lon_e_deg':220,'lat_deg':-89.5,'dem_z_m':0,'dem_sha256':'checked'}
    raw = tmp_path/'raw/horizons'; raw.mkdir(parents=True)
    start, end = '2026-11-17T00:00:00Z', '2026-11-27T00:00:00Z'
    params = request_params(10,220,-89.5,0,1,R,R,'2026-11-14T00:00:00Z','2026-11-21T00:00:00Z',1)
    record = {'identity':{'method_version':ADAPTER_VERSION,'site_id':'coordinate','dataset_sha256':'checked',
                         'observer_height_m':1,'endpoint':JPL,'params':params}}
    (raw/'coordinate_sun_1min_hint.receipt.json').write_text(json.dumps(record))
    (raw/'coordinate_sun_1min_hint.json').write_text('{}')  # Planner hint only; fetch must validate actual bytes.
    plan = segments(tmp_path,site,10,1,start,end,1)
    assert len(plan) == 2 and plan[0][:2] == (pd.Timestamp(start),pd.Timestamp('2026-11-21T00:00:00Z'))
    assert plan[0][2] == pd.Timestamp('2026-11-14T00:00:00Z')
    assert plan[1][0] == plan[0][1] and plan[-1][1] == pd.Timestamp(end)
    incompatible = segments(tmp_path,site,10,2,start,end,1)
    assert len(incompatible) == 1 and incompatible[0][2] == pd.Timestamp(start)


def test_identical_pending_jobs_are_coalesced_and_keep_exact_request(pipeline, monkeypatch):
    from threading import Event
    entered, release = Event(), Event()
    original = pipeline.run
    def slow(request, progress):
        entered.set()
        assert release.wait(timeout=10)
        return original(request, progress)
    monkeypatch.setattr(pipeline, 'run', slow)
    jobs = PointAnalysisJobs(root=pipeline.root, pipeline=pipeline, max_pending=1)
    request = query(min_sunlit_fraction=.8)
    try:
        first = jobs.submit(request)
        assert entered.wait(timeout=5)
        repeated = jobs.submit(request)
        assert repeated.job_id == first.job_id
        assert jobs.read(first.job_id)['request'] == request.model_dump()
        assert len(jobs.active) == 1
    finally:
        release.set()
        jobs.close()
