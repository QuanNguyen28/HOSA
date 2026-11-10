"""Bulk window scan, then bounded detail loading; never calls an LLM."""
from datetime import timedelta

from app.core.errors import DomainError
from .metrics import assess, violation_key
from .models import Candidate, utc
from .ranking import display_key


def scan_windows(query, scenario, repository, first: int, stop: int):
    counts = {"candidate_total": len(query.site_ids)*(stop-first), "pass": 0, "fail": 0, "indeterminate": 0}
    candidates = []
    epoch = utc(scenario["A_utc"])
    for site_id in query.site_ids:
        try:
            rows = repository.windows(site_id)
            ranges = repository.covered_ranges(site_id)
        except FileNotFoundError:
            rows, ranges = {}, []
        for index in range(first, stop):
            row = rows.get(index)
            start = epoch+timedelta(minutes=index*scenario["start_step_minutes"])
            end = start+timedelta(hours=query.duration_hours)
            covered = any(a <= start and end <= b for a, b in ranges)
            if row is None or any(v is None for v in row["metrics"].values()) or not covered:
                counts["indeterminate"] += 1
                continue
            if utc(row["start_utc"]) != start or utc(row["end_utc"]) != end:
                raise DomainError("ENGINE_CONTRACT_ERROR", 502)
            decision, checks, violations = assess(row["metrics"], query.constraints, query.min_sunlit_fraction, query.duration_hours)
            counts[{"PASS": "pass", "FAIL": "fail", "INDETERMINATE": "indeterminate"}[decision]] += 1
            if decision == "INDETERMINATE":
                continue
            candidates.append(Candidate(site_id=site_id, candidate_id=f"{site_id}@{index}", start_index=index,
                start_utc=row["start_utc"], end_utc=row["end_utc"], decision=decision, metrics=row["metrics"],
                constraint_states=checks, violations=violations, decisive_event=None, provenance={"windows": row["source"]}))
    eligible = [c for c in candidates if c.decision == "PASS"]
    if eligible:
        eligible.sort(key=lambda c: display_key(c, query.rank_by, query.current_site_id))
    else:
        eligible = [c for c in candidates if c.decision == "FAIL"]
        eligible.sort(key=lambda c: (violation_key(c, query.constraints, query.min_sunlit_fraction, query.duration_hours),
                                     *display_key(c, query.rank_by, query.current_site_id)))
    selected = []
    for candidate in eligible:
        overlap = any(old.site_id == candidate.site_id and utc(candidate.start_utc) < utc(old.end_utc)
                      and utc(old.start_utc) < utc(candidate.end_utc) for old in selected)
        if query.non_overlapping and overlap:
            continue
        selected.append(candidate)
        if len(selected) == query.max_results:
            break
    counts["returned"] = len(selected)
    counts["not_returned"] = counts["candidate_total"]-len(selected)
    return selected, counts
