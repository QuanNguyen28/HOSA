"""Opt-in live evaluation through the real FastAPI routes; no fixture LLM."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from app.assistant.config import get_assistant_settings
from app.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly allow paid OpenRouter requests")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/fixtures/assistant/prompts.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/cache/assistant/live-eval.json")
    args = parser.parse_args()
    settings = get_assistant_settings()
    if not args.live or not settings.assistant_enabled or not settings.openrouter_model or not settings.openrouter_api_key:
        print("No requests made. Use --live and configure ASSISTANT_ENABLED, OPENROUTER_MODEL, OPENROUTER_API_KEY in root .env.")
        return 2
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    request_template = json.loads((ROOT / "tests/fixtures/assistant/request.json").read_text(encoding="utf-8"))
    records = []
    with TestClient(app) as client:
        for case in cases[:max(0, min(args.limit, len(cases)))]:
            payload = {**request_template, "text": case["text"], **case.get("context", {})}
            response = client.post("/api/assistant/parse", json=payload)
            record = {"id": case["id"], "parse_http": response.status_code, "passed": False}
            if response.status_code == 200:
                parsed = response.json()
                record["parse_status"] = parsed["status"]
                record["issues"] = parsed["issues"]
                record["extracted_patch"] = parsed.get("patch")
                match = parsed["status"] == case["expected_parse_status"]
                if parsed["status"] == "READY" and match:
                    match = all(parsed["spec"][key] == expected for key, expected in case.get("expected_spec", {}).items())
                    if match:
                        evaluated = client.post("/api/assistant/evaluate", json={"draft_id": parsed["draft_id"],
                            "spec_hash": parsed["spec_hash"], "baseline": payload["baseline"], "confirmed": True})
                        record["evaluate_http"] = evaluated.status_code
                        if evaluated.status_code == 200:
                            result = evaluated.json()
                            record.update(result_status=result["evidence"]["status"], explanation_mode=result["explanation_mode"],
                                          timings_ms=result["timings_ms"], llm_calls=result["llm_calls"],
                                          token_usage=result["token_usage"], prompt_version=result["prompt_version"])
                            # A template fallback is functional resilience, not a successful explanation-model eval.
                            match = result["evidence"]["status"] == case["expected_result_status"] and result["explanation_mode"] == "llm_plan"
                        else:
                            record["error"] = evaluated.json().get("detail")
                            match = False
                elif parsed["status"] != "READY":
                    match = match and case.get("expected_issue") in parsed["issues"]
                record["passed"] = match
            else:
                record["error"] = response.json().get("detail")
            records.append(record)
    report = {"mode": "live", "model": settings.openrouter_model, "total": len(records),
              "passed": sum(r["passed"] for r in records), "cases": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Live evaluation: {report['passed']}/{report['total']}; report: {args.output}")
    return 0 if records and all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
