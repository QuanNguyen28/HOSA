"""Deterministic orchestration: validate, compare/search, rank, and persist."""
from datetime import timedelta

from app.core.errors import DomainError
from app.mission.resolution import VERSION as RESOLUTION_VERSION
from .analysis import analyze_candidate
from app.mission.snapshot import SnapshotProvider
from app.mission.evaluation import EVALUATION_VERSION, VALIDATION_VERSION
from app.services.lunarsight.shared_ephemeris import SharedEphemeris
from app.services.lunarsight.solar_disc import VERSION as SOLAR_DISC_VERSION
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
    def __init__(self, repository=None, results=None, point_pipeline=None):
        self.repository = repository or SnapshotRepository()
        self.results = results or ResultRepository()
        self.point_pipeline = point_pipeline

    def capabilities(self, resolve_indeterminate=False):
        caps = self.repository.capabilities()
        if not resolve_indeterminate:
            return caps
        scenario = caps['scenario']
        query = CompareRequest(site_ids=[scenario['site_ids'][0]], arrival_utc=scenario['A_utc'],
            min_sunlit_fraction=0., resolve_indeterminate=True, illumination_model="sun_center")
        return self.source_capabilities(query)

    def source_capabilities(self, query):
        if query.data_source == "snapshot":
            caps = self.capabilities()
            if not query.resolve_indeterminate:
                return caps
            coordinate = self.source_capabilities(query.model_copy(update={"data_source": "coordinate"}))
            return {**caps, "source_hash": digest({"snapshot": caps["source_hash"], "coordinate": coordinate["source_hash"],
                "resolution": RESOLUTION_VERSION}), "resolution_policy": RESOLUTION_VERSION}
        from app.point_analysis.sources import installed_sources
        from app.mission.targets import compare_sites
        from app.point_analysis.geometry import METHOD_VERSION as GEOMETRY_VERSION
        from app.services.lunarsight.horizons import ADAPTER_VERSION
        from app.services.lunarsight.visibility import SENSITIVITY_VERSION
        from app.services.lunarsight.contact_windows import METHOD_VERSION as CONTACT_VERSION
        sources = [{key: source[key] for key in ("dataset_id", "sha256", "resolution_m")} for source in installed_sources()]
        if not sources:
            from app.precompute.store import Store
            from app.services.lunarsight.point import terrain_sources
            records = Store().manifest()["sites"].values()
            reference = next(iter(records), None)
            if reference:
                resolutions = {r["dataset_id"]: r["resolution_m"] for r in terrain_sources()}
                sources = [{**r, "resolution_m": resolutions[r["dataset_id"]]} for r in reference["source_inventory"]]
        from app.services.lunarsight.catalog import processed_root
        from app.services.lunarsight.acquire import hashfile
        catalog = processed_root()/"site_catalog.geojson"
        sites = compare_sites()
        named_targets = {t.site_id: {"latitude_deg": sites[t.site_id]["lat"], "longitude_e_deg": sites[t.site_id]["lon"]}
                         for t in query.mission_targets() if t.site_id in sites}
        return {"scenario": {}, "warnings": ["PROVISIONAL: sampled solar-disc illumination and Earth-centre LOS; no RF, power or thermal model."],
            "dataset_version": "verified-dem-coordinate", "source_hash": digest({
            "datasets": sources, "evaluation": EVALUATION_VERSION, "validation": VALIDATION_VERSION,
            "planning": METHOD_VERSION,
            "illumination_model": query.illumination_model,
            "solar_disc_method": SOLAR_DISC_VERSION if query.illumination_model == "solar_disc" else None,
            "ephemeris": SharedEphemeris().descriptor() if query.illumination_model == "solar_disc" else None,
            "geometry": GEOMETRY_VERSION, "horizons": ADAPTER_VERSION, "sensitivity": SENSITIVITY_VERSION,
            "contact": CONTACT_VERSION, "resolution": RESOLUTION_VERSION if query.resolve_indeterminate else None, "catalog": hashfile(catalog) if any(t.site_id for t in query.mission_targets()) else None,
            **({"named_targets": named_targets} if named_targets else {})})}

    def validate(self, query):
        caps = self.source_capabilities(query)
        scenario = caps["scenario"]
        if query.expected_source_hash is not None and query.expected_source_hash != caps["source_hash"]:
            raise DomainError("STALE_DATASET", 409)
        if query.data_source == "coordinate":
            # Resolve catalog identifiers up front; no snapping of explicit coordinates.
            for target in query.mission_targets():
                target.resolved()
            return caps, None
        if query.scenario_id != scenario["scenario_id"]:
            raise DomainError("UNSUPPORTED_SCENARIO")
        if any(target.site_id not in scenario["site_ids"] for target in query.mission_targets()):
            raise DomainError("UNSUPPORTED_SITE_SCOPE")
        if query.current_site_id is not None and query.current_site_id not in scenario["site_ids"]:
            raise DomainError("UNSUPPORTED_BASELINE_SITE")
        if query.duration_hours != scenario["D_hours"]:
            raise DomainError("UNSUPPORTED_DURATION")
        if query.hardware is not None and query.hardware.model_dump() != scenario["device_heights_m"]:
            raise DomainError("UNSUPPORTED_HARDWARE")
        return caps, start_index(query.arrival_utc, scenario)

    def analyzer(self, snapshot):
        return lambda query, target, index: analyze_candidate(query, index, target=target,
            snapshot=snapshot, point_pipeline=self.point_pipeline)

    def compare(self, query: CompareRequest) -> PlanningResult:
        if query.data_source == "snapshot" and (query.duration_hours != 72 or query.illumination_model == "solar_disc"):
            query = query.model_copy(update={"data_source": "coordinate"})
        caps, index = self.validate(query)
        canonical = query.model_copy(update={"arrival_utc": utc(query.arrival_utc).isoformat().replace("+00:00", "Z")})
        analyze = self.analyzer(SnapshotProvider())
        candidates = [analyze(canonical, target, index) for target in query.mission_targets()]
        counts = {"candidate_total": len(candidates), "pass": sum(c.decision == "PASS" for c in candidates),
                  "fail": sum(c.decision == "FAIL" for c in candidates),
                  "indeterminate": sum(c.decision == "INDETERMINATE" for c in candidates)}
        return self.finish(canonical, caps, candidates, counts, "compare")

    def search(self, query: SearchRequest) -> PlanningResult:
        if query.data_source == "snapshot" and (query.duration_hours != 72 or query.illumination_model == "solar_disc"):
            query = query.model_copy(update={"data_source": "coordinate"})
        caps, first = self.validate(query)
        scenario = caps["scenario"]
        if query.data_source == "coordinate":
            elapsed = (utc(query.until_utc)-utc(query.arrival_utc)).total_seconds()/60
            if elapsed <= 0 or elapsed % query.start_step_minutes:
                raise DomainError("INVALID_SEARCH_RANGE")
            first, stop = 0, int(elapsed/query.start_step_minutes)
            if stop*len(query.mission_targets()) > 128:
                raise DomainError("SEARCH_TOO_LARGE", 422)
            last_start = (utc(query.arrival_utc) + timedelta(minutes=(stop-1)*query.start_step_minutes)).isoformat()
            try:
                for target in query.mission_targets():
                    query.mission(target, start_utc=last_start)
            except ValueError as error:
                raise DomainError("INVALID_SEARCH_RANGE", 422) from error
            scenario = {"A_utc": query.arrival_utc, "start_step_minutes": query.start_step_minutes}
        else:
            if query.start_step_minutes != scenario["start_step_minutes"]:
                raise DomainError("OFF_START_GRID")
            stop = start_index(query.until_utc, scenario, allow_stop=True)
            if stop <= first:
                raise DomainError("INVALID_SEARCH_RANGE")
        if query.resolve_indeterminate and (stop-first)*len(query.mission_targets()) > 128:
            raise DomainError("SEARCH_TOO_LARGE", 422)
        snapshot = SnapshotProvider()
        selected, counts = scan_windows(query, scenario, self.repository, first, stop,
            analyze=self.analyzer(snapshot), preflight=snapshot.preflight_failure if query.data_source == "snapshot" and not query.resolve_indeterminate else None)
        return self.finish(query, caps, selected, counts, "window_search")

    def finish(self, query, caps, candidates, counts, operation):
        if self.source_capabilities(query)["source_hash"] != caps["source_hash"]:
            raise DomainError("STALE_DATASET", 409)
        passing = [c for c in candidates if c.decision == "PASS"]
        failing = [c for c in candidates if c.decision == "FAIL"]
        recommendation = min(passing, key=lambda c: display_key(c, query.rank_by, query.current_site_id)) if passing else (
            min(failing, key=lambda c: (violation_key(c, query.constraints, query.min_sunlit_fraction, query.min_earth_los_fraction, query.duration_hours),
                                       *display_key(c, query.rank_by, query.current_site_id))) if failing else None)
        status = "FEASIBLE" if counts["pass"] else "NO_FEASIBLE_IN_EVALUATED_SET" if counts["fail"] else "INSUFFICIENT_DATA"
        request = query.model_dump(exclude={"expected_source_hash"})
        request["hardware"] = query.hardware.model_dump() if query.hardware else {"sun_panel": 1., "earth_antenna": 2.}
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
                      "A failed hard availability or contact requirement returns FAIL with quality warnings; PASS requires full or sampled mission-path validation. Continuity limits are soft preferences.",
                      "Soft preferences break primary-metric ties; rank ranges still describe the selected metric only.",
                      "Rank ranges overlap where metric bounds do; display order is an operational tie-break.",
                      "Near-miss recommendations remain FAIL and cannot be applied.",
                      "Event durations are clipped to the mission window; full darkness outside it is not measured.",
                      "Search rank ranges describe returned picks, not every scanned window."])
        self.results.save(result)
        return result
