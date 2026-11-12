#!/usr/bin/env python3
"""Check chatbot-fix routes and preserved computing against installed NASA/JPL inputs.

No model calls or generated science inputs. LLM provider readiness is reported
separately and never counted as a successful live inference.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter

import httpx

from verify_indeterminate_resolution import verify

ROOT = Path(__file__).resolve().parents[1]


def verify_merged(base_url, offline=True):
    report = {'passed': False, 'point_compare_search_csv': verify(base_url, offline)}
    request = json.loads((ROOT/'docs/examples/point-analysis-long-end-date-request.json').read_text())
    request['offline'] = offline
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=600) as client:
        first = perf_counter()
        response = client.post('/api/lunar/point/analyze', json=request)
        response.raise_for_status()
        result = response.json()
        first_seconds = perf_counter()-first
        assert result['request']['duration_hours'] == 240
        assert result['end_utc'] == '2026-11-27T00:00:00Z'
        assert result['decision'] == 'PASS'
        assert result['validation']['mission_path']['passed'] is True
        again = perf_counter()
        response = client.post('/api/lunar/point/analyze', json=request)
        response.raise_for_status()
        repeated = response.json()
        repeat_seconds = perf_counter()-again
        assert repeated['result_id'] == result['result_id']
        assert repeated['metrics_hours'] == result['metrics_hours']
        assert repeated['execution']['result_cache_hit'] is True
        report['long_mission'] = {'result_id': result['result_id'], 'duration_hours': 240,
            'decision': result['decision'], 'full_validation_passed': result['validation']['passed'],
            'mission_path_passed': result['validation']['mission_path']['passed'],
            'resolution_policy': result['resolution']['policy_version'],
            'first_call_seconds': first_seconds, 'first_result_cache_hit': result['execution']['result_cache_hit'],
            'repeat_call_seconds': repeat_seconds, 'repeat_result_cache_hit': True}
        response = client.get('/openapi.json'); response.raise_for_status()
        paths = response.json()['paths']
        expected = ['/api/assistant/sessions/{session_id}/messages',
            '/api/assistant/runs/{run_id}/cancel', '/api/lunar/point/analyze',
            '/api/lunar/terrain/south-polar-cap']
        assert all(path in paths for path in expected)
        report['routes_present'] = expected
        response = client.get('/api/lunar/terrain/south-polar-cap', params={'samples': 257})
        response.raise_for_status()
        assert response.json()['coverage_status'] == 'COVERED'
        report['real_terrain_mesh_covered'] = True
        response = client.get('/api/assistant/capabilities'); response.raise_for_status()
        capabilities = response.json()
        report['llm'] = {key: capabilities[key] for key in ('provider', 'provider_configured', 'assistant_enabled')}
        report['llm']['live_inference_run'] = False
        report['llm']['note'] = 'Provider inference is a separate check; this script does not call an LLM.'
    report['passed'] = True
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8001')
    parser.add_argument('--online', action='store_true', help='Allow JPL retrieval for missing exact query spans')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify_merged(args.base_url, not args.online)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': report['passed'], 'long_mission': report['long_mission'], 'llm': report['llm']}, indent=2))
