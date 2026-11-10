"""Explicit scripted language-model substitute for terminal rehearsal only."""
import json
import re

from app.assistant.models import ExplainPlan, RequestPatch
from app.assistant.provider import Completion

DEMO_PROMPT = "Đổi lịch hạ cánh sang ngày 17/11, giữ phần cứng và đổi điểm trong vùng này."


class DemoLLM:
    async def complete(self, contract, messages):
        if contract is RequestPatch:
            request = json.loads(messages[-1]["content"])["request"]
            patch = {"arrival_shift_days": None, "arrival_utc": None, "duration_hours": None,
                "hardware_change": False, "site_scope": "selected", "max_darkness_hours": None,
                "max_earth_blackout_hours": None, "min_sunlit_fraction": None, "unresolved_fields": [],
                "unsupported_requirements": [], "source_quotes": ["17/11"]}
            if request["text"] != DEMO_PROMPT:
                patch.update(unsupported_requirements=["scripted_demo_requires_the_displayed_sample"],
                             source_quotes=[request["text"]])
            else:
                answer = request["clarifications"][-1]["answer"] if request["clarifications"] else ""
                match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})", answer)
                if match:
                    patch.update(arrival_utc=match.group(), source_quotes=[match.group()])
                else:
                    patch.update(unresolved_fields=["year","time","timezone"],
                        clarification_questions=[{"field":"arrival_utc",
                            "question":"Ngày 17/11 thuộc năm nào, lúc mấy giờ và theo múi giờ nào? Ví dụ 2026-11-17T00:00:00Z."}])
            output = RequestPatch.model_validate(patch)
        else:
            evidence = json.loads(messages[-1]["content"])
            blocks = []
            for candidate in evidence["candidates"]:
                key = candidate["candidate_id"]
                reason, suffix = ("DATA_MISSING","availability") if candidate["issue"] else (
                    ("EARTH_LOS","earth") if candidate["constraint_states"].get("max_earth_blackout_hours") == "FAIL" else ("DARKNESS","dark"))
                blocks.append({"site_id":candidate["site_id"], "candidate_id":key, "reason_code":reason, "fact_ids":[key+"."+suffix]})
            output = ExplainPlan.model_validate({"run_id":evidence["run_id"], "spec_hash":evidence["spec_hash"],
                                                 "lead_code":evidence["status"], "blocks":blocks})
        return Completion(output, "scripted-demo", 0.0, {})
