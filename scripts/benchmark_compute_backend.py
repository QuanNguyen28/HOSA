"""Microbenchmark real cached outputs; no JPL calls, no synthetic science inputs."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.mission.models import MissionRequest, ContactRequirements
from app.mission.evaluation import frame_contacts, records
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.point_analysis.service import calculate
from app.services.lunarsight.contact_windows import analyze_contacts


def benchmark(result_path):
    result = json.loads(Path(result_path).read_text())
    request = MissionRequest.model_validate(result['request'])
    pipeline = PointAnalysisPipeline(ROOT/'data/cache/point-analysis')
    cached = pipeline.lookup_cached(request)
    if cached is None or cached['result_id'] != result['result_id']:
        raise ValueError('A hash-verified completed result is required')
    result = cached
    def timed(fn):
        values = []
        for _ in range(5):
            start = perf_counter(); value = fn(); values.append(perf_counter()-start)
        return median(values), value
    cache_seconds, again = timed(lambda: calculate(request, pipeline))
    assert again['result_id'] == result['result_id'] and again['execution']['result_cache_hit']
    frame = pd.DataFrame(result['timeline'])
    for field in ('start_utc','end_utc'):
        frame[field] = pd.to_datetime(frame[field], utc=True)
    contact_request = request.model_copy(update={'contact_requirements':ContactRequirements(
        min_contact_minutes=30, setup_minutes=5, required_windows=1, first_contact_deadline_minutes=120)})
    payload = {'request':contact_request.model_dump(), 'end_utc':request.end_utc, 'validation':result['validation']}
    def reference():
        return analyze_contacts({**payload, 'timeline':records(frame)}, **contact_request.contact_requirements.model_dump())
    before, original = timed(reference)
    after, optimized = timed(lambda: frame_contacts(contact_request, frame, payload))
    assert optimized == original
    compact = frame.copy()
    for key in ('sun_state','earth_state','joint_state','sun_coverage_flag','earth_coverage_flag'):
        if key in compact:
            compact[key] = pd.Categorical(compact[key])
    return {'result_id':result['result_id'], 'duration_hours':request.duration_hours,
        'native_intervals':len(frame), 'cached_request_median_seconds':cache_seconds,
        'contact_reference_median_seconds':before, 'contact_optimized_median_seconds':after,
        'contact_speedup':before/after, 'contact_outputs_identical':True,
        'timeline_dataframe_bytes_before':int(frame.memory_usage(deep=True).sum()),
        'timeline_dataframe_bytes_with_categories':int(compact.memory_usage(deep=True).sum()),
        'scope':'Microbenchmark only; excludes cold terrain scans and uncached JPL network time.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=benchmark(args.result)
    text=json.dumps(report,indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text,end='')
