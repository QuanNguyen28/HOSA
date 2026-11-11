import math
from bisect import bisect_left, bisect_right
import numpy as np
import pandas as pd
from .durations import bounds, combine, longest

SENSITIVITY_VERSION = "ordered-events-1.0"

def classify(e,h,complete):
    """Incomplete terrain can prove a blockage at a sampled direction."""
    el,hor,cov=np.broadcast_arrays(e,h,complete)
    valid=np.isfinite(el)&np.isfinite(hor)
    return np.where(valid&(el<=hor),"B",np.where(valid&cov&(el>hor),"V","?"))

def lookup(p,az):
    if not len(p): raise ValueError("Missing horizon")
    step=float(p.az_step_deg.iloc[0]); n=len(p)
    if not np.allclose(p.az_deg.to_numpy(),np.arange(n)*step) or not np.isclose(n*step,360):
        raise ValueError("Incomplete or unordered azimuth grid")
    az=np.asarray(az,dtype=float)
    finite=np.isfinite(az); x=np.where(finite,az%360,0)/step
    i=np.floor(x).astype(int)%n; j=(i+1)%n; f=x-np.floor(x)
    h=p.horizon_deg.to_numpy()
    cov=p.coverage_complete.to_numpy(dtype=bool)
    exact=np.isclose(f,0,atol=1e-10,rtol=0)
    c=finite&cov[i]&(exact|cov[j])
    # For a gap between bearings no interpolated lower bound is assumed.
    result=np.where(finite&exact,h[i],np.where(c,h[i]*(1-f)+h[j]*f,np.nan))
    return result,c

def visibility(sun,earth,ps,pe):
    if not sun.index.equals(earth.index) or len(sun)<2: raise ValueError("Sun/Earth grids differ or empty")
    index=sun.index
    if index.tz is None or index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError("Expected ordered unique aware UTC")
    df=pd.DataFrame(index=index)
    for label,ep,p in [("sun",sun,ps),("earth",earth,pe)]:
        df[f"{label}_az_deg"]=ep.az_deg; df[f"{label}_el_deg"]=ep.el_deg
        h,cov=lookup(p,ep.az_deg)
        df[f"{label}_horizon_deg"]=h; df[f"{label}_terrain_complete"]=cov
        df[f"{label}_clearance_deg"]=ep.el_deg-h
        df[f"{label}_state"]=classify(ep.el_deg,h,cov)
        df[f"{label}_ephem_valid"]=ep.row_present & ep[["az_deg","el_deg"]].notna().all(axis=1)
        df[f"{label}_coverage_flag"]=np.select(
            [~df[f"{label}_ephem_valid"],~cov],["missing_ephemeris","incomplete_terrain"],default="covered")
    df["joint_state"]=combine(df.sun_state,df.earth_state)
    # Final timestamp is a boundary only, not an extra interval.
    df["start_utc"]=index; df["end_utc"]=index.to_series().shift(-1)
    return df.iloc[:-1].copy()

def max_rule(v,m):
    if isinstance(m,bool) or not isinstance(m,(int,float)) or not math.isfinite(m) or not 0<=m<=72:
        raise ValueError("Maximum threshold must be finite and between 0 and 72")
    lo,hi=v
    if not np.isfinite([lo,hi]).all() or lo>hi or lo<0 or hi>72+1e-9: raise ValueError("Invalid bounds")
    return "PASS" if hi<=m+1e-9 else ("FAIL" if lo>m+1e-9 else "INDETERMINATE")

def valid_start(a,b,k):
    if isinstance(k,bool) or not isinstance(k,(int,np.integer)) or not 0<=k<1344:
        raise ValueError("UNSUPPORTED_CONFIG: start index outside [0,1344)")
    t=a+pd.Timedelta(minutes=15*int(k))
    if t>=b: raise ValueError("UNSUPPORTED_CONFIG")
    return t

def analyze(v,start,dark,blackout):
    if start.tzinfo is None: raise ValueError("Expected aware UTC")
    end=start+pd.Timedelta(hours=72)
    s=v[(v.start_utc<end)&(v.end_utc>start)]
    if s.empty or s.start_utc.iloc[0]>start or s.end_utc.iloc[-1]<end or not np.array_equal(s.start_utc.iloc[1:].to_numpy(),s.end_utc.iloc[:-1].to_numpy()):
        raise ValueError("DATA_NOT_READY: gaps or missing boundary")
    dt=(s.end_utc.clip(upper=end)-s.start_utc.clip(lower=start)).dt.total_seconds().to_numpy()/3600
    b=bounds(s.sun_state,s.earth_state,dt)
    checks=[max_rule(b["longest_dark_hours"],dark),max_rule(b["longest_blackout_hours"],blackout)]
    return b,checks,"FAIL" if "FAIL" in checks else ("PASS" if checks==["PASS","PASS"] else "INDETERMINATE")

def grid_windows(v,a,b,dark,blackout):
    rows=[]
    for k in range(1344):
        start=valid_start(a,b,k); vals,checks,decision=analyze(v,start,dark,blackout)
        rows.append(dict(start_index=k,start_utc=start,end_utc=start+pd.Timedelta(hours=72),
                         darkness_constraint=checks[0],earth_constraint=checks[1],decision=decision,
                         **{f"{key}_{bound}":pair[i] for key,pair in vals.items() for i,bound in enumerate(("L","U"))}))
    return pd.DataFrame(rows)

def match_events(first, second, max_shift_minutes=15):
    """Maximum-cardinality, minimum-total-shift monotone one-to-one matching.

    Each event may be used once, and before/after states must agree. A Fenwick
    tree keeps the best increasing chain of candidates inside the time band;
    updating only after each first-series event prevents reusing either side.
    """
    def events(series):
        changed = (series != series.shift()) & series.shift().notna()
        return [(stamp, series.iloc[series.index.get_loc(stamp)-1], series.loc[stamp])
                for stamp in series.index[changed]]
    left, right = events(first), events(second)
    times = [stamp.value for stamp, _, _ in right]
    band = int(max_shift_minutes * 60 * 1_000_000_000)
    # count, summed shift, predecessor, left index, right index, shift
    nodes = [(0, 0., -1, -1, -1, 0.)]
    tree = [0] * (len(right)+1)
    def better(a, b):
        return a if (nodes[a][0], -nodes[a][1], -a) >= (nodes[b][0], -nodes[b][1], -b) else b
    def query(stop):
        best = 0
        while stop:
            best = better(best, tree[stop])
            stop -= stop & -stop
        return best
    for i, (stamp, before, after) in enumerate(left):
        pending = []
        for j in range(bisect_left(times, stamp.value-band), bisect_right(times, stamp.value+band)):
            if right[j][1:] != (before, after):
                continue
            previous = query(j)
            shift = abs(times[j]-stamp.value) / 60_000_000_000
            nodes.append((nodes[previous][0]+1, nodes[previous][1]+shift, previous, i, j, shift))
            pending.append((j+1, len(nodes)-1))
        for position, node in pending:
            while position < len(tree):
                tree[position] = better(tree[position], node)
                position += position & -position
    node = query(len(right))
    pairs = []
    while node:
        _, _, previous, i, j, shift = nodes[node]
        pairs.append((i, j, shift))
        node = previous
    return left, right, list(reversed(pairs))


def sensitivity(a,b,columns):
    """Compare states on finest native grid via left hold, and report time differences."""
    if a.start_utc.iloc[0]!=b.start_utc.iloc[0] or a.end_utc.iloc[-1]!=b.end_utc.iloc[-1]:
        raise ValueError("Sensitivity requires matching time domains")
    output={}
    a=a.set_index("start_utc"); b=b.set_index("start_utc")
    step=(b.end_utc-b.index).dt.total_seconds()/60
    for key in columns:
        aa=a[key].reindex(b.index,method="ffill"); bb=b[key]
        ea,eb,matches=match_events(a[key],bb)
        pairs=[match[2] for match in matches]
        output[key]=dict(minutes_state_diff=float(step[aa!=bb].sum()),
            delta_visible_minutes=float(step[bb=="V"].sum()-step[aa=="V"].sum()),
            delta_blocked_minutes=float(step[bb=="B"].sum()-step[aa=="B"].sum()),
            events_first=len(ea),events_second=len(eb),matched_first_within_15min=len(pairs),
            matched_second_within_15min=len(pairs),
            unmatched_first=len(ea)-len(pairs),unmatched_second=len(eb)-len(pairs),
            max_matched_event_shift_minutes=max(pairs) if pairs else None)
    return output
