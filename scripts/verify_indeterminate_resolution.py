#!/usr/bin/env python3
"""Check full-sun mission validation and immediate hard rejection on a real API.

NASA terrain and exact JPL queries are required; no LLM or synthetic science.
"""
import argparse
import csv
from datetime import datetime, timedelta
import io
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(base_url, offline=False):
    report = {"passed": True, "tolerances": {"horizon_deg": .1, "event_minutes": 5, "duration_minutes": 10}, "cases": []}
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=900) as client:
        for expected in ('PASS', 'FAIL'):
            path = ROOT/'docs/examples'/f'point-revalidation-{expected.lower()}-request.json'
            request = json.loads(path.read_text())
            request['offline'] = offline
            outcomes = {}
            for enabled in (False, True):
                response = client.post('/api/lunar/point/analyze', json={**request, 'resolve_indeterminate': enabled})
                response.raise_for_status()
                outcomes[enabled] = response.json()
            before, after = outcomes[False], outcomes[True]
            assert before['decision'] == ('INDETERMINATE' if expected == 'PASS' else 'FAIL'), before['decision']
            assert after['decision'] == expected, after['decision']
            if expected == 'PASS':
                assert after['validation']['passed'] is False  # Preserve the full-circle failure.
                assert after['validation']['mission_path']['passed'] is True
                assert after['metrics_hours']['total_sun_hours'] == [72, 72]
                assert after['resolution']['status'] == 'resolved'
            else:
                assert after['validation']['passed'] is False
                assert after['metrics_hours']['total_sun_hours'] == [0, 0]
                assert after['constraint_checks']['min_sunlit_fraction'] == 'FAIL'
                assert after['resolution']['refinement_rounds'] == 0
            assert before['validation']['tolerances'] == after['validation']['tolerances'] == report['tolerances']
            assert after['resolution']['refinement_rounds'] <= 2
            assert {k:v for k,v in before['request'].items() if k!='resolve_indeterminate'} == {k:v for k,v in after['request'].items() if k!='resolve_indeterminate'}
            planning = {k:v for k,v in request.items() if k not in {'site_id', 'latitude_deg', 'longitude_e_deg', 'start_utc', 'panel_height_m', 'antenna_height_m'}}
            planning.update(data_source='coordinate', targets=[{k:request[k] for k in ('latitude_deg', 'longitude_e_deg')}],
                arrival_utc=request['start_utc'], hardware={'sun_panel':request['panel_height_m'], 'earth_antenna':request['antenna_height_m']})
            until = (datetime.fromisoformat(request['start_utc'].replace('Z', '+00:00'))+timedelta(minutes=15)).isoformat()
            planning_results = []
            for endpoint, body in (('/planning/compare', planning), ('/planning/windows/search',
                    {**planning, 'until_utc':until, 'start_step_minutes':15, 'max_results':1})):
                response = client.post('/api'+endpoint, json=body)
                response.raise_for_status()
                result = response.json()
                assert result['coverage']['indeterminate'] == 0
                assert result['apply_allowed'] is (expected == 'PASS')
                candidate = result['candidates'][0]
                assert candidate['analysis_result_id'] == after['result_id']
                assert candidate['decision'] == expected
                assert candidate['metrics'] == after['metrics_hours']
                assert candidate['resolution'] == after['resolution']
                planning_results.append(result)
            assert planning_results[0]['candidates'][0]['candidate_id'] == planning_results[1]['candidates'][0]['candidate_id']
            export = client.get(f"/api/planning/results/{planning_results[0]['result_id']}", params={'format':'csv'})
            export.raise_for_status()
            row = next(csv.DictReader(io.StringIO(export.text)))
            assert json.loads(row['resolution_json']) == after['resolution']
            assert json.loads(row['validation_json']) == after['validation']
            report['cases'].append({'request_file': str(path.relative_to(ROOT)), 'before': before['decision'],
                'after': after['decision'], 'result_id': after['result_id'], 'validation_passed': after['validation']['passed'],
                'mission_path': after['validation'].get('mission_path'), 'reason_codes':after['validation']['reason_codes'],
                'refinement_rounds': after['resolution']['refinement_rounds'], 'cross_routes': ['point','compare','search','csv'],
                'metrics_hours': after['metrics_hours'], 'configuration': after['validation']['configuration']})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = verify(args.base_url, args.offline)
    text = json.dumps(report, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')
