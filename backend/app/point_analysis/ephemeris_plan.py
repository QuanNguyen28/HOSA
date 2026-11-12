"""Reuse exact validated query spans, then batch only uncovered native samples."""
import json
from pathlib import Path

import pandas as pd

from app.services.lunarsight.acquire import JPL
from app.services.lunarsight.horizons import ADAPTER_VERSION, request_params
from app.services.lunarsight.terrain import R

INTERVALS_PER_BATCH = 40000  # Page size, not a mission-duration limit.


def segments(root, site, target, height, start, end, step):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    params = request_params(target, site['lon_e_deg'], site['lat_deg'], site['dem_z_m'], height,
                            R, R, start, end, step)
    signature = {k: v for k, v in params.items() if k not in ('START_TIME', 'STOP_TIME')}
    spans = set()
    body = 'sun' if target == 10 else 'earth'
    for path in (Path(root)/'raw/horizons').glob(f"{site['site_id']}_{body}_{step}min_*.receipt.json"):
        try:
            record = json.loads(path.read_text())
            identity = record['identity']
            other = identity['params']
            if (identity.get('method_version') != ADAPTER_VERSION or identity.get('endpoint') != JPL
                    or identity.get('site_id') != site['site_id']
                    or identity.get('dataset_sha256') != site['dem_sha256']
                    or identity.get('observer_height_m') != height
                    or {k: v for k, v in other.items() if k not in ('START_TIME', 'STOP_TIME')} != signature):
                continue
            a = pd.Timestamp(other['START_TIME'].strip("'"), tz='UTC')
            b = pd.Timestamp(other['STOP_TIME'].strip("'"), tz='UTC')
            raw = path.with_name(path.name.removesuffix('.receipt.json')+'.json')
            if a < b and b > start and a < end and raw.is_file():
                spans.add((a, b))
        except (OSError, ValueError, KeyError, TypeError):
            continue  # Unusable hints are never used as scientific evidence.
    spans = sorted(spans)
    plan, cursor = [], start
    while cursor < end:
        covering = [(a, b) for a, b in spans if a <= cursor < b]
        if covering:
            a, b = max(covering, key=lambda pair: pair[1])
            stop = min(b, end)
            plan.append((cursor, stop, a, b))
        else:
            future = [a for a, _ in spans if a > cursor]
            stop = min(cursor + pd.Timedelta(minutes=step*INTERVALS_PER_BATCH), end,
                       min(future) if future else end)
            plan.append((cursor, stop, cursor, stop))
        cursor = stop
    return plan
