"""Validate references and render factual prose; LLMs do not own numbers or decisions."""


def identity(block):
    return block.candidate_id or block.site_id


def valid_plan(plan, evidence):
    if (plan.run_id, plan.spec_hash, plan.lead_code) != (evidence.run_id, evidence.spec_hash, evidence.status):
        return False
    candidates = {c.candidate_id: c for c in evidence.candidates}
    if sorted(identity(b) for b in plan.blocks) != sorted(candidates):
        return False
    suffix = {"DARKNESS": "dark", "EARTH_LOS": "earth", "SUNLIGHT": "sun", "DATA_MISSING": "availability"}
    constraint = {"DARKNESS": "max_darkness_hours", "EARTH_LOS": "max_earth_blackout_hours", "SUNLIGHT": "min_sunlit_fraction"}
    for block in plan.blocks:
        key = identity(block)
        candidate = candidates[key]
        if block.site_id != candidate.site_id:
            return False
        if f"{key}.{suffix[block.reason_code]}" not in block.fact_ids:
            return False
        if any(k not in evidence.facts or evidence.facts[k]["candidate_id"] != key for k in block.fact_ids):
            return False
        if candidate.issue and block.reason_code != "DATA_MISSING":
            return False
        if candidate.decision == "FAIL" and candidate.constraint_states.get(constraint.get(block.reason_code)) != "FAIL":
            return False
    return True


def render(evidence, plan=None):
    ordering = [identity(b) for b in plan.blocks] if plan else [c.candidate_id for c in evidence.candidates]
    by_id = {c.candidate_id: c for c in evidence.candidates}
    texts, fact_ids = [], []
    for key in ordering:
        c = by_id[key]
        label = f"{c.site_id} ({c.start_utc})" if evidence.request.search_from_utc else c.site_id
        if c.issue:
            texts.append(f"{label}: chưa đủ dữ liệu; không dùng để xếp hạng.")
            fact_ids.append(f"{key}.availability")
            continue
        dark, earth = c.metrics["longest_dark_hours"], c.metrics["longest_blackout_hours"]
        texts.append(f"{label}: {c.decision}; tối liên tục {dark[0]:.2f}–{dark[1]:.2f} giờ "
                     f"(ngưỡng {evidence.request.constraints.max_darkness_hours:g}); "
                     f"mất tầm nhìn Trái Đất {earth[0]:.2f}–{earth[1]:.2f} giờ "
                     f"(ngưỡng {evidence.request.constraints.max_earth_blackout_hours:g}).")
        fact_ids.extend((f"{key}.dark", f"{key}.earth"))
        if evidence.request.min_sunlit_fraction is not None or evidence.request.rank_by == "total_sun_hours":
            low, high = c.metrics["total_sun_hours"]
            suffix = f"; ngưỡng tối thiểu {evidence.request.min_sunlit_fraction*100:g}%" if evidence.request.min_sunlit_fraction is not None else ""
            texts.append(f"{label}: có nắng {low:.2f}–{high:.2f} giờ ({low/72*100:.2f}–{high/72*100:.2f}%){suffix}.")
            fact_ids.append(f"{key}.sun")
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
