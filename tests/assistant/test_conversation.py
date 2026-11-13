"""Conversation regressions: state inheritance, commands, cancellation and coordinates."""
import asyncio
import json
from copy import deepcopy

import pytest

from app.assistant.models import ParseRequest, RequestPatch
from app.assistant.sites import available_sites
from conftest import FixtureLLM, default_patch
from scripts.assistant_chat import ChatSession, run_console


class TurnLLM(FixtureLLM):
    def __init__(self, patches):
        super().__init__()
        self.patches = iter(patches)
        self.requests = []

    async def complete(self, contract, messages):
        if contract is RequestPatch:
            self.requests.append(json.loads(messages[-1]['content'])['request'])
            self.patch = next(self.patches)
        return await super().complete(contract, messages)


def patch(text, **updates):
    return default_patch(**{'arrival_shift_days': None, 'max_darkness_hours': None,
        'site_scope': 'unspecified', 'source_quotes': [text], **updates})


def console(service, payload, answers):
    answers = iter(answers)
    output = []
    assert run_console(service, payload, ask=lambda _: next(answers), say=output.append) == 0
    return output


def test_commands_update_baseline_and_do_not_call_llm(service, request_payload):
    output = console(service, request_payload, ['/sites Site04_P1', '/baseline', '/sites all', '/baseline', '/quit'])
    states = [json.loads(s) for s in output if s.startswith('{')]
    assert states[0]['current_site_id'] == 'Site04_P1'
    assert states[0]['selected_site_ids'] == ['Site04_P1']
    assert states[1]['selected_site_ids'] == ['Site01_P1', 'Site04_P1']
    assert not service.llm.calls


def test_evaluated_turn_becomes_next_turn_context(service, request_payload):
    service.llm = TurnLLM([patch('chọn Site04', site_ids=['Site04_P1'],
        arrival_utc='2026-11-17T00:00:00Z', max_earth_blackout_hours=5),
        patch('giảm tối', max_darkness_hours=8)])
    original = deepcopy(request_payload)
    console(service, request_payload, ['chọn Site04', 'y', 'giảm tối', 'y', '/quit'])
    first, second = service.llm.requests
    assert not first['conversation_history']
    assert second['baseline']['current_site_id'] == 'Site04_P1'
    assert second['baseline']['arrival_utc'] == '2026-11-17T00:00:00Z'
    assert second['baseline']['constraints']['max_earth_blackout_hours'] == 5
    assert second['selected_site_ids'] == ['Site04_P1']
    assert second['conversation_history'][0]['text'] == 'chọn Site04'
    assert second['conversation_history'][0]['outcome'] == 'evaluated'
    assert request_payload == original


def test_cancelled_turn_does_not_apply_plan(service, request_payload):
    service.llm = TurnLLM([patch('đổi điểm', site_ids=['Site04_P1']), patch('giữ nguyên')])
    console(service, request_payload, ['đổi điểm', 'n', 'giữ nguyên', 'n', '/quit'])
    second = service.llm.requests[1]
    assert second['baseline']['current_site_id'] == 'Site01_P1'
    assert second['conversation_history'][0]['outcome'] == 'cancelled'


def test_site_command_during_confirmation_invalidates_draft(service, request_payload):
    service.llm = TurnLLM([patch('giữ nguyên'), patch('giữ nguyên')])
    console(service, request_payload, ['giữ nguyên', '/sites Site04_P1', 'giữ nguyên', 'n', '/quit'])
    assert 'ExplainPlan' not in service.llm.calls
    assert service.llm.requests[1]['baseline']['current_site_id'] == 'Site04_P1'


def test_new_keeps_context_reset_clears_it(request_payload):
    state = ChatSession(request_payload)
    state.command('/sites Site04_P1', lambda _: None)
    state.text = 'đang hỏi'
    state.command('/new', lambda _: None)
    assert state.text is None and state.baseline.current_site_id == 'Site04_P1'
    assert len(state.history) == 1
    state.command('/reset', lambda _: None)
    assert state.baseline.current_site_id == 'Site01_P1' and state.history == []


def test_unspecified_scope_uses_selection(service, request_payload):
    request_payload['selected_site_ids'] = ['Site04_P1']
    service.llm = FixtureLLM(patch('ba ngày'))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'READY' and result.spec.site_ids == ['Site04_P1']


def custom_duration_context(payload, hours=8784):
    payload['baseline'].update(arrival_utc='2027-11-17T00:00:00Z', duration_hours=hours,
                               current_site_id='im1-odysseus')
    payload['selected_site_ids'] = ['im1-odysseus']
    return payload


@pytest.mark.parametrize('hours', [240, 8784])
@pytest.mark.parametrize('copied_duration', [False, True])
def test_new_date_does_not_silently_reuse_custom_duration(service, request_payload, hours, copied_duration):
    request_payload = custom_duration_context(request_payload, hours)
    text = 'Phân tích IM-1 vào 2028-11-17T00:00:00Z'
    request_payload['text'] = text
    service.llm = FixtureLLM(patch(text, arrival_utc='2028-11-17T00:00:00Z',
        duration_hours=hours if copied_duration else None))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'NEEDS_INPUT' and result.draft_id is None
    assert result.issues == ['DURATION_CONFIRMATION_REQUIRED']
    assert result.questions[0].field == 'mission_duration'
    assert str(hours) in result.questions[0].question


@pytest.mark.parametrize('text,duration', [
    ('Phân tích IM-1 vào 2028-11-17T00:00:00Z, giữ nguyên thời lượng', None),
    ('Phân tích IM-1 vào 2028-11-17T00:00:00Z trong 24 giờ', 24),
])
def test_explicit_duration_choice_with_new_date_is_respected(service, request_payload, text, duration):
    request_payload = custom_duration_context(request_payload)
    request_payload['text'] = text
    service.llm = FixtureLLM(patch(text, arrival_utc='2028-11-17T00:00:00Z', duration_hours=duration))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'READY'
    assert result.spec.duration_hours == (8784 if duration is None else duration)


def test_relative_start_shift_is_not_mistaken_for_mission_duration(service, request_payload):
    request_payload = custom_duration_context(request_payload)
    text = 'Lùi ngày bắt đầu 1 ngày, giữ phần cứng'
    request_payload['text'] = text
    service.llm = FixtureLLM(patch(text, arrival_shift_days=1))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'NEEDS_INPUT' and result.issues == ['DURATION_CONFIRMATION_REQUIRED']


def test_duration_clarification_resolves_without_reusing_a_year(service, request_payload):
    request_payload = custom_duration_context(request_payload)
    text = 'Phân tích IM-1 vào 2028-11-17T00:00:00Z'
    request_payload.update(text=text, clarifications=[{'question':'Bạn muốn nhiệm vụ kéo dài bao nhiêu giờ?', 'answer':'24'}])
    service.llm = FixtureLLM(patch(text, arrival_utc='2028-11-17T00:00:00Z', duration_hours=24))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'READY' and result.spec.duration_hours == 24
    assert result.spec.end_utc == '2028-11-18T00:00:00Z'


def test_missing_duration_fields_ask_about_duration_not_generic_request(service, request_payload):
    request_payload = custom_duration_context(request_payload)
    text = 'Phân tích IM-1 vào 2028-11-17T00:00:00Z'
    request_payload['text'] = text
    service.llm = FixtureLLM(patch(text, arrival_utc='2028-11-17T00:00:00Z',
        unresolved_fields=['duration_hours', 'mission_end_utc']))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'NEEDS_INPUT'
    assert [q.field for q in result.questions] == ['mission_duration']


def test_explicit_keep_current_overrides_region(service, request_payload):
    service.llm = FixtureLLM(patch('ba ngày', site_scope='keep_current'))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.spec.site_ids == ['Site01_P1']


@pytest.mark.parametrize('longitude', [203.733786, -156.266214])
def test_coordinate_command_identifies_site04(longitude, request_payload):
    state = ChatSession(request_payload)
    state.command(f'/sites coords -89.779800 {longitude}', lambda _: None)
    assert state.baseline.current_site_id == 'Site04_P1'
    assert state.selected == ['Site04_P1']


def test_coordinate_command_rejects_unknown_and_nonfinite(request_payload):
    state = ChatSession(request_payload)
    for command in ['/sites coords -89 10', '/sites coords nan 0', '/sites coords 0 inf', '/sites coords 91 0']:
        state.command(command, lambda _: None)
        assert state.baseline.current_site_id == 'Site01_P1'


def test_natural_language_coordinate_selection_and_rejection(service, request_payload):
    coords = available_sites()[1]
    service.llm = FixtureLLM(patch('ba ngày', site_coordinates={k: coords[k] for k in ('lat_deg', 'lon_e_deg')}))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.spec.site_ids == ['Site04_P1']
    service.llm.patch = patch('ba ngày', site_coordinates={'lat_deg': -89, 'lon_e_deg': 10})
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.issues == ['UNSUPPORTED_SITE_COORDINATES'] and result.draft_id is None


def test_extra_planning_context_is_inherited_and_exact_date_clears_search(service, request_payload):
    request_payload['baseline']['min_sunlit_fraction'] = 0.5
    request_payload['planning_context'] = {'rank_by': 'total_sun_hours',
        'search_from_utc': '2026-11-17T00:00:00Z', 'search_until_utc': '2026-11-18T00:00:00Z'}
    service.llm = FixtureLLM(patch('ba ngày'))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.spec.search_from_utc == '2026-11-17T00:00:00Z'
    assert result.spec.min_sunlit_fraction == 0.5 and result.spec.rank_by == 'total_sun_hours'
    service.llm.patch = patch('ba ngày', arrival_utc='2026-11-19T00:00:00Z')
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.spec.search_from_utc is None


def test_history_cannot_quote_assistant_summary(service, request_payload):
    request_payload['conversation_history'] = [{'text': 'giữ nguyên', 'outcome': 'evaluated', 'summary': 'ba ngày'}]
    request_payload['text'] = 'như cũ'
    service.llm = FixtureLLM(patch('ba ngày'))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.issues == ['UNSUPPORTED_SOURCE_QUOTE']


def test_pending_information_survives_next_outer_turn(service, request_payload):
    service.llm = TurnLLM([
        patch('đổi ngày', unresolved_fields=['arrival_utc']),
        patch('đổi ngày', unresolved_fields=['arrival_utc']),
        patch('2026-11-17T00:00:00Z', arrival_utc='2026-11-17T00:00:00Z')])
    answers = iter(['đổi ngày', 'chưa biết', '2026-11-17T00:00:00Z', 'n', '/quit'])
    run_console(service, request_payload, ask=lambda _: next(answers), say=lambda _: None,
                max_clarifications=1)
    last = service.llm.requests[-1]
    assert last['text'] == 'đổi ngày'
    assert [c['answer'] for c in last['clarifications']] == ['chưa biết', '2026-11-17T00:00:00Z']


def test_history_is_bounded_and_new_does_not_reapply_old_changes(request_payload):
    state = ChatSession(request_payload)
    for index in range(12):
        state.text = f'lượt {index}'
        state.finish('abandoned')
    assert len(state.history) == 8
    assert state.history[0].text == 'lượt 4'
    assert state.baseline.arrival_utc == request_payload['baseline']['arrival_utc']


def test_hard_earth_minimum_is_remembered_independently_of_soft_limits(service, request_payload):
    service.llm = TurnLLM([patch('Earth LOS ít nhất 10%', min_earth_los_fraction=.1),
                           patch('giảm khoảng tối', max_darkness_hours=4)])
    output = console(service, request_payload, ['Earth LOS ít nhất 10%', 'y', 'giảm khoảng tối', 'n', '/quit'])
    second = service.llm.requests[1]
    assert second['baseline']['min_earth_los_fraction'] == .1
    assert second['baseline']['min_sunlit_fraction'] == .8
    assert any('yêu cầu mềm' in line for line in output)


def test_explicit_earth_minimum_overrides_baseline_without_changing_sun(service, request_payload):
    service.llm = FixtureLLM(patch('Earth LOS ít nhất 90%', min_earth_los_fraction=.9))
    request_payload['text'] = 'Earth LOS ít nhất 90%'
    response = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert response.spec.min_earth_los_fraction == .9
    assert response.spec.min_sunlit_fraction == .8
    assert response.spec.constraints.max_earth_blackout_hours == 6
