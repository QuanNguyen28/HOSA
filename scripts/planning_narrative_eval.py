"""Real-provider acceptance of the UI's legacy parse/review/evaluate narrative flow."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:5179")
    parser.add_argument("--output", type=Path, default=ROOT/"data/cache/assistant/planning-narrative-live.json")
    args = parser.parse_args()
    if not args.live:
        print("No requests made; pass --live to run paid inference.")
        return 2
    from app.assistant.engine import PlanningAdapter
    from app.assistant.models import RequestSpec
    records = []
    with httpx.Client(base_url=args.base_url, timeout=httpx.Timeout(None,connect=15)) as client:
        caps = client.get("/api/assistant/capabilities")
        caps.raise_for_status()
        cap = caps.json()
        scenario = cap["scenario"]
        baseline = {"scenario_id":scenario["scenario_id"],"arrival_utc":scenario["A_utc"],
            "illumination_model":"solar_disc","duration_hours":scenario["D_hours"],
            "hardware":scenario["device_heights_m"],"constraints":scenario["example_constraints"],
            **scenario["example_requirements"],"current_site_id":scenario["site_ids"][0]}
        start = baseline["arrival_utc"]
        questions = [
            f"So sánh Site01_P1 với Site04_P1 bắt đầu {start}, nhiệm vụ 72 giờ, chiếu sáng 80%, Earth LOS 80%, panel 1 m, antenna 2 m. Giải thích yêu cầu nào quyết định kết luận, ít số liệu thôi.",
            f"Compare Site01_P1 and Site04_P1 starting {start}, for 72 hours, requiring 80% mean sunlight and 80% Earth LOS, panel 1 m and antenna 2 m. Explain the decision in English, focusing on why rather than a metric list.",
        ]
        for number, text in enumerate(questions, 1):
            print(f"Planning narrative {number}: parsing", flush=True)
            record = {"case_id":f"NARRATIVE-{number}","question":text,"provider_requested":cap["provider"],
                      "model_requested":cap["primary_model"],"checked_utc":datetime.now(timezone.utc).isoformat()}
            parsed = client.post("/api/assistant/parse",json={"text":text,"baseline":baseline,
                "selected_site_ids":scenario["site_ids"],"require_explicit_start":True,"resolve_indeterminate":False})
            record["parse_status"] = parsed.status_code
            body = parsed.json()
            if parsed.is_success and body.get("status") == "READY":
                evaluated = client.post("/api/assistant/evaluate",json={"draft_id":body["draft_id"],
                    "spec_hash":body["spec_hash"],"baseline":baseline,"confirmed":True})
                record["evaluate_status"] = evaluated.status_code
                result = evaluated.json()
                record["result"] = result
                failures = []
                if not evaluated.is_success:
                    failures.append("evaluate_http_failed")
                else:
                    evidence = result["evidence"]
                    direct = PlanningAdapter().evaluate(RequestSpec.model_validate(body["spec"]),body["draft_id"],body["spec_hash"]).model_dump()
                    if evidence != direct:
                        failures.append("direct_engine_evidence_mismatch")
                    if result["explanation_mode"] != "llm_plan" or result.get("explanation_error"):
                        failures.append("natural_explanation_failed")
                    if not result["explanation"] or len(result["explanation"]) != 1:
                        failures.append("natural_prose_missing")
                    if any(k not in evidence["facts"] for k in result["explanation_fact_ids"]):
                        failures.append("invalid_fact_id")
                    if result.get("provider") != cap["provider"] or result.get("model") != cap["primary_model"]:
                        failures.append("provider_model_mismatch")
                record.update(passed=not failures, failures=failures)
            else:
                record.update(passed=False, parse_result=body, failures=["parse_not_ready"])
            records.append(record)
            print(f"Planning narrative {number}: {'PASS' if record['passed'] else 'FAIL'}", flush=True)
    report = {"mode":"strict_live_ui_planning","total":len(records),
              "passed":sum(r["passed"] for r in records),"cases":records,
              "quality_note":"Read the prose alongside engine evidence; automated checks do not prove semantic correctness."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Report: {args.output}")
    return 0 if all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
