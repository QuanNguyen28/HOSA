"""Measure real 72h missions with isolated caches and unchanged NASA/JPL inputs.

No network calls and no synthetic science. Existing DEM/ephemeris artifacts must
be installed. Results are never taken from a completed-result cache on first run.
"""
import argparse
from copy import deepcopy
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.services.lunarsight.acquire import hashfile

SOURCE = ROOT/'data/cache/point-analysis'


def seed(root, base_only=False):
    raw = root/'raw/horizons'; raw.mkdir(parents=True)
    for path in (SOURCE/'raw/horizons').glob('*.json'):
        # Hard links are read-only inputs; the adapter writes parsed CSV/header
        # files only in this isolated root. Never link a .part file.
        os.link(path, raw/path.name)
    for receipt in (SOURCE/'geometry').glob('*/receipt.json'):
        identity = json.loads(receipt.read_text())['identity']
        if base_only and identity['az_steps_deg'][0] != .125:
            continue
        dest = root/'geometry'/receipt.parent.name
        dest.mkdir(parents=True)
        for path in [receipt, *receipt.parent.glob('*.csv')]:
            os.link(path, dest/path.name)


def measured(pipeline_class, root, request):
    timing, stages = {}, []
    class Measured(pipeline_class):
        def geometry(self, *args, **kwargs):
            start = perf_counter()
            value = super().geometry(*args, **kwargs)
            timing['geometry_seconds'] = timing.get('geometry_seconds', 0)+perf_counter()-start
            return value
        def ephemerides(self, *args, **kwargs):
            start = perf_counter()
            value = super().ephemerides(*args, **kwargs)
            timing['ephemeris_seconds'] = timing.get('ephemeris_seconds', 0)+perf_counter()-start
            return value
        def evaluate_geometry(self, *args, **kwargs):
            start = perf_counter()
            value = super().evaluate_geometry(*args, **kwargs)
            timing['evaluation_seconds'] = timing.get('evaluation_seconds', 0)+perf_counter()-start
            return value
    pipeline = Measured(root)
    start = perf_counter()
    result = pipeline.run(request, lambda stage: stages.append({'stage': stage, 'seconds':perf_counter()-start}))
    elapsed = perf_counter()-start
    assert not result['execution']['result_cache_hit']
    start = perf_counter(); cached = pipeline.lookup_cached(request); cache_seconds = perf_counter()-start
    assert cached['result_id'] == result['result_id'] and cached['execution']['result_cache_hit']
    return result, {**timing, 'elapsed_seconds':elapsed, 'cached_result_seconds':cache_seconds,
        'decision':result['decision'], 'result_id':result['result_id'], 'duration_hours':request.duration_hours,
        'full_validation_passed':result['validation']['passed'],
        'mission_bounds_passed':result['validation'].get('mission_path',{}).get('passed',False),
        'refinement_rounds':result['resolution']['refinement_rounds'], 'stages':stages,
        'metrics_hours':result['metrics_hours'], 'reason_codes':result['validation']['reason_codes']}


def requests():
    paths = ['point-revalidation-pass-request.json','point-analysis-bounded-site04-request.json',
             'point-revalidation-fail-request.json']
    output = [(name, json.loads((ROOT/'docs/examples'/name).read_text())) for name in paths]
    strict = deepcopy(output[1][1]); strict['min_earth_los_fraction'] = 1.
    output.append(('Site04-strict-100pct-Earth', strict))
    return [(name,MissionRequest.model_validate({**q,'offline':True})) for name,q in output]


def verify(before_path=None, publish=False):
    report = {'passed':False, 'scope':'Real 72h missions. Isolated result caches; verified existing NASA DEM/JPL raw inputs; network excluded.',
              'cases':[], 'first_refinement_comparison':None}
    cases = requests()
    # Cold refinement: both runs have base geometry/raw JPL, neither has refined
    # geometry or completed results. This is not a full cold NASA/JPL benchmark.
    if before_path:
        report['before_pipeline_sha256'] = hashlib.sha256(before_path.read_bytes()).hexdigest()
        spec = importlib.util.spec_from_file_location('app.point_analysis.before_proof', before_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.RESOLUTION_VERSION = 'indeterminate-resolution-2.0'
        comparison = {}
        for label, cls in [('before',module.PointAnalysisPipeline),('after',PointAnalysisPipeline)]:
            with TemporaryDirectory(prefix='audit-refinement-', dir=SOURCE) as directory:
                root=Path(directory); seed(root,base_only=True)
                result, timing = measured(cls,root,cases[0][1])
                assert result['decision']=='PASS'
                comparison[label]=timing
                print('REFINEMENT', label, json.dumps(timing), flush=True)
        comparison['speedup']=comparison['before']['elapsed_seconds']/comparison['after']['elapsed_seconds']
        report['first_refinement_comparison']=comparison
    with TemporaryDirectory(prefix='audit-spots-', dir=SOURCE) as directory:
        root=Path(directory);seed(root)
        for name, request in cases:
            before, timing_before=measured(PointAnalysisPipeline,root,request.model_copy(update={'resolve_indeterminate':False}))
            after,timing=measured(PointAnalysisPipeline,root,request.model_copy(update={'resolve_indeterminate':True}))
            report['cases'].append({'case':name,'request':request.model_dump(),'without_resolution':timing_before,'with_resolution':timing,
                'mission_path':after['validation'].get('mission_path')})
            if publish:
                # Commit complete result artifacts only after validating identity
                # and hashes. This warms the real API using real offline data.
                for result in (before, after):
                    src=root/'results'/result['result_id'];dest=SOURCE/'results'/result['result_id']
                    receipt=json.loads((src/'receipt.json').read_text())
                    assert PointAnalysisPipeline.cached_result(src,receipt['identity'])['result_id']==result['result_id']
                    for filename, checksum in result['provenance']['artifacts'].items():
                        assert hashfile(src/filename)==checksum
                    if not dest.exists():
                        import shutil
                        shutil.copytree(src,dest)
            print('CASE',name,timing_before['decision'],timing['decision'],timing['elapsed_seconds'],flush=True)
    assert [c['with_resolution']['decision'] for c in report['cases']]==['PASS','PASS','FAIL','INDETERMINATE']
    report['indeterminate_before']=sum(c['without_resolution']['decision']=='INDETERMINATE' for c in report['cases'])
    report['indeterminate_after']=sum(c['with_resolution']['decision']=='INDETERMINATE' for c in report['cases'])
    report['passed']=True
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-pipeline',type=Path)
    parser.add_argument('--publish-verified-results',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=verify(args.before_pipeline,args.publish_verified_results)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'indeterminate_before':report['indeterminate_before'],
        'indeterminate_after':report['indeterminate_after']},indent=2))
