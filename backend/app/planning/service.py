"""Deterministic orchestration: validate, compare/search, rank, and persist."""
from datetime import timedelta

from app.core.errors import DomainError
from .analysis import analyze_candidate
from .finder import scan_windows
from .metrics import violation_key
from .models import CompareRequest, PlanningResult, SearchRequest, utc
from .ranking import display_key, rank_candidates
from .repository import METHOD_VERSION, ResultRepository, SnapshotRepository, digest


def start_index(at: str, scenario: dict, allow_stop=False) -> int:
    instant = utc(at)
    begin, stop = utc(scenario["A_utc"]), utc(scenario["B_utc"])
    if instant < begin or instant > stop or (instant == stop and not allow_stop):
        raise DomainError("OUTSIDE_TIME_COVERAGE")
    offset = (instant-begin).total_seconds()
    step = scenario["start_step_minutes"]*60
    if offset % step:
        raise DomainError("OFF_START_GRID")
    return int(offset//step)


class PlanningService:
    def __init__(self, repository=None, results=None):
        self.repository = repository or SnapshotRepository()
        self.results = results or ResultRepository()

    def capabilities(self):
        return self.repository.capabilities()

    def validate(self, query):
        caps = self.capabilities()
        scenario = caps["scenario"]
        if query.scenario_id != scenario["scenario_id"]:
            raise DomainError("UNSUPPORTED_SCENARIO")
        if any(site not in scenario["site_ids"] for site in query.site_ids):
            raise DomainError("UNSUPPORTED_SITE_SCOPE")
        if query.current_site_id is not None and query.current_site_id not in scenario["site_ids"]:
            raise DomainError("UNSUPPORTED_BASELINE_SITE")
        if query.duration_hours != scenario["D_hours"]:
            raise DomainError("UNSUPPORTED_DURATION")
        if query.hardware is not None and query.hardware.model_dump() != scenario["device_heights_m"]:
            raise DomainError("UNSUPPORTED_HARDWARE")
        if query.expected_source_hash is not None and query.expected_source_hash != caps["source_hash"]:
            raise DomainError("STALE_DATASET", 409)
        return caps, start_index(query.arrival_utc, scenario)

    def compare(self, query: CompareRequest) -> PlanningResult:
        caps, index = self.validate(query)
        canonical = query.model_copy(update={"arrival_utc": utc(query.arrival_utc).isoformat().replace("+00:00", "Z")})
        candidates = [analyze_candidate(canonical.model_copy(update={"site_ids": [site]}), index) for site in query.site_ids]
        counts = {"candidate_total": len(candidates), "pass": sum(c.decision == "PASS" for c in candidates),
                  "fail": sum(c.decision == "FAIL" for c in candidates),
                  "indeterminate": sum(c.decision == "INDETERMINATE" for c in candidates)}
        return self.finish(canonical, caps, candidates, counts, "compare")

    def search(self, query: SearchRequest) -> PlanningResult:
        caps, first = self.validate(query)
        stop = start_index(query.until_utc, caps["scenario"], allow_stop=True)
        if stop <= first:
            raise DomainError("INVALID_SEARCH_RANGE")
        selected, counts = scan_windows(query, caps["scenario"], self.repository, first, stop)
        candidates = []
        for pick in selected:
            detail_query = CompareRequest(**query.model_dump(exclude={"until_utc", "max_results", "non_overlapping"}))
            detail_query = detail_query.model_copy(update={"site_ids": [pick.site_id], "arrival_utc": pick.start_utc})
            detail = analyze_candidate(detail_query, pick.start_index)
            if detail.decision != pick.decision or detail.metrics != pick.metrics:
                raise DomainError("SEARCH_DETAIL_MISMATCH", 502)
            candidates.append(detail)
        return self.finish(query, caps, candidates, counts, "window_search")

    def finish(self, query, caps, candidates, counts, operation):
        if self.capabilities()["source_hash"] != caps["source_hash"]:
            raise DomainError("STALE_DATASET", 409)
        passing = [c for c in candidates if c.decision == "PASS"]
        failing = [c for c in candidates if c.decision == "FAIL"]
        recommendation = min(passing, key=lambda c: display_key(c, query.rank_by, query.current_site_id)) if passing else (
            min(failing, key=lambda c: (violation_key(c, query.constraints, query.min_sunlit_fraction, query.duration_hours),
                                       *display_key(c, query.rank_by, query.current_site_id))) if failing else None)
        status = "FEASIBLE" if counts["pass"] else "NO_FEASIBLE_IN_EVALUATED_SET" if counts["fail"] else "INSUFFICIENT_DATA"
        request = query.model_dump(exclude={"expected_source_hash"})
        request["hardware"] = query.hardware.model_dump() if query.hardware else caps["scenario"]["device_heights_m"]
        request["arrival_utc"] = utc(query.arrival_utc).isoformat().replace("+00:00", "Z")
        if operation == "window_search":
            request["until_utc"] = utc(query.until_utc).isoformat().replace("+00:00", "Z")
        result = PlanningResult(
            result_id=digest({"request": request, "source": caps["source_hash"], "operation": operation})[:20],
            operation=operation, status=status, candidates=candidates,
            recommended_candidate_id=recommendation.candidate_id if recommendation else None,
            apply_allowed=bool(passing), rank_by=query.rank_by, ranking=rank_candidates(candidates, query.rank_by),
            coverage=counts, request=request, dataset_version=caps["dataset_version"],
            method_version=METHOD_VERSION, source_hash=caps["source_hash"],
            warnings=[*caps["warnings"], "Only selected sites and evaluated starts are covered.",
                      "Rank ranges overlap where metric bounds do; display order is an operational tie-break.",
                      "Near-miss recommendations remain FAIL and cannot be applied.",
                      "Event durations are clipped to the mission window; full darkness outside it is not measured.",
                      "Search rank ranges describe returned picks, not every scanned window."])
        self.results.save(result)
        return result
