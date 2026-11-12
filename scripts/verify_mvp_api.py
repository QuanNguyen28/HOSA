#!/usr/bin/env python3
"""Exercise a running MVP against real, documented coordinate requests (no LLM)."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(base_url, offline=False):
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=600) as client:
        def post(path, body):
            response = client.post('/api' + path, json=body)
            response.raise_for_status()
            return response.json()
        direct = {}
        for name in ('pass', 'fail'):
            query = json.loads((ROOT/f'docs/examples/point-analysis-outside-{name}-request.json').read_text())
            result = post('/lunar/point/analyze', {**query, 'offline': offline})
            assert result['decision'] == name.upper(), result['decision']
            assert result['validation']['passed'] is True
            direct[name] = result
        query = json.loads((ROOT/'docs/examples/planning-compare-coordinate-request.json').read_text())
        query['offline'] = offline
        compared = post('/planning/compare', query)
        end = datetime.fromisoformat(query['arrival_utc'].replace('Z', '+00:00')) + timedelta(minutes=15)
        searched = post('/planning/windows/search', {**query, 'until_utc': end.isoformat(),
            'start_step_minutes': 15, 'max_results': 5, 'non_overlapping': True})
        for result in (compared, searched):
            assert result['coverage']['pass'] == result['coverage']['fail'] == 1
            assert result['coverage']['indeterminate'] == 0
            assert result['status'] == 'FEASIBLE' and result['apply_allowed']
            for candidate in result['candidates']:
                reference = direct[candidate['decision'].lower()]
                assert candidate['analysis_result_id'] == reference['result_id']
                assert candidate['metrics'] == reference['metrics_hours']
                assert candidate['validation'] == reference['validation']
                assert candidate['constraint_states'] == reference['constraint_checks']
        chosen = next(c for c in compared['candidates'] if c['decision'] == 'PASS')
        assert searched['candidates'][0]['candidate_id'] == chosen['candidate_id']
        for format in ('json', 'csv'):
            response = client.get(f"/api/planning/results/{compared['result_id']}", params={'format': format})
            response.raise_for_status()
            assert 'attachment' in response.headers.get('content-disposition', '')
            if format == 'json':
                assert response.json() == compared
            else:
                assert 'candidate_id' in response.text and direct['fail']['decision'] in response.text
        return {'passed': True, 'point_decisions': {k: v['decision'] for k, v in direct.items()},
            'compare': compared['coverage'], 'search': searched['coverage'], 'exports': ['json', 'csv']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--offline', action='store_true', help='Use only exact matching JPL cache entries')
    args = parser.parse_args()
    print(json.dumps(verify(args.base_url, args.offline), indent=2))
