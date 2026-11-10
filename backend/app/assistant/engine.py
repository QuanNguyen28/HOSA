"""Thin boundary from LLM contracts to the shared deterministic backend."""
from app.planning.models import CompareRequest, SearchRequest
from app.planning.repository import digest
from app.planning.service import PlanningService, start_index

from .evidence import build_evidence
from .normalization import baseline_issue, normalize_request


class PlanningAdapter:
    def __init__(self, planner=None):
        self.planner = planner or PlanningService()

    def capabilities(self):
        return self.planner.capabilities()

    index = staticmethod(start_index)
    baseline_issue = staticmethod(baseline_issue)
    normalize = staticmethod(normalize_request)

    def evaluate(self, spec, run_id, spec_hash):
        query = {"scenario_id": spec.scenario_id, "site_ids": spec.site_ids,
                 "arrival_utc": spec.arrival_utc, "constraints": spec.constraints,
                 "hardware": spec.hardware, "current_site_id": spec.current_site_id,
                 "min_sunlit_fraction": spec.min_sunlit_fraction, "min_earth_los_fraction": spec.min_earth_los_fraction, "rank_by": spec.rank_by,
                 "expected_source_hash": spec.source_hash}
        if spec.search_from_utc:
            result = self.planner.search(SearchRequest(**{**query, "arrival_utc": spec.search_from_utc},
                until_utc=spec.search_until_utc, max_results=3, non_overlapping=True))
        else:
            result = self.planner.compare(CompareRequest(**query))
        return build_evidence(result, spec, run_id, spec_hash)
