"""Strict, real-provider evaluation through HOSA's persistent chat API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


def normalize(text: str) -> str:
    value=unicodedata.normalize("NFD",text.casefold())
    return "".join(char for char in value if unicodedata.category(char)!="Mn")


def check_case(case: dict, run: dict, source_reader) -> list[str]:
    failures=[]
    result=run.get("result") or {}
    if run.get("status") not in {"completed","partial","needs_input"}:
        return ["run_status:"+str(run.get("error_code") or run.get("status"))]
    if result.get("provider")!=case.get("provider_expected"):
        failures.append("provider_mismatch")
    if result.get("status")!=case.get("expected_run_status","completed"):
        failures.append("run_status_mismatch")
    expected_intents=case.get("expected_intents") or ([case["expected_intent"]] if case.get("expected_intent") else [])
    if expected_intents and result.get("intent") not in expected_intents:
        failures.append("intent_mismatch")
    answer=normalize(result.get("answer",""))
    for phrase in case.get("required_terms",[]):
        if normalize(phrase) not in answer:
            failures.append("missing_required_term:"+phrase)
    for phrase in case.get("forbidden_terms",[]):
        if normalize(phrase) in answer:
            failures.append("forbidden_term:"+phrase)
    citations=result.get("citations") or []
    if case.get("require_citation",False) and not citations:
        failures.append("citation_missing")
    paths=[normalize(item.get("path","")) for item in citations]
    for path_fragment in case.get("required_source_paths",[]):
        if not any(normalize(path_fragment) in path for path in paths):
            failures.append("required_source_missing:"+path_fragment)
    for citation in citations:
        source=source_reader(citation.get("source_id",""))
        if source is None or source.get("source_hash")!=citation.get("source_hash") or source.get("excerpt")!=citation.get("excerpt"):
            failures.append("citation_invalid:"+str(citation.get("source_id","")))
    engine=result.get("result") or {}
    if case.get("require_engine_evidence") or result.get("evidence_claims"):
        from app.assistant.chat_models import EvidenceClaim
        from app.assistant.interpretation import claim_issues
        claims=[EvidenceClaim.model_validate(item) for item in result.get("evidence_claims",[])]
        failures.extend(claim_issues(claims,result.get("evidence") or {},required=True))
        if engine and (result.get("evidence") or {}).get("result_id")!=engine.get("result_id"):
            failures.append("evidence_result_mismatch")
    expected=case.get("expected_engine",{})
    for key,value in expected.items():
        if engine.get(key)!=value:
            failures.append("engine_mismatch:"+key)
    trace=result.get("trace") or []
    successes=[item for item in trace if item.get("provider")==case.get("provider_expected") and item.get("outcome")=="success"]
    if not successes:
        failures.append("strict_provider_trace_missing")
    elif case.get("expected_model") and not any(item.get("model")==case["expected_model"] for item in successes):
        failures.append("provider_model_mismatch")
    return failures


def execute_turn(client, session_id: str, case: dict, provider: str, model: str,
                 case_id: str, turn_number: int) -> dict:
    started=time.monotonic()
    response=client.post(f"/api/assistant/sessions/{session_id}/messages",
        headers={"Idempotency-Key":str(uuid4())},json={"text":case["text"]})
    if response.status_code!=202:
        return {"turn":turn_number,"passed":False,"error_code":(response.json().get("detail") or {}).get("code","MESSAGE_REJECTED"),
                "http_status":response.status_code}
    run_id=response.json()["id"]
    last_progress_log=time.monotonic()
    while True:
        current=client.get(f"/api/assistant/runs/{run_id}")
        if not current.is_success:
            return {"turn":turn_number,"run_id":run_id,"passed":False,"error_code":"RUN_READ_FAILED",
                    "http_status":current.status_code}
        run=current.json()
        if run["status"] in {"completed","partial","needs_input","failed","cancelled","interrupted"}:
            source_cache={}
            def read_source(source_id):
                if source_id not in source_cache:
                    item=client.get(f"/api/assistant/sources/{source_id}") if source_id else None
                    source_cache[source_id]=item.json() if item is not None and item.is_success else None
                return source_cache[source_id]
            failures=check_case({**case,"provider_expected":provider,"expected_model":model},run,read_source)
            return {"turn":turn_number,"run_id":run_id,"passed":not failures,"run_status":run["status"],
                    "error_code":run.get("error_code"),"failures":failures or None,"latency_s":round(time.monotonic()-started,2),
                    "result":run.get("result"),"finished_utc":utc_now()}
        now=time.monotonic()
        if now-last_progress_log>=30:
            last_progress_log=now
            print(f"{case_id} turn {turn_number}: still {run.get('status')}/{run.get('stage')} (no application generation deadline)",flush=True)
        time.sleep(.5)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true",help="Make real paid requests using local .env credentials")
    parser.add_argument("--provider",choices=["nvidia","gemini"],required=True)
    parser.add_argument("--cases",type=Path,default=ROOT/"tests/fixtures/assistant/llm_smoke_cases.json")
    parser.add_argument("--limit",type=int,default=0,help="Limit cases; 0 runs every case in the file")
    parser.add_argument("--case-id",action="append",default=[],help="Run only this case ID; may be repeated")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if not args.live:
        print("No API request made. Pass --live to explicitly run real-provider evaluation.")
        return 2
    if args.limit<0:
        parser.error("--limit must be 0 or positive")

    # Provider selection and failover policy are process-local for this strict run.
    os.environ["ASSISTANT_ENABLED"]="true"
    os.environ["ASSISTANT_PROVIDER"]=args.provider
    os.environ["ASSISTANT_FAILOVER_ENABLED"]="false"
    os.environ["ASSISTANT_STREAMING"]="true"
    os.environ["ASSISTANT_DATABASE_PATH"]=str(ROOT/"data/cache/assistant"/f"eval-{args.provider}.sqlite3")
    from app.assistant.config import get_assistant_settings
    get_assistant_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app

    settings=get_assistant_settings()
    secret=(settings.nvidia_api_key if args.provider=="nvidia" else settings.gemini_api_key)
    if not secret or not secret.get_secret_value().strip():
        print("No API request made: selected provider credential is not configured.")
        return 2
    cases=json.loads(args.cases.read_text(encoding="utf-8"))
    if not isinstance(cases,list) or not cases:
        parser.error("--cases must contain a non-empty JSON array")
    if args.case_id:
        by_id={case.get("id"):case for case in cases}
        missing=[identifier for identifier in args.case_id if identifier not in by_id]
        if missing:
            parser.error("unknown case ID(s): "+", ".join(missing))
        selected=[by_id[identifier] for identifier in args.case_id]
    else:
        selected=cases[:args.limit] if args.limit else cases
    timestamp=utc_now()
    records=[]

    with TestClient(app) as client:
        capabilities=client.get("/api/assistant/capabilities")
        if not capabilities.is_success:
            print("Provider preflight failed at capabilities: HTTP "+str(capabilities.status_code))
            return 1
        cap=capabilities.json()
        if cap.get("provider")!=args.provider or not cap.get("provider_configured"):
            print("Provider preflight failed: selected provider is not ready in the app.")
            return 1
        for case in selected:
            print(f"Starting {case['id']} ({args.provider})",flush=True)
            record={"case_id":case["id"],"provider_requested":args.provider,"model_requested":cap.get("primary_model"),
                    "started_utc":utc_now(),"case_hash":hashlib.sha256(json.dumps(case,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
            session_response=client.post("/api/assistant/sessions")
            if not session_response.is_success:
                record.update(passed=False,error_code="SESSION_CREATE_FAILED",http_status=session_response.status_code)
                records.append(record); continue
            session_id=session_response.json()["id"]
            turns=case.get("turns") or [{key:value for key,value in case.items() if key!="turns"}]
            turn_results=[]
            for index,turn in enumerate(turns,1):
                if isinstance(turn,str):
                    turn={"text":turn}
                turn_case={**case,**turn}
                turn_results.append(execute_turn(client,session_id,turn_case,args.provider,
                                                  record["model_requested"],case["id"],index))
                print(f"{case['id']} turn {index}: {'PASS' if turn_results[-1].get('passed') else 'FAIL'}",flush=True)
            record["turns"]=turn_results
            record["total_turns"]=len(turn_results)
            record["passed"]=bool(turn_results) and all(item.get("passed") for item in turn_results)
            record["finished_utc"]=utc_now()
            if len(turn_results)==1:
                record["result"]=turn_results[0].get("result")
                record["run_status"]=turn_results[0].get("run_status")
                record["error_code"]=turn_results[0].get("error_code")
                record["failures"]=turn_results[0].get("failures")
            if not record["passed"]:
                record["failures"]=[f"turn_{item['turn']}:"+str(item.get("error_code") or ";".join(item.get("failures") or []))
                                    for item in turn_results if not item.get("passed")]
            records.append(record)
            print(f"{case['id']}: {'PASS' if record.get('passed') else 'FAIL'}",flush=True)

    all_results=[turn.get("result") for case in records for turn in case.get("turns",[]) if turn.get("result")]
    latencies=sorted(item["latency_ms"] for result in all_results for item in
                     ((result.get("trace") or [])) if isinstance(item.get("latency_ms"),(int,float)))
    def percentile(values, p):
        return values[min(len(values)-1,max(0,round((len(values)-1)*p)))] if values else None
    usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    for result in all_results:
        for item in ((result.get("trace") or [])):
            for key in usage:
                usage[key]+=int((item.get("usage") or {}).get(key,0))
    report={"mode":"strict_live","provider_requested":args.provider,
            "model_requested":cap.get("primary_model"),"started_utc":timestamp,"finished_utc":utc_now(),
            "capabilities":{"streaming":cap.get("streaming"),"generation_deadline":cap.get("generation_deadline")},
            "metrics":{"provider_call_latency_ms_p50":percentile(latencies,.50),
                       "provider_call_latency_ms_p95":percentile(latencies,.95),"token_usage":usage},
            "total":len(records),"passed":sum(bool(item.get("passed")) for item in records),
            "failed":sum(not bool(item.get("passed")) for item in records),"cases":records}
    output=args.output or ROOT/"data/cache/assistant"/f"live-eval-{args.provider}.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(f"Strict live result: {report['passed']}/{report['total']} | provider={args.provider} | report={output}")
    return 0 if records and all(item.get("passed") for item in records) else 1


if __name__=="__main__":
    raise SystemExit(main())
