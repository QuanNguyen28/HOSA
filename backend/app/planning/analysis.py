"""One authoritative adapter for individual details, comparison and finder picks."""
from datetime import timedelta

from app.core.errors import DomainError
from app.services.lunarsight import planning as legacy
from .metrics import assess
from .models import Candidate, utc


def analyze_candidate(query, index: int) -> Candidate:
    start, end = utc(query.arrival_utc), utc(query.arrival_utc)+timedelta(hours=query.duration_hours)
    site_id = query.site_ids[0]
    identity = f"{site_id}@{index}"
    try:
        payload = legacy.analyze_request({"scenario_id": query.scenario_id, "site_ids": [site_id],
            "start_index": index, "constraints": query.constraints.model_dump()})
        if payload["dataset_version"] != legacy.DATASET_VERSION or payload["method_version"] != legacy.METHOD_VERSION or len(payload["sites"]) != 1:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        row = payload["sites"][0]
        if row["site_id"] != site_id or utc(row["start_utc"]) != start or utc(row["end_utc"]) != end:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        decision, states, violations = assess(row["metrics"], query.constraints, query.min_sunlit_fraction, query.duration_hours)
        if any(row["constraint_states"].get(k) != states[k] for k in ("max_darkness_hours", "max_earth_blackout_hours")):
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        contexts = {}
        for event in row["events"]:
            a, b = utc(event["start_utc"]), utc(event["end_utc"])
            if event["body"] not in ("sun", "earth") or event["state"] not in ("B", "?"):
                raise DomainError("ENGINE_CONTRACT_ERROR", 502)
            if not start <= a < b <= end or abs((b-a).total_seconds()/3600-event["duration_hours"]) > 1e-6:
                raise DomainError("ENGINE_CONTRACT_ERROR", 502)
            metric = "longest_dark_hours" if event["body"] == "sun" else "longest_blackout_hours"
            if event["state"] == "B" and event["duration_hours"] > row["metrics"][metric][1]+1e-6:
                raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        for body, metric in (("sun", "longest_dark_hours"), ("earth", "longest_blackout_hours")):
            observed = [e for e in row["events"] if e["body"] == body and e["state"] == "B"]
            worst = max(observed, key=lambda e: e["duration_hours"], default=None)
            contexts[metric] = {
                "scope": "within_mission_window",
                "touches_window_edge": bool(worst and (utc(worst["start_utc"]) == start or utc(worst["end_utc"]) == end)),
                "outside_window_duration_known": False,
            }
        return Candidate(site_id=site_id, candidate_id=identity, start_index=index,
            start_utc=row["start_utc"], end_utc=row["end_utc"], decision=decision,
            metrics=row["metrics"], constraint_states=states, decisive_event=row["decisive_event"],
            events=row["events"], metric_context=contexts, violations=violations, provenance=row["provenance"])
    except (KeyError, TypeError, IndexError) as error:
        raise DomainError("ENGINE_CONTRACT_ERROR", 502) from error
    except (FileNotFoundError, ValueError) as error:
        if isinstance(error, ValueError) and not str(error).startswith("DATA_NOT_READY"):
            raise DomainError("ENGINE_CONTRACT_ERROR", 502) from error
        return Candidate(site_id=site_id, candidate_id=identity, start_index=index,
            start_utc=start.isoformat().replace("+00:00", "Z"), end_utc=end.isoformat().replace("+00:00", "Z"),
            decision="INDETERMINATE", metrics={}, constraint_states={}, decisive_event=None,
            provenance={}, issue="DATA_NOT_READY")
