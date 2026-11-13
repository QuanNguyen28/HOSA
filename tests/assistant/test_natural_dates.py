"""Natural input preserves science times without inventing missing components."""
import asyncio

import pytest

from app.assistant.models import ParseRequest
from app.assistant.start_time import start_context
from conftest import FixtureLLM, default_patch


def parse(service, payload, **patch):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None,
        source_quotes=[payload['text']], **patch))
    return asyncio.run(service.parse(ParseRequest.model_validate(payload)))


@pytest.mark.parametrize('date', [
    '11/24/2026 9 AM UTC', '24/11/2026 09:00 UTC',
    'November 24, 2026 at 9 AM UTC', '24 November 2026 09:00 UTC',
    'ngày 24 tháng 11 năm 2026 lúc 9 giờ UTC',
    '2026-11-24T09:00:00Z', '24/11/2026 16:00 UTC+7',
])
def test_natural_dates_normalize_to_same_engine_time(service, request_payload, date):
    request_payload.update(text=f'Analyze IM-1 {date}', require_explicit_start=True)
    result = parse(service, request_payload)
    assert result.status == 'READY'
    assert result.spec.arrival_utc == '2026-11-24T09:00:00Z'
    assert result.spec.duration_hours == 72
    assert result.spec.site_ids == ['im1-odysseus']


def test_screenshot_date_then_time_only_keeps_english_and_default_duration(service, request_payload):
    request_payload.update(text='explore IM-1', require_explicit_start=True, clarifications=[
        {'question': 'When should the mission start?', 'answer': '11/24/2026'}])
    missing = parse(service, request_payload, unresolved_fields=['arrival_utc', 'duration_hours'],
        clarification_questions=[{'field': 'arrival_utc', 'question': 'Please give the date again.'}])
    assert missing.status == 'NEEDS_INPUT'
    assert [q.field for q in missing.questions] == ['time', 'timezone']
    assert all(q.question.isascii() for q in missing.questions)
    assert missing.patch.arrival_utc is None
    request_payload['clarifications'].append({
        'question': '\n'.join(q.question for q in missing.questions), 'answer': '9 AM UTC'})
    ready = parse(service, request_payload, unresolved_fields=['arrival_utc', 'duration_hours'])
    assert ready.status == 'READY'
    assert ready.spec.arrival_utc == '2026-11-24T09:00:00Z'
    assert ready.spec.end_utc == '2026-11-27T09:00:00Z'
    assert service.drafts.get(ready.draft_id).language == 'en'


def test_initial_explore_does_not_reask_default_duration(service, request_payload):
    request_payload.update(text='explore IM-1', require_explicit_start=True)
    result = parse(service, request_payload, unresolved_fields=['arrival_utc', 'duration_hours'])
    assert result.status == 'NEEDS_INPUT'
    assert [q.field for q in result.questions] == ['arrival_utc']


@pytest.mark.parametrize('answer,fields', [
    ('11/24/2026', ['time', 'timezone']),
    ('11/24/2026 UTC', ['time']),
    ('11/24/2026 UTC+07:00', ['time']),
    ('11/24/2026 09:00', ['timezone']),
    ('11/12/2026 09:00 UTC', ['arrival_utc']),
])
def test_missing_or_ambiguous_parts_cannot_be_guessed(service, request_payload, answer, fields):
    request_payload.update(text=f'Explore IM-1 {answer}', require_explicit_start=True)
    result = parse(service, request_payload, arrival_utc='2026-11-24T00:00:00Z')
    assert result.status == 'NEEDS_INPUT' and result.draft_id is None
    assert [q.field for q in result.questions] == fields
    if fields == ['arrival_utc']:
        assert 'day and month' in result.questions[0].question


def test_ambiguous_date_can_be_resolved_without_repeating_time(service, request_payload):
    request_payload.update(text='Explore IM-1 11/12/2026 at 9 AM UTC',
        clarifications=[{'question': 'Which day and month?', 'answer': '12 November 2026'}])
    result = parse(service, request_payload)
    assert result.status == 'READY' and result.spec.arrival_utc == '2026-11-12T09:00:00Z'


@pytest.mark.parametrize('text', [
    'Compare IM-1 and IM-2 from 2026-11-24T00:00:00Z to 2026-11-27T00:00:00Z',
    'Find the best date between November 24, 2026 and November 27, 2026',
    'Move the mission 1 day later',
])
def test_windows_search_and_relative_dates_stay_with_existing_parser(request_payload, text):
    request_payload['text'] = text
    assert start_context(ParseRequest.model_validate(request_payload)) is None


def test_custom_duration_confirmation_is_preserved(service, request_payload):
    request_payload['baseline'].update(duration_hours=240, current_site_id='im1-odysseus')
    request_payload['text'] = 'Explore IM-1 November 24, 2026 at 9 AM UTC'
    result = parse(service, request_payload)
    assert result.status == 'NEEDS_INPUT'
    assert result.issues == ['DURATION_CONFIRMATION_REQUIRED']


def test_duration_answer_is_not_used_as_a_clock(request_payload):
    request_payload.update(text='Explore IM-1 11/24/2026 UTC', clarifications=[
        {'question': 'How long should the mission last?', 'answer': '12 giờ'}])
    context = start_context(ParseRequest.model_validate(request_payload))
    assert context['time'] is None and context['missing_fields'] == ['time']


def test_seconds_are_not_rounded_onto_the_scientific_grid(service, request_payload):
    request_payload['text'] = 'Explore IM-1 2026-11-24T09:00:01Z'
    result = parse(service, request_payload)
    assert result.status == 'NEEDS_INPUT'
    assert result.issues == ['INVALID_COORDINATE_ARRIVAL']


@pytest.mark.parametrize('text', [
    'Analyze IM-1 from 2026-11-24T00:00:00Z until December 27, 2026',
    'Phân tích IM-1 từ 2026-11-24T00:00:00Z đến ngày 27 tháng 12 năm 2026',
])
def test_missing_explicit_end_cannot_silently_become_the_default_72_hours(service, request_payload, text):
    request_payload['text'] = text
    result = parse(service, request_payload, arrival_utc='2026-11-24T00:00:00Z',
        unresolved_fields=['mission_end_utc'])
    assert result.status == 'NEEDS_INPUT'
    assert result.draft_id is None
    assert result.patch.unresolved_fields == ['mission_end_utc']
