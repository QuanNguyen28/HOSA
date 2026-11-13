"""Ordered hard requirements and explicit evidence for sampled hard failures."""
import numpy as np
import pandas as pd

from app.mission.metrics import hard_checks
from app.mission.evaluation import frame_contacts

VERSION = "hard-first-temporal-confirmation-2.0"


def check(request, metric, frame):
    checks = {}
    availability = hard_checks(metric, request.min_sunlit_fraction or 0, request.min_earth_los_fraction or 0, request.duration_hours)
    for name in ("min_sunlit_fraction", "min_earth_los_fraction"):
        if getattr(request, name) is None:
            continue
        checks[name] = availability[name]
        if checks[name] == "FAIL":
            return checks, failure(request, metric, frame, name), None
    contact = None
    if request.contact_requirements is not None:
        contact = frame_contacts(request, frame)
        for name, state in contact["requirements"]["sampled_checks"].items():
            checks["contact."+name] = state
            if state == "FAIL":
                proof = failure(request, metric, frame, "contact."+name)
                proof["contact_metrics"] = contact["metrics"]
                return checks, proof, contact
    return checks, None, contact


def failure(request, metric, frame, name):
    body = "sun" if name == "min_sunlit_fraction" else "earth"
    result = {"constraint": name, "scope": "requested_sampled_mission", "policy_version": VERSION,
        "coordinate": {"latitude_deg": request.latitude_deg, "longitude_e_deg": request.longitude_e_deg},
        "window": {"start_utc": request.start_utc, "end_utc": request.end_utc},
        "evidence_intervals": [],
        "sampling_minutes": float((frame.end_utc-frame.start_utc).dt.total_seconds().max()/60)}
    if not name.startswith("contact."):
        hours = metric["total_sun_hours" if body == "sun" else "total_earth_los_hours"]
        limit = getattr(request, name)
        result.update(limit=limit, unit="fraction", observed_bounds=[h/request.duration_hours for h in hours],
            shortfall_hours_bounds=[max(0., limit*request.duration_hours-h) for h in reversed(hours)],
            explanation="Even the upper bound is below the required fraction. Evidence intervals contribute to the whole-window shortfall; no single instant alone proves a fractional failure.")
        rejected = frame.sun_visible_fraction_upper.lt(1).to_numpy() if body == "sun" and "sun_visible_fraction_upper" in frame else frame[body+"_state"].eq("B").to_numpy()
    else:
        result.update(limit=request.contact_requirements.model_dump(), unit="contact_requirements",
            explanation="A contact hard requirement failed on the sampled timeline; blocked intervals are supporting evidence.")
        rejected = frame.earth_state.eq("B").to_numpy()
        deadline = request.contact_requirements.first_contact_deadline_minutes
        if deadline is not None:
            result["deadline_utc"] = (pd.Timestamp(request.start_utc)+pd.Timedelta(minutes=deadline)).isoformat()
    edges = np.flatnonzero(np.diff(np.r_[False, rejected, False]))
    duration = (frame.end_utc-frame.start_utc).dt.total_seconds().to_numpy()
    loss = (1-frame.sun_visible_fraction_upper.to_numpy()) if body == "sun" and "sun_visible_fraction_upper" in frame else rejected.astype(float)
    cumulative = np.r_[0., np.cumsum(loss*duration)]
    spans = sorted(zip(edges[::2], edges[1::2]), key=lambda pair: (-(cumulative[pair[1]]-cumulative[pair[0]]), pair[0]))
    starts, ends = frame.start_utc, frame.end_utc
    for a, b in spans[:3]:
        worst = a+int(np.argmax(loss[a:b]))
        result["evidence_intervals"].append({"target": body,
            "start_utc": starts.iloc[a].isoformat(), "end_utc": ends.iloc[b-1].isoformat(),
            "at_utc": starts.iloc[worst].isoformat()})
    return result
