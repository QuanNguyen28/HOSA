"""Search candidates using the same analyzer as comparison and individual requests."""
from datetime import timedelta

from .metrics import violation_key
from .models import utc
from .ranking import display_key


def scan_windows(query, scenario, repository, first, stop, *, analyze, preflight=None):
    targets = query.mission_targets()
    counts = {'candidate_total': len(targets)*(stop-first), 'pass': 0, 'fail': 0, 'indeterminate': 0}
    candidates = []
    step = scenario['start_step_minutes']
    epoch = utc(scenario['A_utc'])
    latest_end = epoch + timedelta(minutes=(stop-1)*step, hours=query.duration_hours)
    unavailable = {i for i, target in enumerate(targets) if preflight and
                   preflight(target, query.mission(target), latest_end)}
    for index in range(first, stop):
        start = (epoch+timedelta(minutes=index*step)).isoformat().replace('+00:00', 'Z')
        current = query.model_copy(update={'arrival_utc': start})
        for position, target in enumerate(targets):
            if position in unavailable:
                counts['indeterminate'] += 1
                continue
            candidate = analyze(current, target, index)
            counts[{'PASS': 'pass', 'FAIL': 'fail', 'INDETERMINATE': 'indeterminate'}[candidate.decision]] += 1
            candidates.append(candidate)
    eligible = [c for c in candidates if c.decision == 'PASS']
    if eligible:
        eligible.sort(key=lambda c: display_key(c, query.rank_by, query.current_site_id))
    else:
        eligible = [c for c in candidates if c.decision == 'FAIL']
        eligible.sort(key=lambda c: (violation_key(c, query.constraints, query.min_sunlit_fraction,
            query.min_earth_los_fraction, query.duration_hours), *display_key(c, query.rank_by, query.current_site_id)))
    selected = []
    for candidate in eligible:
        overlap = any(old.site_id == candidate.site_id and utc(candidate.start_utc) < utc(old.end_utc)
                      and utc(old.start_utc) < utc(candidate.end_utc) for old in selected)
        if query.non_overlapping and overlap:
            continue
        selected.append(candidate)
        if len(selected) == query.max_results:
            break
    counts['returned'] = len(selected)
    counts['not_returned'] = counts['candidate_total']-len(selected)
    return selected, counts
