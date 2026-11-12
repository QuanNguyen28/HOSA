"""Validate references and render factual prose; LLMs do not own numbers or decisions."""


def identity(block):
    return block.candidate_id or block.site_id


def valid_plan(plan, evidence):
    if (plan.run_id, plan.spec_hash, plan.lead_code) != (evidence.run_id, evidence.spec_hash, evidence.status):
        return False
    candidates = {c.candidate_id: c for c in evidence.candidates}
    if sorted(identity(b) for b in plan.blocks) != sorted(candidates):
        return False
    suffix = {"DARKNESS": "dark", "BLACKOUT": "blackout", "EARTH_LOS": "earth", "SUNLIGHT": "sun", "DATA_MISSING": "availability"}
    constraint = {"EARTH_LOS": "min_earth_los_fraction", "SUNLIGHT": "min_sunlit_fraction"}
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
        sun, earth = c.metrics["total_sun_hours"], c.metrics["total_earth_los_hours"]
        texts.append(f"{label}: {c.decision}; có nắng {sun[0]:.2f}–{sun[1]:.2f} giờ "
                     f"(tối thiểu {evidence.request.min_sunlit_fraction*100:g}%); "
                     f"có Earth LOS {earth[0]:.2f}–{earth[1]:.2f} giờ "
                     f"(tối thiểu {evidence.request.min_earth_los_fraction*100:g}%).")
        fact_ids.extend((f"{key}.sun", f"{key}.earth"))
        if not c.validation.get("passed"):
            if c.validation.get("mission_path", {}).get("passed"):
                texts.append(f"{label}: kiểm chứng đường đi của nhiệm vụ đạt; kiểm chứng horizon toàn vòng vẫn chưa đạt. Ngưỡng còn PROVISIONAL.")
            elif c.decision == "FAIL":
                texts.append(f"{label}: không đạt yêu cầu cứng; vẫn trả FAIL dù kiểm chứng dữ liệu/số học chưa đạt: " + ", ".join(c.validation.get("reason_codes", [])) + ".")
            fact_ids.append(f"{key}.validation")
        if c.resolution.get("enabled"):
            status = c.resolution.get("status")
            if status == "resolved":
                texts.append(f"{label}: đã hoàn tất kiểm chứng bổ sung; {c.resolution.get('initial_decision')} → {c.decision}; giữ nguyên yêu cầu và ngưỡng kiểm chứng.")
            elif c.decision == "INDETERMINATE":
                reasons = ", ".join(c.validation.get("reason_codes", []))
                error = c.resolution.get("error_code")
                texts.append(f"{label}: kết quả theo mẫu là {c.nominal_sampled_decision}; kiểm chứng bổ sung chưa hoàn tất: {reasons}" + (f"; {error}." if error else "."))
            fact_ids.append(f"{key}.validation")

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
