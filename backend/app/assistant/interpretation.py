"""Meaning and addressable evidence for explanations; never evaluate a mission here."""
from __future__ import annotations
import re
import unicodedata

INTERPRETATION_VERSION = "mission-interpretation-2.1-contextual"


def explanation_view(evidence: dict, text: str) -> dict:
    """Use qualitative evidence by default; retain numeric detail for explicit data questions."""
    plain="".join(char for char in unicodedata.normalize("NFD",text.casefold()) if unicodedata.category(char)!="Mn").replace("đ","d")
    numeric=bool(re.search(r"\b(bao nhieu|so lieu|thong so|bang so lieu|bang chi so|cu the tung|chi tiet tung|khi nao|may gio|how many|how much|numbers|numeric|metrics|bounds|table|when does|when can|when is|what time)\b",plain))
    if re.search(r"\b(thay vi|khong can|khong liet ke|han che|it|bot|tranh|dung liet ke).{0,45}(so lieu|thong so)|(?:without|rather than|few|fewer|less).{0,35}(numbers|metrics|data)",plain):
        numeric=False
    if numeric:
        return evidence
    facts={}
    source=evidence.get("facts",{})
    for identifier,fact in source.items():
        core={key:fact[key] for key in ("result_id","candidate_id","kind","state") if key in fact}
        if fact.get("kind")=="decision":
            core.update({key:fact.get(key) for key in ("site_id","nominal_decision","validation_passed",
                         "mission_path_passed","validation_scope")})
            core["validation_meanings"]=[item["meaning"] for item in fact.get("validation_meanings",[])]
            if fact.get("issue"):
                core["data_issue"]=VALIDATION_MEANINGS.get(fact["issue"],"Required backend evidence is unavailable.")
        elif fact.get("kind","").startswith("metric."):
            core.update(definition=fact.get("definition"),context=fact.get("context"))
        elif fact.get("kind","").startswith(("hard.","soft.")):
            core.update(requirement_type=fact.get("requirement_type"),changes_hard_decision=fact.get("changes_hard_decision"))
            core.update(_requirement_margin(fact,source))
        elif fact.get("kind")=="contact":
            requirements=fact.get("requirements") or {}
            core.update(scope=fact.get("scope"),checks=requirements.get("sampled_checks"),
                        final_contact_decision=requirements.get("decision"))
        elif fact.get("kind","").startswith("event."):
            event=fact.get("event") or {}
            core["event"]={key:event[key] for key in ("body","target","state") if key in event}
        facts[identifier]=core
    return {**{key:value for key,value in evidence.items() if key not in {"facts","request","provenance"}},
            "facts":facts,"detail_mode":"qualitative",
            "note":("Detailed values are in the engine card. For a hard requirement, achieved_percent vs required_percent "
                    "may be quoted to show how far it is from passing; otherwise explain states and validation causes "
                    "without inventing missing quantities.")}


HARD_METRICS={"min_sunlit_fraction":"total_sun_hours","min_earth_los_fraction":"total_earth_los_hours"}


def _requirement_margin(fact:dict,facts:dict)->dict:
    """Achieved vs required percentage for a hard fraction, copied from engine bounds."""
    name=fact.get("kind","")[5:]
    duration=fact.get("duration_hours")
    required=fact.get("requested_value")
    if name not in HARD_METRICS or not duration or required is None:
        return {}
    metric=facts.get(f"{fact.get('result_id')}/{fact.get('candidate_id')}/metric.{HARD_METRICS[name]}") or {}
    bounds=metric.get("bounds_hours")
    if not bounds or len(bounds)!=2:
        return {}
    low,high=(round(value/duration*100) for value in bounds)
    return {"required_percent":round(required*100),
            "achieved_percent":low if low==high else [low,high]}

VALIDATION_MEANINGS = {
    "SENSITIVITY_FAILED":"A required comparison of resolutions, terrain radius or sampling did not meet the backend stability checks; do not claim which subcheck failed without its diagnostics.",
    "COMPARISON_EVIDENCE_MISSING":"A required independent comparison is missing, so validation cannot be completed.",
    "INCOMPLETE_TERRAIN":"Terrain coverage needed for the analysis is incomplete.",
    "INCOMPLETE_EPHEMERIS":"Sun/Earth position evidence needed for the requested observer and time is incomplete.",
    "HORIZONS_CACHE_MISS":"No cached Horizons evidence exists for this exact observer/time request; another site's cache is not a substitute.",
    "OUTSIDE_DEM_COVERAGE":"The requested target is outside available terrain coverage.",
    "DEM_SEAM_FAILED":"Terrain tile seam verification did not pass.",
    "ENU_REFERENCE_FAILED":"The required local reference-frame verification did not pass.",
    "DATA_NOT_READY":"Required scientific input or processed evidence is not ready.",
}

METRIC_MEANINGS = {
    "total_sun_hours": {
        "meaning": "Equivalent full-disc sunlight hours: integral of visible solar-disc area fraction over mission time, including solid-Earth occultation. Divide by mission duration for mean illumination. Explicit legacy sun_center results retain their original centre-visibility meaning.",
        "use": "Checks the requested minimum illumination fraction; relates to opportunities for solar exposure.",
        "limit": "Not generated energy, thermal safety or continuous sunlight. Those require other models."},
    "total_earth_los_hours": {
        "meaning": "Total geometric visibility of Earth's centre during the mission, possibly split into intervals.",
        "use": "Checks the requested minimum Earth LOS fraction.",
        "limit": "Not one continuous contact window, radio link success, throughput or ground-station availability."},
    "longest_dark_hours": {
        "meaning": "Longest continuous interval with no part of the solar disc visible within the mission window (centre blockage for explicit legacy sun_center results).",
        "use": "Describes continuity of illumination; a supplied maximum is a soft preference.",
        "limit": "Does not determine battery endurance; a boundary-clipped event can continue outside the mission."},
    "longest_blackout_hours": {
        "meaning": "Longest continuous Earth-centre blockage within the mission window.",
        "use": "Describes geometric communication interruptions; a supplied maximum is a soft preference.",
        "limit": "Exceeding this soft preference alone never causes a hard FAIL."},
    "longest_joint_hours": {
        "meaning": "Longest continuous interval with some solar-disc area visible and Earth's centre geometrically visible (Sun centre for explicit legacy results).",
        "use": "Helps identify overlapping opportunities; use the engine's ranking when selected.",
        "limit": "Not a universal site quality score or proof of actual power and communications."},
    "contact": {
        "meaning": "Continuous usable Earth LOS windows after setup, evaluated by the existing contact engine.",
        "use": "Minimum duration, distinct required windows and first-contact deadline are hard requirements when supplied.",
        "limit": "A large total LOS does not guarantee a long enough usable window. Distinct windows are not sessions packed into one window."},
    "geometry": {
        "meaning": "Clearance compares target elevation with terrain horizon at the same azimuth.",
        "use": "A stored blocked event and its angles can explain local horizon obstruction.",
        "limit": "Name a crater/ridge or identify the physical cause only if the backend/source actually establishes it."},
    "decision": {
        "meaning": "PASS meets the evaluated hard requirements with the required validation; FAIL violates a hard requirement; INDETERMINATE lacks a defensible final conclusion.",
        "use": "Copy final decisions and nominal decisions separately from the engine. Validation may gate a nominal result.",
        "limit": "No hard requirements means no feasibility decision. Never turn unknown into failure or success, or imply landing certification."},
    "bounds": {
        "meaning": "Lower/upper bounds reflect known and unknown visibility samples under the engine method.",
        "use": "Explain threshold overlap and incomplete coverage using the engine's constraint states.",
        "limit": "Not a statistical confidence interval or a probability of mission success."},
}

ANSWER_POLICY = (
    "Understand the user's underlying decision or confusion, rather than matching a command word. "
    "Choose the explanation structure from that intent; do not fill a fixed introduction/metrics/limits/next-steps template. "
    "Synthesize relevant sources into a causal explanation: what matters to this question, why it matters, and what follows. "
    "Distinguish observed facts, supported interpretation and missing evidence; frame hypothetical examples explicitly as hypothetical. "
    "Use measured, literal language: do not dramatize environmental danger or assert timing, temperature, perfect precision, "
    "universal visibility geometry or an optimum that the supplied evidence does not establish. "
    "Describe geometric opportunities as such; do not turn them into guaranteed power supply or radio performance. "
    "A PASS on a fraction threshold only establishes that threshold; it does not by itself establish full or continuous visibility. "
    "Do not claim an effect size, best site/date, battery endurance or successful radio link without the corresponding engine/model evidence. "
    "Answer the user's actual question in the first sentence, then explain only the relevant reason and mission implication. "
    "Use plain prose without Markdown headings or field dumps, with connected paragraphs and enough explanation to resolve the question. "
    "Do not enumerate every metric or repeat a project overview for a focused follow-up. Lists/tables are useful when the user asks for a comparison or a list. "
    "For a follow-up asking why validation or a conclusion is unresolved, explain that cause only; do not recap the preceding numeric comparison. "
    "Use plain language; never expose typed query, schema, arrival_utc, JSON field names, internal stages or API jargon in the answer. "
    "For missing required inputs ask only the smallest necessary clarification, usually one short question. "
    "Conceptual questions about what the project helps decide, what a metric means, why conditions change, or hypothetical schedule changes are knowledge questions. "
    "Answer those directly without requesting a date, coordinates or thresholds, and without offering an unsolicited calculation. "
    "Only ask mission inputs when the user actually requests a concrete computation, comparison or search. "
    "Optional soft limits and ranking preferences must not block a request or trigger extra questions. "
    "For a missing start instant, ask for date, time and timezone together in one short question. "
    "Do not repeat thresholds and definitions during clarification. Retain explicit values from conversation. "
    "Connect a result to the user's stated goal; distinguish total availability from continuity and contact usability. "
    "Include only numbers that explain the conclusion and copy them from evidence, with units and the actual mission duration. "
    "Prefer qualitative reasoning with only the few quantities needed to support it; detailed metrics stay in the engine card unless requested. "
    "When the final decision is INDETERMINATE, lead with the unresolved conclusion and its validation/coverage cause before any nominal PASS or FAIL. "
    "Mention scientific limits only when relevant to the question or conclusion. "
    "Suggest a next comparison only within supplied scope/capabilities; ask before changing sites, times or thresholds. "
    "The challenge values rapid, intuitive comparison of lunar sites and dates and accessible explanations of Sun/Earth geometry. "
    "Metric definitions are interpretation guidance, not measurements or evidence that any site passed."
)


def engine_evidence(summary: dict) -> dict:
    """Copy observations/states into small facts tied to one exact result/candidate."""
    result_id = summary.get("result_id")
    if not result_id:
        return {}
    facts = {}
    request = summary.get("request") or {}

    def put(candidate_id, kind, state=None, **data):
        identifier = f"{result_id}/{candidate_id}/{kind}"
        facts[identifier] = {"result_id": result_id, "candidate_id": candidate_id,
                             "kind": kind, "state": state, **data}

    candidates = summary.get("candidates")
    if candidates is None:
        candidates = [{"candidate_id": result_id, "site_id": request.get("site_id"),
            "decision": summary.get("decision"), "nominal_sampled_decision": summary.get("nominal_sampled_decision"),
            "metrics": summary.get("metrics_hours", {}), "constraint_states": summary.get("constraint_checks", {}),
            "soft_constraint_states": summary.get("soft_constraint_checks", {}),
            "validation": summary.get("validation", {}), "contact_analysis": summary.get("contact_analysis"),
            "start_utc": request.get("start_utc"), "end_utc": summary.get("end_utc"),
            "coordinate": summary.get("coordinate"), "events": summary.get("explanation_events", [])}]
    for candidate in candidates:
        cid = candidate.get("candidate_id") or candidate.get("site_id")
        validation = candidate.get("validation") or {}
        put(cid, "decision", candidate.get("decision"), site_id=candidate.get("site_id"),
            start_utc=candidate.get("start_utc"), end_utc=candidate.get("end_utc"),
            nominal_decision=candidate.get("nominal_sampled_decision"), issue=candidate.get("issue"),
            coordinate=candidate.get("coordinate"), validation_passed=validation.get("passed"),
            mission_path_passed=(validation.get("mission_path") or {}).get("passed", False),
            validation_scope=(validation.get("mission_path") or {}).get("scope"),
            mission_bounds=(validation.get("mission_path") or {}).get("metrics_hours"),
            validation_reasons=validation.get("reason_codes", []),
            validation_meanings=[{"code":code,"meaning":VALIDATION_MEANINGS.get(code.split(":")[-1],
                "A required backend check did not pass; the specific cause is not established by this summary.")}
                for code in validation.get("reason_codes", [])])
        for name, bounds in (candidate.get("metrics") or {}).items():
            put(cid, "metric."+name, bounds_hours=bounds, definition=name,
                context=(candidate.get("metric_context") or {}).get(name))
        for name, state in (candidate.get("constraint_states") or {}).items():
            limit = request.get(name)
            duration = request.get("duration_hours")
            put(cid, "hard."+name, state, requirement_type="hard", requested_value=limit,
                duration_hours=duration,
                required_hours=limit*duration if name in {"min_sunlit_fraction","min_earth_los_fraction"}
                    and limit is not None and duration is not None else None,
                contact_requirements=request.get("contact_requirements") if name.startswith("contact.") else None)
        for name, state in (candidate.get("soft_constraint_states") or {}).items():
            put(cid, "soft."+name, state, requirement_type="soft",
                requested_max_hours=(request.get("constraints") or {}).get(name), changes_hard_decision=False)
        contact = candidate.get("contact_analysis")
        if contact:
            windows=contact.get("visible_windows") or []
            put(cid, "contact", requirements=contact.get("requirements"), metrics=contact.get("metrics"),
                sampling=contact.get("sampling"), scope=contact.get("scope"),
                visible_windows=windows[:5], windows_truncated=len(windows)>5)
        # Only decisive/blocked events already supplied by the backend; no new terrain attribution.
        for index, event in enumerate(candidate.get("explanation_events", candidate.get("events", []))[:4]):
            put(cid, f"event.{index}", event=event)
    return {"interpretation_version":INTERPRETATION_VERSION,
            "result_id": result_id, "status": summary.get("status", summary.get("decision")),
            "source_hash": summary.get("source_hash"), "request": request,
            "method_version":summary.get("method_version"),"provenance":summary.get("provenance"),
            "recommended_candidate_id": summary.get("recommended_candidate_id"),
            "apply_allowed": summary.get("apply_allowed"), "coverage": summary.get("coverage"),
            "facts": facts}


def claim_issues(claims, evidence: dict, required: bool = False) -> list[str]:
    facts = evidence.get("facts", {})
    issues = []
    if required and not claims:
        issues.append("engine_evidence_required")
    for claim in claims:
        fact = facts.get(claim.evidence_id)
        if fact is None:
            issues.append("engine_evidence_not_in_result")
        elif claim.state != fact.get("state"):
            issues.append("engine_state_mismatch")
    if required and not any(facts.get(c.evidence_id, {}).get("kind") == "decision" for c in claims):
        issues.append("final_decision_evidence_required")
    return sorted(set(issues))
