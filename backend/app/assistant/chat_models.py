from typing import Literal

from pydantic import Field

from app.mission.models import Contract


class EvidenceClaim(Contract):
    evidence_id: str
    state: Literal["PASS", "FAIL", "INDETERMINATE"] | None = None


class ChatTurn(Contract):
    intent: Literal["knowledge", "explain", "clarify", "point", "compare", "search"]
    answer: str = ""
    clarification: str | None = Field(default=None, max_length=2000)
    source_ids: list[str] = Field(default_factory=list, max_length=12)
    query: dict | None = None
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list, max_length=80)


class NewSession(Contract):
    pass


class NewMessage(Contract):
    text: str = Field(min_length=1, max_length=12000)


class ApplyPlan(Contract):
    run_id: str
    expected_applied_state: dict
    candidate: dict
