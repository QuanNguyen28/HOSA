"""Language changes prose, never the mission contract or scientific evidence."""
import asyncio

import pytest

from app.assistant.language import text_language, request_language
from app.assistant.models import ParseRequest, EvaluateRequest
from app.assistant.clarification import questions_for, ISSUE_FIELDS
from app.assistant.explanations import render
from conftest import FixtureLLM, default_patch


@pytest.mark.parametrize('text,expected', [
    ('Compare IM-1 and IM-2.', 'en'),
    ('Analyze IM-1 for 24 hours.', 'en'),
    ('So sánh IM-1 và IM-2.', 'vi'),
    ('so sanh hai diem trong 24 gio', 'vi'),
    ('Hãy trả lời bằng tiếng Anh.', 'en'),
    ('Explain it in Vietnamese.', 'vi'),
    ('2028-11-17T00:00:00Z', None),
])
def test_language_selection(text, expected):
    assert text_language(text) == expected


def test_short_followup_retains_conversation_language(request_payload):
    request_payload.update(text='24', conversation_history=[{
        'text':'Analyze IM-1.', 'outcome':'evaluated', 'summary':''}])
    assert request_language(ParseRequest.model_validate(request_payload)) == 'en'


def test_every_known_clarification_has_an_english_response():
    for issue in ISSUE_FIELDS:
        questions = questions_for(issue, language='en', baseline_duration_hours=8784)
        assert questions and all(item.question.isascii() for item in questions)
    assert '8784 hours' in questions_for('DURATION_CONFIRMATION_REQUIRED', language='en', baseline_duration_hours=8784)[0].question


def test_english_missing_start_asks_in_english(service, request_payload):
    text = 'Compare Site01_P1 and Site04_P1.'
    request_payload.update(text=text, require_explicit_start=True)
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, source_quotes=[text]))
    result = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.status == 'NEEDS_INPUT' and result.questions[0].field == 'arrival_utc'
    assert 'When should the mission start' in result.questions[0].question


def test_english_evaluation_preserves_evidence_and_fact_ids(service, request_payload):
    text = 'Compare Site01_P1 and Site04_P1 on 2026-11-17T00:00:00Z.'
    request_payload['text'] = text
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc='2026-11-17T00:00:00Z', source_quotes=[text]))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == 'READY'
    assert service.drafts.get(parsed.draft_id).language == 'en'
    result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id, spec_hash=parsed.spec_hash,
        baseline=request_payload['baseline'], confirmed=True)))
    assert any('hard requirements' in line for line in result.explanation)
    assert not any('giờ' in line or 'chưa' in line or 'yêu cầu' in line for line in result.explanation)
    _, vi_facts = render(result.evidence, language='vi')
    _, en_facts = render(result.evidence, language='en')
    assert en_facts == vi_facts
    assert result.evidence.request.duration_hours == parsed.spec.duration_hours
    assert result.evidence.request.site_ids == parsed.spec.site_ids
