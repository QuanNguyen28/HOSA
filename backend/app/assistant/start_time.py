"""Preserve explicit start-date components across clarification answers.

This deliberately handles single, explicit dates only. Mission windows, search
ranges and relative dates remain with the existing language parser/validator.
Never fill missing time or timezone from the demo baseline.
"""
from datetime import datetime, timezone
import re
import unicodedata


MONTHS = {name: index for index, name in enumerate((
    'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december'), 1)}
MONTH_PATTERN = '|'.join(MONTHS)
DATE = re.compile(
    rf'\b(?:(\d{{4}})-(\d{{1,2}})-(\d{{1,2}})|'
    rf'(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})|'
    rf'({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})|'
    rf'(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})[,]?\s+(\d{{4}})|'
    rf'(\d{{1,2}})\s+thang\s+(\d{{1,2}})\s+(?:nam\s+)?(\d{{4}}))(?!\d)', re.I)


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def start_context(request):
    """Return only user-supplied components, or None outside this narrow scope."""
    texts = [request.text, *(turn.answer for turn in request.clarifications
        if not re.search(r'how long|duration|thoi luong|keo dai|bao nhieu gio', plain(turn.question))
        or DATE.search(plain(turn.answer)))]
    joined = plain(' '.join(texts))
    # Do not reinterpret a mission end, a search window or a relative shift as
    # an arrival. Those require the existing semantic parser.
    if re.search(r'\b(?:until|ending|end at|end on|ends|between|from|to|best|search|move|shift|delay|earlier|later|tu|den|ket thuc|tim ngay|lui|som hon)\b', joined):
        return None
    day = clock = zone = None
    ambiguous = False
    found = False
    # Vietnamese writes numeric dates day/month/year ("3/12/2026" = 3 December).
    day_first = bool(re.search(r'\b(?:ngay|luc|gio|thang|nam|bat dau|phan tich|so sanh)\b', joined))
    for raw in texts:
        text = plain(raw)
        matches = list(DATE.finditer(text))
        if len(matches) > 1:
            return None
        if matches:
            found = True
            a, b, c, d, e, f, month, number, year, number2, month2, year2, vd, vm, vy = matches[0].groups()
            ambiguous = False
            if a:
                values = int(a), int(b), int(c)
            elif d:
                first, second = int(d), int(e)
                if day_first and first <= 31 and second <= 12:
                    values = (int(f), second, first)
                elif first <= 12 and second <= 12 and first != second:
                    ambiguous = True
                    day = None
                    values = None
                else:
                    values = (int(f), first, second) if second > 12 else (int(f), second, first)
            elif month:
                values = int(year), MONTHS[month], int(number)
            elif month2:
                values = int(year2), MONTHS[month2], int(number2)
            else:
                values = int(vy), int(vm), int(vd)
            if values:
                try:
                    day = datetime(*values).date().isoformat()
                except ValueError:
                    return None
            text = text[:matches[0].start()] + ' ' + text[matches[0].end():]
        offset = re.search(r'(?:\butc|\bgmt)?\s*([+-])(\d{2}):(\d{2})\b|\b(?:utc|gmt)\s*([+-])(\d{1,2})\b', text)
        clock_text = text[:offset.start()] + ' ' + text[offset.end():] if offset else text
        time_match = re.search(r'(?:\bt|(?<![\w:]))(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d.:])\s*(am\b|pm\b)?', clock_text)
        short_time = re.search(r'\b(\d{1,2})\s*(am|pm|gio|h)\b', clock_text)
        if short_time and re.search(r'(?:for|trong|keo dai|duration(?: of)?)\s*$', clock_text[:short_time.start()]):
            short_time = None
        named_time = re.search(r'\b(noon|midday|midnight|nua dem|giua trua)\b', clock_text)
        if time_match or short_time:
            match = time_match or short_time
            hour = int(match[1])
            minute = int(match[2]) if time_match else 0
            second = int(match[3] or 0) if time_match else 0
            meridiem = match[4] if time_match else match[2]
            if meridiem in ('am', 'pm'):
                if not 1 <= hour <= 12:
                    return None
                hour = hour % 12 + (12 if meridiem == 'pm' else 0)
            elif re.match(r'\s*(?:gio\s*)?(?:chieu|toi)\b', clock_text[match.end():]) and 1 <= hour < 12:
                hour += 12  # "1 giờ chiều", "8h tối"
            elif re.match(r'\s*(?:gio\s*)?(?:dem|khuya)\b', clock_text[match.end():]) and hour == 12:
                hour = 0  # "12 giờ đêm"
            if hour > 23 or minute > 59 or second > 59:
                return None
            clock = f'{hour:02}:{minute:02}:{second:02}'
        elif named_time:
            clock = '00:00:00' if named_time[1] in ('midnight', 'nua dem') else '12:00:00'
        if offset:
            sign, hours, minutes = offset.group(1, 2, 3) if offset[1] else (offset[4], offset[5], '0')
            hours, minutes = int(hours), int(minutes)
            if hours > 14 or minutes > 59 or (hours == 14 and minutes):
                return None
            zone = f'{sign}{hours:02}:{minutes:02}'
        elif re.search(r'\b(?:utc|gmt)\b|\d[zZ]\b', text):
            zone = '+00:00'
    if not found:
        return None
    missing = ['arrival_utc'] if ambiguous else [field for field, value in (('time', clock), ('timezone', zone)) if value is None]
    result = {'date': day, 'time': clock, 'timezone': zone, 'ambiguous_date': ambiguous, 'missing_fields': missing}
    if not missing:
        try:
            value = datetime.fromisoformat(f'{day}T{clock}{zone}').astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return None
        result['arrival_utc'] = value.isoformat().replace('+00:00', 'Z')
    return result


def reconcile_start(request, patch, default_duration):
    duration_intent = re.compile(
        r'\b(?:duration|lasting|thoi luong|keo dai)\b|'
        r'\b(?:for|trong|nhiem vu)\s+\d|'
        r'^\s*\d+(?:[.,]\d+)?\s*(?:hours?|days?|weeks?|gio|ngay|tuan|h)\s*[.!]?\s*$')
    texts = [request.text, *(turn.answer for turn in request.clarifications)]
    explicit_end = any(re.search(r'\b(?:end|ends|ending|until|ket thuc|den)\b|\bfrom\b.+\bto\b', plain(text))
                       for text in texts)
    if request.baseline and request.baseline.duration_hours == default_duration and not any(
            duration_intent.search(plain(text)) for text in texts) and not (explicit_end and patch.mission_end_utc is None):
        # A redundant request for the default length may be discarded. Missing
        # information about the user's explicit END must never become 72 hours.
        redundant = {'duration_hours', 'mission_end_utc', 'mission_duration'}
        patch = patch.model_copy(update={
            'unresolved_fields': [field for field in patch.unresolved_fields if field not in redundant],
            'clarification_questions': [q for q in patch.clarification_questions if q.field != 'mission_duration']})
    context = start_context(request)
    if context is None or patch.mission_end_utc or patch.search_from_utc or patch.search_until_utc or patch.arrival_shift_days is not None:
        return patch
    date_fields = {'arrival_utc', 'arrival', 'date', 'year', 'time', 'timezone'}
    fields = [field for field in patch.unresolved_fields if field not in date_fields]
    questions = [q for q in patch.clarification_questions if q.field not in date_fields]
    fields += context['missing_fields']
    return patch.model_copy(update={'arrival_utc': context.get('arrival_utc'),
        'unresolved_fields': list(dict.fromkeys(fields)), 'clarification_questions': questions})
