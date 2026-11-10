from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.assistant.config import AssistantSettings
from app.assistant.engine import PlanningAdapter
from app.assistant.models import ExplainPlan, RequestPatch
from app.assistant.provider import Completion
from app.assistant.service import AssistantService
from app.assistant.store import DraftStore
from app.services.lunarsight import planning


def default_patch(**updates):
    return RequestPatch.model_validate({"arrival_shift_days": 3, "arrival_utc": None,
        "duration_hours": None, "hardware_change": False, "site_scope": "selected",
        "max_darkness_hours": 12, "max_earth_blackout_hours": None, "min_sunlit_fraction": None,
        "unresolved_fields": [], "unsupported_requirements": [], "source_quotes": ["ba ngày"], **updates})


class FixtureLLM:
    def __init__(self, patch=None, mutate=None):
        self.patch = patch or default_patch()
        self.mutate = mutate
        self.calls = []

    async def complete(self, contract, messages):
        self.calls.append(contract.__name__)
        if contract is RequestPatch:
            output = self.patch
        else:
            evidence = json.loads(messages[-1]["content"])
            payload = {"run_id": evidence["run_id"], "spec_hash": evidence["spec_hash"],
                "lead_code": evidence["status"], "blocks": [
                    {"site_id": c["site_id"], "candidate_id": c["candidate_id"],
                     "reason_code": "DATA_MISSING" if c["issue"] else "EARTH_LOS" if c["constraint_states"].get("min_earth_los_fraction") == "FAIL" else "SUNLIGHT",
                     "fact_ids": [c["candidate_id"] + (".availability" if c["issue"] else ".earth" if c["constraint_states"].get("min_earth_los_fraction") == "FAIL" else ".sun")]}
                    for c in evidence["candidates"]]}
            if self.mutate:
                self.mutate(payload)
            output = ExplainPlan.model_validate(payload)
        return Completion(output, "fixture-model", 1.0, {})


@pytest.fixture
def request_payload():
    return {"text": "Lịch hạ cánh bị lùi ba ngày. Giữ phần cứng, đổi điểm trong vùng này, tối tối đa 12 giờ.",
        "baseline": {"scenario_id": "south_pole_demo_v1", "arrival_utc": "2026-11-14T00:00:00Z",
            "duration_hours": 72, "hardware": {"sun_panel": 1, "earth_antenna": 2},
            "constraints": {"max_darkness_hours": 12, "max_earth_blackout_hours": 6},
            "min_sunlit_fraction": 0.8, "min_earth_los_fraction": 0.8,
            "current_site_id": "Site01_P1"}, "selected_site_ids": ["Site01_P1", "Site04_P1"]}


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(planning, "_result_dir", lambda: tmp_path / "results")
    return AssistantService(AssistantSettings(assistant_enabled=True, _env_file=None), FixtureLLM(), DraftStore(), PlanningAdapter())
