"""Live check of Mission planning chat against the backend (makes real LLM requests).

Usage: python scripts/mission_chat_live_check.py [--case-id ID] [--workers 3]

For every scenario: drive /assistant/parse+evaluate like the UI, then
  1. parity: replay the exact spec on the tab endpoints (/planning/compare or
     /planning/windows/search) and compare every candidate field;
     single-site explore also replays /lunar/point/analyses (Explore tab);
  2. number audit: every %, hour, minute and count in the prose must match a
     value derivable from the engine evidence;
  3. site audit: every catalog site named in the prose must be evaluated.
"""
import json, re, sys, time, concurrent.futures as cf
from pathlib import Path
import httpx

import argparse

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--api", default="http://127.0.0.1:8014/api", help="Running backend API base URL")
parser.add_argument("--cases", type=Path, default=ROOT / "tests/fixtures/assistant/mission_chat_live_cases.json")
parser.add_argument("--case-id", action="append", default=[], help="Run only this case ID; may be repeated")
parser.add_argument("--workers", type=int, default=3)
parser.add_argument("--output", type=Path, default=ROOT / "data/cache/assistant/mission-chat-live-check.json")
ARGS = parser.parse_args()
API = ARGS.api.rstrip("/")
OUT = ARGS.output
CASES = json.loads(ARGS.cases.read_text(encoding="utf-8"))
ONLY = set(ARGS.case_id)
WORKERS = ARGS.workers
TIMEOUT = httpx.Timeout(900, connect=10)
METRICS = ("total_sun_hours", "total_earth_los_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours")


def post(c, path, body):
    r = c.post(API + path, json=body, timeout=TIMEOUT)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:300]}


def chat(client, case, caps):
    sc = caps["scenario"]
    # Same working baseline the UI builds from the tabs' default mission settings
    # (frontend DEFAULT_MISSION): 20 m / 20 m, 80 % sunlight, 30-minute contact, no Earth LOS fraction.
    baseline = {"illumination_model": "solar_disc", "scenario_id": sc["scenario_id"], "arrival_utc": sc["A_utc"],
                "duration_hours": sc["D_hours"], "hardware": {"sun_panel": 20.0, "earth_antenna": 20.0},
                "constraints": {"max_darkness_hours": 12, "max_earth_blackout_hours": 6},
                "min_sunlit_fraction": 0.8, "min_earth_los_fraction": None,
                "contact_requirements": {"min_contact_minutes": 30, "setup_minutes": 5, "required_windows": 1,
                                         "first_contact_deadline_minutes": 120},
                "current_site_id": sc["site_ids"][0]}
    selected, history = list(sc["site_ids"]), []
    context = {"rank_by": "total_earth_los_hours", "search_from_utc": None, "search_until_utc": None}
    turns = []
    for turn in case["turns"]:
        answers = list(turn.get("answers", []))
        req = {"text": turn["text"], "resolve_indeterminate": True, "baseline": baseline,
               "require_explicit_start": len(history) == 0, "selected_site_ids": selected,
               "conversation_history": history[-8:], "clarifications": [], "planning_context": context}
        rec = {"text": turn["text"], "steps": [], "expect_issue": turn.get("expect_issue")}
        for _ in range(5):
            t = time.time(); code, d = post(client, "/assistant/parse", req)
            step = {"http": code, "s": round(time.time() - t, 1), "status": d.get("status"), "issues": d.get("issues"),
                    "questions": [q["question"] for q in d.get("questions", [])]}
            rec["steps"].append(step)
            if code != 200:
                step["error"] = d; break
            if d["status"] == "READY":
                t = time.time()
                code, ev = post(client, "/assistant/evaluate", {"draft_id": d["draft_id"], "spec_hash": d["spec_hash"],
                                                                "baseline": req["baseline"], "confirmed": True})
                rec["evaluate_http"], rec["evaluate_s"] = code, round(time.time() - t, 1)
                if code != 200:
                    rec["evaluate_error"] = ev; break
                rec["evidence"], rec["explanation"] = ev["evidence"], "\n".join(ev["explanation"])
                rec["explanation_mode"], rec["timings"] = ev["explanation_mode"], ev.get("timings_ms")
                spec = d["spec"]
                history.append({"text": req["text"], "clarifications": req["clarifications"], "outcome": "evaluated",
                                "summary": " ".join(ev["explanation"])[:1500]})
                selected = spec["site_ids"]
                baseline = {k: spec[k] for k in ("illumination_model", "scenario_id", "arrival_utc", "duration_hours", "hardware",
                                                  "constraints", "min_sunlit_fraction", "min_earth_los_fraction",
                                                  "contact_requirements")}
                baseline["current_site_id"] = spec["site_ids"][0] if len(spec["site_ids"]) == 1 else spec["current_site_id"]
                context = {k: spec[k] for k in ("rank_by", "search_from_utc", "search_until_utc")}
                break
            if not answers:  # UI keeps the request pending for any non-READY status
                break
            req = {**req, "clarifications": [*req["clarifications"], {"question": "\n".join(step["questions"]), "answer": answers.pop(0)}]}
        turns.append(rec)
    return turns


def parity(client, ev):
    s = ev["request"]
    q = {k: s[k] for k in ("illumination_model", "resolve_indeterminate", "scenario_id", "site_ids", "duration_hours",
                           "data_source", "arrival_utc", "constraints", "hardware", "current_site_id",
                           "min_sunlit_fraction", "min_earth_los_fraction", "rank_by", "contact_requirements")}
    if s.get("search_from_utc"):
        q.update(arrival_utc=s["search_from_utc"], until_utc=s["search_until_utc"], max_results=3, non_overlapping=True)
        if s.get("search_step_minutes"):
            q["start_step_minutes"] = s["search_step_minutes"]
        code, r = post(client, "/planning/windows/search", q)
    else:
        q["end_utc"] = s["end_utc"]
        code, r = post(client, "/planning/compare", q)
    if code != 200:
        return [f"tab endpoint HTTP {code}: {r}"]
    problems = []
    if r["status"] != ev["status"]:
        problems.append(f"status chat={ev['status']} tab={r['status']}")
    key = lambda c: (c["site_id"], c["start_utc"])
    a, b = {key(c): c for c in ev["candidates"]}, {key(c): c for c in r["candidates"]}
    if set(a) != set(b):
        problems.append(f"candidate set differs chat={sorted(a)} tab={sorted(b)}")
    for k in set(a) & set(b):
        for field in ("decision", "nominal_sampled_decision", "constraint_states", "soft_constraint_states"):
            if a[k].get(field) != b[k].get(field):
                problems.append(f"{k} {field} chat={a[k].get(field)} tab={b[k].get(field)}")
        for m in METRICS:
            x, y = a[k]["metrics"].get(m), b[k]["metrics"].get(m)
            if x != y:
                problems.append(f"{k} {m} chat={x} tab={y}")
    rec_tab = next((c for c in r["candidates"] if c["candidate_id"] == r.get("recommended_candidate_id")), None)
    rec_chat = next((c for c in ev["candidates"] if c["candidate_id"] == ev.get("recommended_candidate_id")), None)
    if (rec_tab and key(rec_tab)) != (rec_chat and key(rec_chat)):
        problems.append(f"recommendation chat={rec_chat and key(rec_chat)} tab={rec_tab and key(rec_tab)}")
    if s.get("search_from_utc") and r["coverage"].get("candidate_total") != ev["coverage"].get("candidate_total"):
        problems.append(f"coverage chat={ev['coverage']} tab={r['coverage']}")
    return problems


def explore_parity(client, ev):
    """Explore tab (/lunar/point/analyses) must give the same sun/Earth hours for a single-site check."""
    s, cand = ev["request"], ev["candidates"][0]
    body = {"site_id": s["site_ids"][0], "start_utc": s["arrival_utc"], "duration_hours": s["duration_hours"],
            "panel_height_m": s["hardware"]["sun_panel"], "antenna_height_m": s["hardware"]["earth_antenna"],
            "min_sunlit_fraction": s["min_sunlit_fraction"], "min_earth_los_fraction": s["min_earth_los_fraction"],
            "constraints": s["constraints"], "contact_requirements": s.get("contact_requirements"), "resolve_indeterminate": True}
    code, job = post(client, "/lunar/point/analyses", body)
    if code not in (200, 202):
        return [f"explore HTTP {code}: {job}"]
    for _ in range(600):
        st = client.get(f"{API}/lunar/point/analyses/{job['job_id']}", timeout=TIMEOUT).json()
        if st["status"] in ("succeeded", "failed"):
            break
        time.sleep(1)
    if st["status"] != "succeeded":
        return [f"explore job {st}"]
    res = client.get(f"{API}/lunar/point/analyses/{job['job_id']}/result", timeout=TIMEOUT).json()
    out = []
    for m in ("total_sun_hours", "total_earth_los_hours"):
        x, y = cand["metrics"].get(m), res["metrics_hours"].get(m)
        if x is None or y is None or any(abs(p - q) > 1e-6 for p, q in zip(x, y)):
            out.append(f"explore {m} chat={x} explore_tab={y}")
    if res.get("decision") != cand["decision"]:
        # With identical requirements the Explore tab must reach the same decision.
        out.append(f"explore decision chat={cand['decision']} explore_tab={res.get('decision')}")
    return out


NUM = re.compile(r"(?<![\d:/.,-])(\d+(?:[.,]\d+)?)(?![\d:/])\s*(%|phần trăm|percent|giờ|hours?|h\b|tiếng|phút|minutes?|mốc|start times?|thời điểm|lượt|ngày|days?|-hour|-day)", re.I)


def allowed(ev, sites_names):
    s, cov = ev["request"], ev["coverage"]
    dur = s["duration_hours"]
    pct, hrs, cnt, mins, days = {0, 100}, {dur}, set(), set(), {dur / 24}
    for f in ("min_sunlit_fraction", "min_earth_los_fraction"):
        if s.get(f) is not None:
            pct.add(round(s[f] * 100)); hrs.update({round(s[f] * dur, 1), round(s[f] * dur)})
    hrs.update({s["hardware"]["sun_panel"], s["hardware"]["earth_antenna"]})  # heights quoted as "20 m"
    for v in (s["constraints"] or {}).values():
        if v is not None: hrs.add(v)
    for c in ev["candidates"]:
        start_h = int(c["start_utc"][11:13]); hrs.update({start_h, start_h % 12 or 12})
        for m, (lo, hi) in c["metrics"].items():
            for v in (lo, hi):
                hrs.add(round(v, 1)); hrs.add(round(v));
                if m in ("total_sun_hours", "total_earth_los_hours") and dur:
                    pct.add(round(v / dur * 100))
            for f, mm in (("min_sunlit_fraction", "total_sun_hours"), ("min_earth_los_fraction", "total_earth_los_hours")):
                if m == mm and s.get(f) is not None:
                    hrs.update({round(s[f] * dur - lo, 1), round(s[f] * dur - hi, 1),
                                round(s[f] * dur - lo), round(s[f] * dur - hi)})
                    pct.add(round(s[f] * 100 - lo / dur * 100)); pct.add(round(s[f] * 100 - hi / dur * 100))
    # Differences between evaluated candidates ("about 1 hour more").
    for m in ("total_sun_hours", "total_earth_los_hours"):
        values = [c["metrics"][m][0] for c in ev["candidates"] if m in c["metrics"]]
        for a in values:
            for b in values:
                if a > b:
                    hrs.update({round(a - b, 1), round(a - b)})
                    if dur:
                        pct.add(round((a - b) / dur * 100))
    if s.get("search_from_utc"):
        step = s.get("search_step_minutes") or 15
        mins.update({step}); hrs.update({step / 60})
        for v in cov.values():
            if isinstance(v, int): cnt.add(v)
        cnt.add(len(ev["candidates"]))
        span = (int(s["search_until_utc"][8:10]) - int(s["search_from_utc"][8:10]))
        days.add(span)
    contact = s.get("contact_requirements") or {}
    for v in contact.values():
        if isinstance(v, (int, float)):
            mins.add(v); cnt.add(v); hrs.add(round(v / 60, 1))
    def flat(x):
        if isinstance(x, dict):
            for v in x.values(): yield from flat(v)
        elif isinstance(x, list):
            for v in x: yield from flat(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            yield x
    for c in ev["candidates"]:
        for v in flat((c.get("contact_analysis") or {}).get("metrics")):
            mins.update({round(v), round(v, 1)}); hrs.update({round(v, 1), round(v / 60, 1)}); cnt.add(v)
    cnt.update({len(s["site_ids"]), 1, 2, 3})
    return pct, hrs, cnt, mins, days


def audit(ev, text, catalog):
    pct, hrs, cnt, mins, days = allowed(ev, catalog)
    issues = []
    for m in NUM.finditer(text):
        v = float(m[1].replace(",", ".")); unit = m[2].lower()
        if unit in ("%", "phần trăm", "percent"):
            ok = any(abs(v - p) <= 1 for p in pct)
        elif unit in ("giờ", "hour", "hours", "h", "tiếng", "-hour"):
            ok = any(abs(v - h) <= 0.15 for h in hrs)
        elif unit in ("phút", "minute", "minutes"):
            ok = any(abs(v - m) <= 0.5 for m in mins)
        elif unit in ("ngày", "day", "days", "-day"):
            ok = True  # calendar day numbers ("ngày 24") are dates, not quantities
        else:
            ok = v in cnt
        if not ok:
            issues.append(f"number '{m[0]}' not in engine evidence")
    evaluated = {c["site_id"] for c in ev["candidates"]} | set(ev["request"]["site_ids"])
    low = text.lower()
    for sid, name in catalog.items():
        if sid in evaluated:
            continue
        if re.search(r"(?<![\w-])" + re.escape(name.lower()) + r"(?![\w-])", low) and not any(
                name.lower() in catalog.get(e, e).lower() for e in evaluated):
            issues.append(f"mentions non-evaluated site '{name}'")
    status = ev["status"]
    if status != "FEASIBLE":
        for m in re.finditer(r"\b(is feasible|là khả thi|được khuyến nghị|recommended plan is|meets all (the )?requirements)\b", low):
            before = low[max(0, m.start() - 40):m.start()]
            if not re.search(r"\b(chưa|không|not|no|cannot|can't|isn't|never|neither|nor)\b", before):
                issues.append(f"claims feasibility ('{m[0]}') but engine status is {status}")
    if re.search(r"min_\w+_fraction|total_\w+_hours|NO_FEASIBLE|INSUFFICIENT_DATA|\d{4}-\d\d-\d\dT", text):
        issues.append("internal identifier or raw timestamp in prose")
    return issues


def run(case):
    client = httpx.Client()
    caps = client.get(API + "/assistant/capabilities", timeout=60).json()
    turns = chat(client, case, caps)
    catalog = CATALOG
    for t in turns:
        if t.get("expect_issue"):
            issues = t["steps"][-1].get("issues") if t["steps"] else None
            t["audit"] = [] if issues == [t["expect_issue"]] else [f"expected {t['expect_issue']}, got {issues}"]
            continue
        ev = t.get("evidence")
        if not ev:
            continue
        t["parity"] = parity(client, ev)
        if len(ev["request"]["site_ids"]) == 1 and not ev["request"].get("search_from_utc") and case.get("explore_parity", True):
            t["explore_parity"] = explore_parity(client, ev)
        t["audit"] = audit(ev, t["explanation"], catalog)
    return {"id": case["id"], "turns": turns}


sys.path.insert(0, str(ROOT / "backend"))  # catalog display names
from app.mission.targets import compare_sites  # noqa: E402
CATALOG = {k: v["name"] for k, v in compare_sites().items()}

cases = [c for c in CASES if not ONLY or c["id"] in ONLY]
results = {}
with cf.ThreadPoolExecutor(WORKERS) as pool:
    futs = {pool.submit(run, c): c["id"] for c in cases}
    for f in cf.as_completed(futs):
        try:
            results[futs[f]] = f.result()
        except Exception as e:
            import traceback; results[futs[f]] = {"id": futs[f], "crash": traceback.format_exc()[-800:]}
        print("done", futs[f], flush=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps([results[c["id"]] for c in cases if c["id"] in results], ensure_ascii=False, indent=1), encoding="utf-8")


bad = 0
for case in results.values():
    for index, turn in enumerate(case.get("turns", [])):
        problems = [*turn.get("parity", []), *[p for p in turn.get("explore_parity", []) if not p.startswith("(info)")],
                    *turn.get("audit", [])]
        if case.get("crash") or problems:
            bad += 1
            print(f"FLAG {case['id']}#{index}: {problems or case.get('crash')}")
    if case.get("crash"):
        bad += 1
        print(f"CRASH {case['id']}: {case['crash']}")
print(f"report: {OUT} · flagged turns: {bad}")
sys.exit(1 if bad else 0)
