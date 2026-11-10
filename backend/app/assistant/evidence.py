"""Compact, addressable facts derived from authoritative planning results."""
from app.planning.repository import digest
from .models import EvidenceBundle


def build_evidence(result, spec, run_id, spec_hash):
    facts, candidates, identities = {}, [], {}
    for item in result.candidates:
        key = item.candidate_id if spec.search_from_utc else item.site_id
        identities[item.candidate_id] = key
        candidate = item.model_copy(update={"candidate_id": key})
        candidates.append(candidate)
        if candidate.issue:
            facts[f"{key}.availability"] = {"site_id": candidate.site_id, "candidate_id": key, "status": candidate.issue}
            continue
        for suffix, metric, body in (("dark", "longest_dark_hours", "sun"),
                                     ("blackout", "longest_blackout_hours", "earth"),
                                     ("earth", "total_earth_los_hours", None),
                                     ("sun", "total_sun_hours", None),
                                     ("joint", "longest_joint_hours", None)):
            events = [e for e in candidate.events if e["body"] == body and e["state"] == "B"]
            worst = max(events, key=lambda e: e["duration_hours"], default=None)
            if worst:
                worst = {**worst, "event_id": digest({"candidate": key, "source": spec.source_hash, "event": worst})[:20]}
            limit = spec.constraints.max_darkness_hours if suffix == "dark" else spec.constraints.max_earth_blackout_hours if suffix == "blackout" else (
                spec.min_sunlit_fraction*72 if suffix == "sun" else spec.min_earth_los_fraction*72 if suffix == "earth" else None)
            facts[f"{key}.{suffix}"] = {"site_id": candidate.site_id, "candidate_id": key, "metric": metric,
                "bounds": candidate.metrics[metric], "limit_hours": limit, "unit": "hours",
                "requirement_type": "hard" if suffix in ("sun", "earth") else "soft",
                "worst_interval": worst, "context": candidate.metric_context.get(metric), "source": candidate.provenance}
    chosen = next((c for c in result.candidates if c.candidate_id == result.recommended_candidate_id), None)
    rankings = [r.model_copy(update={"candidate_id": identities[r.candidate_id],
                "tied_with": [identities[k] for k in r.tied_with]}) for r in result.ranking]
    return EvidenceBundle(run_id=run_id, spec_hash=spec_hash, source_hash=result.source_hash, request=spec,
        status=result.status, recommended_site_id=chosen.site_id if chosen else None,
        recommended_candidate_id=identities.get(result.recommended_candidate_id), candidates=candidates,
        ranking=rankings, apply_allowed=result.apply_allowed, coverage=result.coverage, facts=facts,
        warnings=result.warnings)
