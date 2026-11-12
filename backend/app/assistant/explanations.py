"""Validate references and render factual prose; LLMs do not own numbers or decisions."""

REASON_SUFFIX = {"DARKNESS": "dark", "BLACKOUT": "blackout", "EARTH_LOS": "earth",
                 "SUNLIGHT": "sun", "DATA_MISSING": "availability"}
HARD_CONSTRAINT = {"EARTH_LOS": "min_earth_los_fraction", "SUNLIGHT": "min_sunlit_fraction"}


def explanation_options(candidate, facts):
    """Allowed reason/fact pairs for this exact candidate and computed status."""
    options = {}
    for reason, suffix in REASON_SUFFIX.items():
        if candidate.issue and reason != "DATA_MISSING":
            continue
        if candidate.decision == "FAIL" and candidate.constraint_states.get(HARD_CONSTRAINT.get(reason)) != "FAIL":
            continue
        fact_id = f"{candidate.candidate_id}.{suffix}"
        if fact_id in facts and facts[fact_id]["candidate_id"] == candidate.candidate_id:
            options[reason] = fact_id
    return options


def identity(block):
    return block.candidate_id or block.site_id


def valid_plan(plan, evidence):
    if (plan.run_id, plan.spec_hash, plan.lead_code) != (evidence.run_id, evidence.spec_hash, evidence.status):
        return False
    candidates = {c.candidate_id: c for c in evidence.candidates}
    if sorted(identity(b) for b in plan.blocks) != sorted(candidates):
        return False
    for block in plan.blocks:
        key = identity(block)
        candidate = candidates[key]
        if block.site_id != candidate.site_id:
            return False
        if explanation_options(candidate, evidence.facts).get(block.reason_code) not in block.fact_ids:
            return False
        if any(k not in evidence.facts or evidence.facts[k]["candidate_id"] != key for k in block.fact_ids):
            return False
    return True


def render(evidence, plan=None):
    ordering = [identity(b) for b in plan.blocks] if plan else [c.candidate_id for c in evidence.candidates]
    by_id = {c.candidate_id: c for c in evidence.candidates}
    focus = {identity(b): b.reason_code for b in plan.blocks} if plan else {}
    texts, fact_ids = [], []
    for key in ordering:
        c = by_id[key]
        label = f"{c.site_id} ({c.start_utc})" if evidence.request.search_from_utc else c.site_id
        if c.issue:
            texts.append(f"{label}: chưa đủ dữ liệu; không dùng để xếp hạng.")
            fact_ids.append(f"{key}.availability")
            continue
        sun, earth = c.metrics["total_sun_hours"], c.metrics["total_earth_los_hours"]
        sun_text = (f"có nắng {sun[0]:.2f}–{sun[1]:.2f} giờ "
                    f"(tối thiểu {evidence.request.min_sunlit_fraction*100:g}%)")
        earth_text = (f"có tầm nhìn Trái Đất {earth[0]:.2f}–{earth[1]:.2f} giờ "
                      f"(tối thiểu {evidence.request.min_earth_los_fraction*100:g}%)")
        ordered_metrics = (earth_text, sun_text) if focus.get(key) == "EARTH_LOS" else (sun_text, earth_text)
        decision = "chưa đủ căn cứ để kết luận (INDETERMINATE)" if c.decision == "INDETERMINATE" else c.decision
        texts.append(f"{label}: {decision} theo yêu cầu cứng; {'; '.join(ordered_metrics)}.")
        fact_ids.extend((f"{key}.sun", f"{key}.earth"))
        for name, metric, suffix, title in (("max_darkness_hours", "longest_dark_hours", "dark", "tối liên tục"),
                                           ("max_earth_blackout_hours", "longest_blackout_hours", "blackout", "mất Earth LOS liên tục")):
            if name not in c.soft_constraint_states:
                continue
            low, high = c.metrics[metric]
            limit = getattr(evidence.request.constraints, name)
            state = c.soft_constraint_states[name]
            note = "vượt mong muốn" if state == "FAIL" else "chưa xác định" if state == "INDETERMINATE" else "đáp ứng mong muốn"
            texts.append(f"{label}: yêu cầu mềm {title} {low:.2f}–{high:.2f} giờ, mong muốn ≤ {limit:g} giờ; {note}, không làm đổi kết luận yêu cầu cứng.")
            fact_ids.append(f"{key}.{suffix}")
        if evidence.request.rank_by == "longest_joint_hours":
            low, high = c.metrics["longest_joint_hours"]
            texts.append(f"{label}: khoảng khả kiến đồng thời dài nhất {low:.2f}–{high:.2f} giờ.")
            fact_ids.append(f"{key}.joint")
        ranking = next((r for r in evidence.ranking if r.candidate_id == key), None)
        if ranking and ranking.rank_min != ranking.rank_max:
            texts.append(f"{label}: khoảng hạng {ranking.rank_min}–{ranking.rank_max}; các cận chỉ số xếp hạng chồng lấn.")
        if any(context["touches_window_edge"] for context in c.metric_context.values()):
            texts.append(f"{label}: sự kiện chạm biên nhiệm vụ; thời lượng ngoài cửa sổ chưa được đo.")
    if not evidence.apply_allowed:
        texts.append("Chưa có phương án đạt trong tập đã đánh giá; không tự nới ngưỡng hoặc cho phép áp dụng.")
    if evidence.recommended_candidate_id:
        selected = by_id[evidence.recommended_candidate_id]
        texts.append(f"Phương án đề xuất: {selected.site_id}, bắt đầu {selected.start_utc}; trạng thái {selected.decision}.")
    if evidence.coverage["indeterminate"]:
        texts.append(f"Có {evidence.coverage['indeterminate']} phương án chưa đủ căn cứ kết luận; không suy rộng ra cả vùng.")
    return texts, fact_ids
