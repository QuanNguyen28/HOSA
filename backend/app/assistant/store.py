"""Bounded single-process pilot store; a shared repository can replace it later."""
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from uuid import uuid4

from .models import EvaluateResponse, RequestSpec
from .provider import AssistantError


@dataclass
class Draft:
    spec: RequestSpec
    spec_hash: str
    expires_at: float
    parse_ms: float
    model: str
    parse_usage: dict = field(default_factory=dict)
    provider: str | None = None
    trace: list[dict] = field(default_factory=list)
    started: bool = False
    result: EvaluateResponse | None = None
    failure: tuple[str, int] | None = None
    language: str = 'vi'
    user_text: str = ''


class DraftStore:
    def __init__(self):
        self._items: dict[str, Draft] = {}
        self._lock = Lock()

    def create(self, draft: Draft, capacity: int) -> str:
        with self._lock:
            self._items = {k: v for k, v in self._items.items() if v.expires_at > monotonic()}
            if len(self._items) >= capacity:
                raise AssistantError("DRAFT_CAPACITY_REACHED", 503)
            identifier = uuid4().hex
            self._items[identifier] = draft
            return identifier

    def get(self, identifier: str) -> Draft:
        with self._lock:
            draft = self._items.get(identifier)
            if draft is None or draft.expires_at <= monotonic():
                raise AssistantError("DRAFT_EXPIRED_OR_UNKNOWN", 410)
            return draft

    def claim(self, identifier: str) -> tuple[Draft, bool]:
        with self._lock:
            draft = self._items.get(identifier)
            if draft is None or draft.expires_at <= monotonic():
                raise AssistantError("DRAFT_EXPIRED_OR_UNKNOWN", 410)
            if draft.failure:
                raise AssistantError(*draft.failure)
            if draft.result is not None:
                return draft, False
            if draft.started:
                raise AssistantError("DRAFT_ALREADY_STARTED", 409)
            draft.started = True
            return draft, True

    def finish(self, identifier: str, result: EvaluateResponse) -> None:
        with self._lock:
            self._items[identifier].result = result

    def fail(self, identifier: str, code: str, status: int) -> None:
        with self._lock:
            self._items[identifier].failure = (code, status)


store = DraftStore()
