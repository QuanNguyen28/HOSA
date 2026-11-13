"""Questions for missing information, with a deterministic fallback to model proposals."""
from .models import ClarificationQuestion

TEMPLATES = {
    "arrival_utc": "Bạn muốn bắt đầu nhiệm vụ lúc nào? Bạn có thể viết tự nhiên, ví dụ ngày 24 tháng 11 năm 2026 lúc 9 giờ UTC, hoặc nêu rõ lùi bao nhiêu ngày.",
    "year": "Ngày hạ cánh thuộc năm nào?",
    "time": "Bạn muốn hạ cánh lúc mấy giờ?",
    "timezone": "Thời gian bạn vừa nêu theo múi giờ nào? Ví dụ UTC hoặc +07:00.",
    "search_range": "Bạn cho phép chọn ngày bắt đầu trong khoảng nào? Ví dụ: từ 17/11/2026 00:00 UTC đến trước 24/11/2026 00:00 UTC.",
    "site_scope": "Bạn muốn phân tích hoặc so sánh điểm nào? Hãy chọn trong 27 điểm của danh sách Khám phá, ví dụ Connecting Ridge hoặc Shackleton Rim.",
    "mission_duration": "Bạn muốn nhiệm vụ kéo dài bao nhiêu giờ, hoặc kết thúc vào ngày/giờ UTC nào? Thời lượng cần nằm trên lưới 5 phút.",
    "constraints": "Bạn cần tối thiểu bao nhiêu % thời gian có nắng và có Earth LOS? Có muốn đặt thêm mong muốn mềm về khoảng tối hoặc mất LOS liên tục không?",
    "request": "Bạn hãy nêu lại phần cần thay đổi cụ thể hơn.",
}
ISSUE_FIELDS = {
    "MISSING_BASELINE": ["request"], "INVALID_BASELINE_TIME": ["arrival_utc"],
    "TOO_MANY_SITES": ["site_scope"], "MISSING_REGION": ["site_scope"], "UNSUPPORTED_SITE_SCOPE": ["site_scope"],
    "UNSUPPORTED_SITE_COORDINATES": ["site_scope"], "AMBIGUOUS_SITE_SELECTION": ["site_scope"],
    "SITE_NOT_IN_CATALOG": ["site_scope"],
    "AMBIGUOUS_ARRIVAL": ["arrival_utc"], "UNRESOLVED_ARRIVAL": ["arrival_utc"],
    "INVALID_COORDINATE_ARRIVAL": ["arrival_utc"],
    "INCOMPLETE_SEARCH_RANGE": ["search_range"], "UNRESOLVED_SEARCH_RANGE": ["search_range"],
    "INVALID_SEARCH_RANGE": ["search_range"], "OUTSIDE_TIME_COVERAGE": ["arrival_utc"],
    "SEARCH_TOO_LARGE": ["search_range"], "INVALID_SEARCH_STEP": ["search_range"],
    "OFF_START_GRID": ["arrival_utc"], "UNSUPPORTED_DURATION": ["mission_duration"],
    "DURATION_CONFIRMATION_REQUIRED": ["mission_duration"],
    "UNSUPPORTED_BASELINE_CONFIG": ["mission_duration"], "UNSUPPORTED_REQUIREMENT": ["request"],
}
ALIASES = {"arrival": "arrival_utc", "date": "arrival_utc", "arrival_change": "arrival_utc",
           "region": "site_scope", "selected_region": "site_scope", "duration": "mission_duration",
           "duration_hours": "mission_duration", "mission_end_utc": "mission_duration", "end_utc": "mission_duration",
           "mission_duration_s": "mission_duration", "max_darkness_hours": "constraints",
           "max_earth_blackout_hours": "constraints", "search_until_utc": "search_range",
           "search_from_utc": "search_range", "min_sunlit_fraction": "constraints", "min_earth_los_fraction": "constraints"}


EN_TEMPLATES = {
    'arrival_utc': 'When should the mission start? You can write a date, time and time zone naturally, for example 24 November 2026 at 9 AM UTC.',
    'year': 'Which year is the arrival date in?',
    'time': 'What time should the mission start?',
    'timezone': 'Which time zone should I use, for example UTC or +07:00?',
    'search_range': 'What range may I search for start dates? Provide both endpoints with time zones; the upper endpoint is exclusive.',
    'site_scope': 'Which site or sites should I analyze or compare? Please choose from the 27 sites listed in Explore, for example Connecting Ridge or Shackleton Rim.',
    'mission_duration': 'How long should the mission last, or at what UTC date and time should it end?',
    'constraints': 'What minimum illumination and Earth LOS fractions are required? Do you also have darkness or blackout preferences?',
    'request': 'Please clarify the part of the mission you want to change.',
}
EN_ISSUES = {
    'OUTSIDE_TIME_COVERAGE': 'The snapshot accepts start dates from 2026-11-14 until before 2026-11-28 UTC. Which start would you like?',
    'OFF_START_GRID': 'Please choose a start on the 15-minute grid: minute 00, 15, 30 or 45. I will not round it automatically.',
    'TOO_MANY_SITES': 'Chat compares up to two sites per request. Which two catalog sites should I use?',
    'INVALID_COORDINATE_ARRIVAL': 'Please supply a start date and time with a time zone on the exact 5-minute grid.',
    'MISSING_BASELINE': 'Please provide the original mission start, duration, site and hardware before changing its schedule.',
    'UNSUPPORTED_SITE_COORDINATES': 'Those coordinates do not match one of the 27 sites listed in Explore. Which listed site should I use?',
    'SITE_NOT_IN_CATALOG': ('Chat only analyses the 27 sites listed in Explore, Compare and Best dates; the site you named is not one of them. '
                            'Which listed site should I use, for example Connecting Ridge, Shackleton Rim or Malapert Massif?'),
    'AMBIGUOUS_SITE_SELECTION': ('I am not sure which catalog site that name refers to. '
                                 'Please write the exact name, for example Connecting Ridge, Shackleton Rim or IM-1.'),
    'SEARCH_TOO_LARGE': ('That search is too long for one request: I can try at most 128 start times '
                         '(64 per site when comparing two). How should I narrow the date range?'),
    'INVALID_SEARCH_STEP': ('The search step must be a multiple of 5 minutes that divides the range evenly. '
                            'Which step should I use, for example 30 minutes or 1 hour?'),
}


SUPPORTED_VI = ("chiều cao tấm pin và ăng-ten, ngưỡng nắng và Earth LOS tối thiểu, khoảng tối hoặc mất Earth LOS liên tục tối đa, "
                "yêu cầu liên lạc (số phút liên lạc liên tục, thời gian thiết lập, số cửa sổ, hạn liên lạc đầu tiên), "
                "ngày giờ, thời lượng, khoảng tìm và cách xếp hạng")
SUPPORTED_EN = ("panel and antenna heights, minimum sunlight and Earth LOS, maximum continuous darkness or Earth blackout, contact requirements "
                "(continuous contact minutes, setup time, number of windows, first-contact deadline), dates, duration, "
                "search range and ranking")


def _unsupported_question(patch, language):
    """Name what could not be applied instead of a generic 'please rephrase'."""
    items = [item for item in (patch.unsupported_requirements if patch else []) if item.strip()]
    hardware = bool(patch and patch.hardware_change)
    if language == 'en':
        parts = []
        if items:
            parts.append('I cannot apply: ' + '; '.join(f'"{item}"' for item in items[:3]) + '.')
        if hardware:
            parts.append('Chat can change panel and antenna heights (up to 30 m); other equipment changes are not supported yet.')
        parts.append(f'Chat supports {SUPPORTED_EN}. Should I continue without that part, or would you like to rephrase it?')
        return ' '.join(parts)
    parts = []
    if items:
        parts.append('Mình chưa áp dụng được: ' + '; '.join(f'«{item}»' for item in items[:3]) + '.')
    if hardware:
        parts.append('Chat đổi được chiều cao tấm pin và ăng-ten (tối đa 30 m); các thay đổi thiết bị khác chưa hỗ trợ.')
    parts.append(f'Chat hỗ trợ {SUPPORTED_VI}. Bạn muốn bỏ phần đó để tính tiếp, hay diễn đạt lại?')
    return ' '.join(parts)


def questions_for(issue: str, patch=None, *, baseline_duration_hours=None, language='vi', start=None):
    if issue == "UNSUPPORTED_REQUIREMENT":
        return [ClarificationQuestion(field="request", question=_unsupported_question(patch, language))]
    if issue == "MISSING_CONTACT_MINUTES":
        return [ClarificationQuestion(field="constraints", question=(
            'How many minutes of continuous Earth contact does each contact need?' if language == 'en'
            else 'Mỗi lần liên lạc cần liên tục tối thiểu bao nhiêu phút?'))]
    fields = ISSUE_FIELDS.get(issue, [])
    if issue == "UNRESOLVED_FIELDS" and patch:
        fields = [ALIASES.get(field, field) for field in patch.unresolved_fields] or [q.field for q in patch.clarification_questions]
    fields = list(dict.fromkeys(field if field in TEMPLATES else "request" for field in fields)) or ["request"]
    if set(fields) >= {"year", "time", "timezone"}:
        fields = ["arrival_utc"] + [f for f in fields if f not in {"year", "time", "timezone"}]
    proposals = {q.field: q.question for q in patch.clarification_questions} if patch else {}
    result = []
    for field in fields[:3]:
        if field == 'arrival_utc' and start and start['ambiguous_date']:
            text = ('Which day and month do you mean? For example, write 24 November 2026.' if language == 'en'
                    else 'Bạn muốn nói ngày nào, tháng nào? Ví dụ: ngày 24 tháng 11 năm 2026.')
            result.append(ClarificationQuestion(field=field, question=text))
            continue
        if language == 'en':
            text = EN_ISSUES.get(issue, EN_TEMPLATES[field])
            if issue == 'DURATION_CONFIRMATION_REQUIRED':
                prior = f'{baseline_duration_hours:g} hours' if baseline_duration_hours is not None else 'a custom duration'
                text = (f'The previous mission used {prior}. For the new start, should I keep that duration, '
                        'use a different duration, or end at a specific date and time?')
            result.append(ClarificationQuestion(field=field, question=text))
            continue
        text = TEMPLATES[field] if field == 'mission_duration' or start else proposals.get(field) or TEMPLATES[field]
        if issue == 'DURATION_CONFIRMATION_REQUIRED':
            prior = f'{baseline_duration_hours:g} giờ' if baseline_duration_hours is not None else 'thời lượng riêng'
            text = (f'Lượt trước dùng {prior}. Với ngày bắt đầu mới, '
                    'bạn muốn giữ thời lượng đó, chọn thời lượng khác, hay kết thúc vào ngày/giờ nào?')
        elif issue == "OUTSIDE_TIME_COVERAGE":
            text = "Dữ liệu demo chỉ nhận ngày bắt đầu từ 14/11 đến trước 28/11/2026 UTC. Bạn muốn chọn mốc nào?"
        elif issue == "OFF_START_GRID":
            text = "Mốc bắt đầu cần đúng lưới 15 phút. Bạn chọn thời điểm nào có phút 00, 15, 30 hoặc 45? Hệ thống không tự làm tròn."
        elif issue == "AMBIGUOUS_SITE_SELECTION":
            text = ("Mình chưa chắc tên điểm bạn nêu ứng với điểm nào trong danh mục. "
                    "Bạn ghi lại đúng tên, ví dụ Connecting Ridge, Shackleton Rim hoặc IM-1 nhé?")
        elif issue == "SEARCH_TOO_LARGE":
            text = ("Khoảng tìm này quá dài cho một lượt: mỗi lượt thử tối đa 128 mốc bắt đầu "
                    "(64 mốc cho mỗi điểm khi so hai điểm). Bạn muốn thu hẹp khoảng ngày thế nào?")
        elif issue == "INVALID_SEARCH_STEP":
            text = ("Bước tìm cần là bội số của 5 phút và chia hết khoảng tìm. "
                    "Bạn muốn dùng bước nào, ví dụ 30 phút hoặc 1 giờ?")
        elif issue == "TOO_MANY_SITES":
            text = "Chat hiện so sánh tối đa hai điểm mỗi lượt. Bạn muốn chọn hai điểm nào trong danh mục Compare?"
        elif issue == "INVALID_COORDINATE_ARRIVAL":
            text = "Bạn chọn ngày giờ bắt đầu có múi giờ đúng mốc 5 phút nhé."
        elif issue == "MISSING_BASELINE":
            text = "Bạn cần cung cấp kế hoạch gốc gồm ngày giờ, thời lượng, điểm và cấu hình phần cứng trước khi thay lịch."
        elif issue == "UNSUPPORTED_SITE_COORDINATES":
            text = "Tọa độ này không trùng với điểm nào trong 27 điểm của danh sách Khám phá. Bạn muốn dùng điểm nào trong danh sách?"
        elif issue == "SITE_NOT_IN_CATALOG":
            text = ("Chat chỉ phân tích 27 điểm trong danh sách Khám phá, So sánh và Thời điểm tốt nhất; điểm bạn nêu không nằm trong danh sách này. "
                    "Bạn muốn dùng điểm nào, ví dụ Connecting Ridge, Shackleton Rim hoặc Malapert Massif?")
        result.append(ClarificationQuestion(field=field, question=text))
    return result
