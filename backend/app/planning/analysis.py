"""Adapt shared mission evaluation into planning candidates; no separate decisions."""
import pandas as pd

from app.core.errors import DomainError
from app.mission.evaluation import events, evaluate, VALIDATION_VERSION
from app.mission.metrics import validate_metrics
from app.mission.snapshot import SnapshotProvider, sensitivity_summary
from .models import Candidate
from .repository import digest


def target_id(target):
    return target.site_id or 'coordinate-' + digest(target.model_dump(exclude_none=True))[:12]


def verify_result(result, request, frame):
    """Reject a provider/cache contract mismatch before ranking or explaining."""
    validate_metrics(result['metrics_hours'], request.duration_hours)
    try:
        expected = evaluate(request, frame, result['validation'])
    except DomainError as error:
        raise DomainError('ENGINE_CONTRACT_ERROR', 502) from error
    for key in ('metrics_hours', 'constraint_checks', 'nominal_sampled_decision', 'decision', 'soft_constraint_checks'):
        if result[key] != expected[key]:
            raise DomainError('ENGINE_CONTRACT_ERROR', 502)
    if result['validation'].get('policy_version') != VALIDATION_VERSION:
        raise DomainError('ENGINE_CONTRACT_ERROR', 502)
    point = request.resolved()
    if any(abs(result['coordinate'][key] - getattr(point, key)) > 1e-10 for key in ('latitude_deg', 'longitude_e_deg')):
        raise DomainError('ENGINE_CONTRACT_ERROR', 502)


def analyze_candidate(query, index=None, *, target=None, snapshot=None, point_pipeline=None):
    target = target or query.mission_targets()[0]
    request = query.mission(target)
    identity = target_id(target)
    try:
        if query.data_source == 'coordinate':
            from app.point_analysis.service import calculate, get_point_pipeline
            result = calculate(request, point_pipeline or get_point_pipeline())
            frame = pd.DataFrame(result['timeline'])
            for key in ('start_utc', 'end_utc'):
                frame[key] = pd.to_datetime(frame[key], utc=True)
            summary = sensitivity_summary(request, result)
        else:
            result = (snapshot or SnapshotProvider()).analyze(target, request)
            frame = result['timeline_frame']
            summary = result['sensitivity']
        verify_result(result, request, frame)
        metric = result['metrics_hours']
        violations = []
        for name, state in result['constraint_checks'].items():
            if state != 'FAIL':
                continue
            violation = {'constraint': name}
            if name in ('min_sunlit_fraction', 'min_earth_los_fraction'):
                limit = getattr(request, name)
                key = 'total_sun_hours' if name == 'min_sunlit_fraction' else 'total_earth_los_hours'
                lo, hi = [v/request.duration_hours for v in metric[key]]
                violation.update(limit=limit, unit='fraction', shortfall_bounds=[max(0., limit-hi), max(0., limit-lo)])
            violations.append(violation)
        event_rows = []
        for row in events(frame):
            if row['target'] not in ('sun', 'earth') or row['state'] not in ('B', '?'):
                continue
            body = row['target']
            samples = frame[(frame.start_utc >= pd.Timestamp(row['start_utc'])) & (frame.end_utc <= pd.Timestamp(row['end_utc']))]
            clearance = samples[f'{body}_clearance_deg']
            worst = samples.loc[clearance.idxmin()] if clearance.notna().any() else samples.iloc[0]
            def value(key):
                v = worst.get(f'{body}_{key}')
                return None if pd.isna(v) else v.item() if hasattr(v, 'item') else v
            event_rows.append({'body': body, 'state': row['state'],
                'start_utc': row['start_utc'].replace('+00:00', 'Z'), 'end_utc': row['end_utc'].replace('+00:00', 'Z'),
                'duration_hours': (pd.Timestamp(row['end_utc'])-pd.Timestamp(row['start_utc'])).total_seconds()/3600,
                'worst_sample': {'at_utc': worst.start_utc.isoformat().replace('+00:00', 'Z'),
                    'azimuth_deg': value('az_deg'), 'elevation_deg': value('el_deg'),
                    'horizon_deg': value('horizon_deg'), 'clearance_deg': value('clearance_deg'),
                    'coverage_flag': value('coverage_flag')}})
        event_rows.sort(key=lambda e: (-e['duration_hours'], e['start_utc']))
        context = {}
        for body, key in (('sun', 'longest_dark_hours'), ('earth', 'longest_blackout_hours')):
            worst = next((e for e in event_rows if e['body'] == body and e['state'] == 'B'), None)
            context[key] = {'scope': 'within_mission_window', 'outside_window_duration_known': False,
                'touches_window_edge': bool(worst and (pd.Timestamp(worst['start_utc']) == pd.Timestamp(request.start_utc)
                    or pd.Timestamp(worst['end_utc']) == pd.Timestamp(request.end_utc)))}
        return Candidate(site_id=identity, candidate_id=f'{identity}@{index if index is not None else request.start_utc}',
            start_index=index, start_utc=request.start_utc, end_utc=request.end_utc,
            decision=result['decision'] or 'INDETERMINATE', nominal_sampled_decision=result['nominal_sampled_decision'],
            metrics=metric, constraint_states=result['constraint_checks'], validation=result['validation'],
            soft_constraint_states=result['soft_constraint_checks'], soft_violations=result.get('soft_violations', []),
            violations=violations, events=event_rows, metric_context=context, decisive_event=None,
            sensitivity=summary, contact_analysis=result.get('contact_analysis'), coordinate=result.get('coordinate'),
            analysis_result_id=result.get('result_id'), provenance=result['provenance'])
    except DomainError as error:
        if error.code not in {'INCOMPLETE_TIMELINE', 'OUTSIDE_DEM_COVERAGE', 'HORIZONS_CACHE_MISS'}:
            raise
        return Candidate(site_id=identity, candidate_id=f'{identity}@{index if index is not None else request.start_utc}',
            start_index=index, start_utc=request.start_utc, end_utc=request.end_utc,
            decision='INDETERMINATE', metrics={}, constraint_states={}, decisive_event=None,
            provenance={}, validation={'passed': False, 'reason_codes': [error.code]}, issue=error.code)
    except FileNotFoundError:
        return Candidate(site_id=identity, candidate_id=f'{identity}@{index if index is not None else request.start_utc}',
            start_index=index, start_utc=request.start_utc, end_utc=request.end_utc,
            decision='INDETERMINATE', metrics={}, constraint_states={}, decisive_event=None,
            provenance={}, validation={'passed': False, 'reason_codes': ['DATA_NOT_READY']}, issue='DATA_NOT_READY')
    except (KeyError, TypeError, IndexError, ValueError) as error:
        raise DomainError('ENGINE_CONTRACT_ERROR', 502) from error
