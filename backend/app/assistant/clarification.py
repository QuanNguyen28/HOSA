"""Questions for missing information, with a deterministic fallback to model proposals."""
from .models import ClarificationQuestion

TEMPLATES = {
    "arrival_utc": "Bạn muốn hạ cánh lúc nào? Cho biết đầy đủ năm, giờ và múi giờ; ví dụ 2026-11-17T00:00:00Z, hoặc nêu rõ lùi bao nhiêu ngày.",
    "year": "Ngày hạ cánh thuộc năm nào?",
    "time": "Bạn muốn hạ cánh lúc mấy giờ?",
    "timezone": "Thời gian bạn vừa nêu theo múi giờ nào? Ví dụ UTC hoặc +07:00.",
    "search_range": "Bạn cho phép đổi ngày trong khoảng nào? Nêu đủ hai mốc ISO có múi giờ; mốc cuối không bao gồm.",
    "site_scope": "Bạn muốn giữ điểm hiện tại hay chọn Site01_P1, Site04_P1 hoặc cả hai?",
    "mission_duration": "Thời lượng nhiệm vụ là bao nhiêu? Dữ liệu demo hiện hỗ trợ 72 giờ.",
    "constraints": "Bạn muốn đặt ngưỡng nào và bao nhiêu giờ? Ví dụ tối liên tục tối đa 12 giờ.",
    "request": "Bạn hãy nêu lại phần cần thay đổi cụ thể hơn.",
}
ISSUE_FIELDS = {
    "MISSING_BASELINE": ["request"], "INVALID_BASELINE_TIME": ["arrival_utc"],
    "MISSING_REGION": ["site_scope"], "UNSUPPORTED_SITE_SCOPE": ["site_scope"],
    "AMBIGUOUS_ARRIVAL": ["arrival_utc"], "UNRESOLVED_ARRIVAL": ["arrival_utc"],
    "INCOMPLETE_SEARCH_RANGE": ["search_range"], "UNRESOLVED_SEARCH_RANGE": ["search_range"],
    "INVALID_SEARCH_RANGE": ["search_range"], "OUTSIDE_TIME_COVERAGE": ["arrival_utc"],
    "OFF_START_GRID": ["arrival_utc"], "UNSUPPORTED_DURATION": ["mission_duration"],
    "UNSUPPORTED_BASELINE_CONFIG": ["mission_duration"], "UNSUPPORTED_REQUIREMENT": ["request"],
}
ALIASES = {"arrival": "arrival_utc", "date": "arrival_utc", "arrival_change": "arrival_utc",
           "region": "site_scope", "selected_region": "site_scope", "duration": "mission_duration",
           "mission_duration_s": "mission_duration", "max_darkness_hours": "constraints",
           "max_earth_blackout_hours": "constraints", "search_until_utc": "search_range",
           "search_from_utc": "search_range"}


def questions_for(issue: str, patch=None):
    fields = ISSUE_FIELDS.get(issue, [])
    if issue == "UNRESOLVED_FIELDS" and patch:
        fields = [ALIASES.get(field, field) for field in patch.unresolved_fields] or [q.field for q in patch.clarification_questions]
    fields = list(dict.fromkeys(field if field in TEMPLATES else "request" for field in fields)) or ["request"]
    if set(fields) >= {"year", "time", "timezone"}:
        fields = ["arrival_utc"] + [f for f in fields if f not in {"year", "time", "timezone"}]
    proposals = {q.field: q.question for q in patch.clarification_questions} if patch else {}
    result = []
    for field in fields[:3]:
        text = proposals.get(field) or TEMPLATES[field]
        if issue == "OUTSIDE_TIME_COVERAGE":
            text = "Dữ liệu demo chỉ nhận ngày bắt đầu từ 14/11 đến trước 28/11/2026 UTC. Bạn muốn chọn mốc nào?"
        elif issue == "OFF_START_GRID":
            text = "Mốc bắt đầu cần đúng lưới 15 phút. Bạn chọn thời điểm nào có phút 00, 15, 30 hoặc 45? Hệ thống không tự làm tròn."
        elif issue == "MISSING_BASELINE":
            text = "Bạn cần cung cấp kế hoạch gốc gồm ngày giờ, thời lượng, điểm và cấu hình phần cứng trước khi thay lịch."
        result.append(ClarificationQuestion(field=field, question=text))
    return result
