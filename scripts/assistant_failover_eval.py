"""Inject a deterministic NIM 429 and verify real Gemini completes the grounded chat."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.assistant.chat_service import ChatService
    from app.assistant.config import get_assistant_settings
    from app.assistant.knowledge import ProjectKnowledge
    from app.assistant.provider import ResilientLLM

    settings = get_assistant_settings()
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        print("Failover evaluation not run: Gemini credential is missing.")
        return 2

    def rate_limit(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "60", "x-request-id": "synthetic-nim-429"})

    async def run():
        llm = ResilientLLM(settings.model_copy(update={"assistant_provider": "nvidia", "assistant_failover_enabled": True}),
                           transports={"nvidia": httpx.MockTransport(rate_limit)})
        knowledge = ProjectKnowledge(raw_root=settings.lunarsight_raw_dataset_path or None)
        result = await ChatService(llm, knowledge).respond(
            "What problem is LunarSight designed to solve?", [], {})
        source_checks = []
        for citation in result.get("citations", []):
            current = knowledge.source(citation["source_id"])
            source_checks.append(bool(current and current["source_hash"] == citation["source_hash"]
                                      and current["excerpt"] == citation["excerpt"]))
        return {"status": result.get("status"), "provider": result.get("provider"),
                "intent": result.get("intent"), "citation_count": len(source_checks),
                "citations_valid": all(source_checks), "trace": llm.events}

    report = asyncio.run(run())
    report["mode"] = "synthetic_nim_429_with_live_gemini"
    report["checked_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["pass"] = (report.get("status") == "completed" and report.get("provider") == "gemini"
                      and report.get("intent") == "knowledge" and report.get("citation_count", 0) > 0
                      and report.get("citations_valid") and any(event.get("provider") == "nvidia"
                          and event.get("outcome") == "error" and event.get("error_code") == "NVIDIA_RATE_LIMIT"
                          for event in report.get("trace", []))
                      and any(event.get("provider") == "gemini" and event.get("outcome") == "success"
                          for event in report.get("trace", [])))
    output = ROOT / "data/cache/assistant/live-failover-eval.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in
        ("mode", "status", "provider", "intent", "citation_count", "citations_valid", "pass")}, ensure_ascii=True))
    print(f"Failover report saved: {output}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
