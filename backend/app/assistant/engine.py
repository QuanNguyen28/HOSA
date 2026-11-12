"""Thin boundary from LLM contracts to the shared deterministic backend."""
from app.planning.models import CompareRequest, SearchRequest
from app.planning.repository import digest
from app.planning.service import PlanningService, start_index

from .evidence import build_evidence
from .normalization import baseline_issue, normalize_request


class PlanningAdapter:
    def __init__(self, planner=None):
        self.planner = planner or PlanningService()

    def capabilities(self, resolve_indeterminate=False):
        caps = self.planner.capabilities(resolve_indeterminate=True) if resolve_indeterminate else self.planner.capabilities()
        q = CompareRequest(site_ids=[caps['scenario']['site_ids'][0]], arrival_utc=caps['scenario']['A_utc'],
                           data_source='coordinate', min_sunlit_fraction=0., resolve_indeterminate=resolve_indeterminate)
        return {**caps, 'coordinate_source_hash': self.planner.source_capabilities(q)['source_hash']}

    index = staticmethod(start_index)
    baseline_issue = staticmethod(baseline_issue)
    def normalize(self, request, patch, caps):
        spec = normalize_request(request, patch, caps)
        if spec.data_source == "coordinate":
            return spec.model_copy(update={"source_hash": self.coordinate_source_hash(spec)})
        return spec

    def coordinate_source_hash(self, spec):
        return self.planner.source_capabilities(CompareRequest(**self.query(spec)))["source_hash"]

    @staticmethod
    def query(spec):
        return {"resolve_indeterminate": spec.resolve_indeterminate, "scenario_id": spec.scenario_id, "site_ids": spec.site_ids,
                 "duration_hours": spec.duration_hours, "data_source": spec.data_source,
                 "arrival_utc": spec.arrival_utc, "constraints": spec.constraints,
                 "hardware": spec.hardware, "current_site_id": spec.current_site_id,
                 "min_sunlit_fraction": spec.min_sunlit_fraction, "min_earth_los_fraction": spec.min_earth_los_fraction, "rank_by": spec.rank_by,
                 "expected_source_hash": spec.source_hash}

    def evaluate(self, spec, run_id, spec_hash):
        query = self.query(spec)
        if spec.search_from_utc:
            result = self.planner.search(SearchRequest(**{**query, "arrival_utc": spec.search_from_utc},
                until_utc=spec.search_until_utc, max_results=3, non_overlapping=True))
        else:
            result = self.planner.compare(CompareRequest(**query))
        return build_evidence(result, spec, run_id, spec_hash)
