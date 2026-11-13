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
        from app.mission.targets import compare_sites
        return {**caps, 'coordinate_source_hash': digest({
            'coordinate': self.planner.source_capabilities(q)['source_hash'],
            'named_catalog': compare_sites()})}

    index = staticmethod(start_index)
    baseline_issue = staticmethod(baseline_issue)
    normalize = staticmethod(normalize_request)

    def evaluate(self, spec, run_id, spec_hash):
        query = {"illumination_model": spec.illumination_model, "resolve_indeterminate": spec.resolve_indeterminate, "scenario_id": spec.scenario_id, "site_ids": spec.site_ids,
                 "duration_hours": spec.duration_hours, "data_source": spec.data_source,
                 "arrival_utc": spec.arrival_utc, "constraints": spec.constraints,
                 "hardware": spec.hardware, "current_site_id": spec.current_site_id,
                 "min_sunlit_fraction": spec.min_sunlit_fraction, "min_earth_los_fraction": spec.min_earth_los_fraction, "rank_by": spec.rank_by,
                 "contact_requirements": spec.contact_requirements,
                 "expected_source_hash": spec.source_hash if spec.data_source == "snapshot" else None}
        if spec.search_from_utc:
            step = {"start_step_minutes": spec.search_step_minutes} if spec.search_step_minutes else {}
            result = self.planner.search(SearchRequest(**{**query, "arrival_utc": spec.search_from_utc},
                until_utc=spec.search_until_utc, max_results=3, non_overlapping=True, **step))
        else:
            result = self.planner.compare(CompareRequest(**query, end_utc=spec.end_utc))
        return build_evidence(result, spec, run_id, spec_hash)
