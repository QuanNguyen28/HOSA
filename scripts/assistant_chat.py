"""Interactive terminal demo over the same service as /api/assistant."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"backend"))

from pydantic import ValidationError
from app.assistant.config import AssistantSettings, get_assistant_settings
from app.assistant.models import (Baseline, ClarificationTurn, ConversationTurn,
    EvaluateRequest, ParseRequest, PlanningContext, SiteCoordinates)
from app.assistant.sites import canonical_site_id, chat_site_ids, named_sites, resolve_coordinates, site_info
from app.assistant.provider import AssistantError, OpenRouterLLM
from app.assistant.service import AssistantService
from app.assistant.store import DraftStore
from scripts.demo_provider import DEMO_PROMPT, DemoLLM

QUIT = {"/quit", "/exit", "exit", "quit", "thoát"}
NEW = {"/new", "/reset"}


def configure_console_utf8():
    """Keep Windows keyboard, native output and redirected streams on UTF-8."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


class ChatSession:
    """Client-owned working state; confirmed evaluations become the next turn's context."""

    def __init__(self, context):
        self.initial = deepcopy(context)
        self.reset()

    def reset(self):
        self.baseline = Baseline.model_validate(self.initial["baseline"])
        self.selected = list(self.initial.get("selected_site_ids") or [self.baseline.current_site_id])
        self.planning = PlanningContext.model_validate(self.initial.get("planning_context", {}))
        self.history = []
        self.text = None
        self.answers = []

    def finish(self, outcome, summary=""):
        if self.text:
            self.history.append(ConversationTurn(text=self.text, clarifications=self.answers[:],
                                                 outcome=outcome, summary=summary))
            self.history = self.history[-8:]
        self.text, self.answers = None, []

    def request(self):
        return ParseRequest(text=self.text, baseline=self.baseline,
            selected_site_ids=self.selected, clarifications=self.answers,
            conversation_history=self.history, planning_context=self.planning)

    def remember(self, spec):
        updates = {"illumination_model": spec.illumination_model, "arrival_utc": spec.arrival_utc, "constraints": spec.constraints,
                   "min_sunlit_fraction": spec.min_sunlit_fraction, "min_earth_los_fraction": spec.min_earth_los_fraction}
        if len(spec.site_ids) == 1:
            updates["current_site_id"] = spec.site_ids[0]
        self.baseline = self.baseline.model_copy(update=updates)
        self.selected = list(spec.site_ids)
        self.planning = PlanningContext(**{key: getattr(spec, key)
            for key in PlanningContext.model_fields})

    def command(self, text, say):
        if text == "/reset":
            self.reset()
            say("Đã xóa lịch sử và khôi phục kế hoạch ban đầu.")
        elif text == "/new":
            self.finish("abandoned")
            say("Đã bắt đầu yêu cầu mới; giữ kế hoạch làm việc, vùng chọn và lịch sử.")
        elif text == "/baseline":
            say("Kế hoạch làm việc hiện tại (ngữ cảnh cho lượt sau):")
            say(json.dumps({**self.baseline.model_dump(), "selected_site_ids": self.selected,
                            "planning_context": self.planning.model_dump()}, ensure_ascii=False, indent=2))
        elif text == "/sites":
            say(json.dumps({"selected_site_ids": self.selected,
                            "available_sites": sorted(site_info(site)["label"] for site in chat_site_ids())},
                           ensure_ascii=False, indent=2))
        elif text.startswith("/sites "):
            choice = text.partition(" ")[2].strip()
            try:
                if choice.startswith("coords "):
                    lat, lon = map(float, choice[len("coords "):].replace(",", " ").split())
                    sites = [resolve_coordinates(SiteCoordinates(lat_deg=lat, lon_e_deg=lon))]
                else:
                    # Same 27 sites as the Explore/Compare/Best dates tabs, by name, ID or code.
                    sites = named_sites(choice) or [canonical_site_id(part.strip()) for part in choice.split(",")]
                if not sites or len(sites) > 2 or len(set(sites)) != len(sites) or any(
                        site not in chat_site_ids() for site in sites):
                    raise ValueError("Unsupported sites")
            except (ValueError, AssistantError):
                say("Chọn tối đa hai điểm trong 27 điểm của danh sách Khám phá, ví dụ /sites Shackleton Rim "
                    "hoặc /sites Connecting Ridge, Shackleton Rim; hoặc /sites coords <lat_deg> <lon_e_deg> "
                    "(chỉ nhận đúng tọa độ của một trong 27 điểm, sai số 1 m).")
                return True
            self.selected = sites
            if len(sites) == 1:
                self.baseline = self.baseline.model_copy(update={"current_site_id": sites[0]})
            say("Vùng chọn cho lượt sau: " + ", ".join(sites))
        else:
            return False
        return True


def run_console(service, initial_context, ask=input, say=print, demo=False, max_clarifications=3):
    session = ChatSession(initial_context)
    say("HOSA | " + ("DEMO GIẢ LẬP LLM — không gọi OpenRouter." if demo else "OpenRouter thật — đọc model/key từ .env."))
    say(f"Kế hoạch làm việc: {session.baseline.arrival_utc}; {session.baseline.duration_hours:g} giờ; {session.baseline.current_site_id}.")
    say("Dữ liệu demo: 14/11–trước 28/11/2026 UTC, lưới 15 phút; nhiệm vụ 72 giờ.")
    say("Lệnh: /quit, /new, /reset, /baseline, /sites, /sites Shackleton Rim, /sites coords <lat> <lon_e>.")
    say("Kế hoạch đã xác nhận đánh giá sẽ được nhớ cho lượt sau; /reset khôi phục phiên ban đầu.")
    if demo:
        say("Nhấn Enter để dùng câu mẫu: " + DEMO_PROMPT)

    def read(prompt, confirmation=False):
        while True:
            answer = ask(prompt).strip()
            if answer.lower() in QUIT:
                raise EOFError
            if confirmation and answer not in {"/baseline", "/sites"} and answer.startswith("/"):
                session.command(answer, say)
                return None  # Any mutation invalidates the displayed draft.
            if session.command(answer, say):
                if answer in NEW:
                    return None
                continue
            return answer

    try:
        while True:
            text = read("\nBạn> ")
            if text is None:
                continue
            if not text:
                if demo and session.text is None:
                    text = DEMO_PROMPT
                else:
                    continue
            if session.text is None:
                session.text = text
            else:
                if len(session.answers) >= 6:
                    say("Đã đạt 6 câu bổ sung. Dùng /new để bắt đầu yêu cầu khác.")
                    continue
                session.answers.append(ClarificationTurn(question="Bổ sung cho yêu cầu đang chờ", answer=text))
            calls = 0
            for round_index in range(max_clarifications + 1):
                try:
                    say("Đang hiểu yêu cầu...")
                    parsed = asyncio.run(service.parse(session.request()))
                    calls += parsed.llm_calls
                    if parsed.status == "READY":
                        spec = parsed.spec
                        say("Kế hoạch đã hiểu:")
                        say(f"  Bắt đầu: {spec.arrival_utc}; kết thúc: {spec.end_utc}")
                        if spec.search_from_utc:
                            say(f"  Được tìm ngày từ {spec.search_from_utc} đến trước {spec.search_until_utc}")
                        say("  Điểm: " + ", ".join(spec.site_ids))
                        say(f"  Yêu cầu cứng: có nắng ≥ {spec.min_sunlit_fraction*100:g}%; có Earth LOS ≥ {spec.min_earth_los_fraction*100:g}%.")
                        for name, label in (("max_darkness_hours", "tối liên tục"), ("max_earth_blackout_hours", "mất Earth LOS liên tục")):
                            limit = getattr(spec.constraints, name)
                            if limit is not None:
                                say(f"  Mong muốn mềm: {label} ≤ {limit:g} giờ; vượt không làm loại phương án.")
                        say("  Phần cứng giữ nguyên; nhiệm vụ 72 giờ.")
                        answer = read("Chạy đánh giá và nhớ kế hoạch cho lượt sau? [y/N] ", confirmation=True)
                        if answer is None:
                            say("Đã hủy bản nháp; chưa chạy bộ tính. Nhập yêu cầu để tạo bản nháp mới.")
                            break
                        if answer.lower() not in {"y", "yes", "có", "c"}:
                            session.finish("cancelled")
                            say("Đã hủy; chưa chạy bộ tính hoặc lượt giải thích; kế hoạch làm việc giữ nguyên.")
                            break
                        say("Đang tính và giải thích...")
                        result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,
                            spec_hash=parsed.spec_hash, baseline=session.baseline, confirmed=True)))
                        calls += result.llm_calls - 1
                        say("Kết quả: " + result.evidence.status)
                        for line in result.explanation:
                            say("  " + line)
                        say(f"Giải thích: {result.explanation_mode}; lượt xử lý LLM được ghi nhận: {calls}" +
                            (" (giả lập; API thật = 0)." if demo else "."))
                        session.remember(spec)
                        summary = json.dumps({"arrival_utc": spec.arrival_utc, "site_ids": spec.site_ids,
                            "status": result.evidence.status, "run_id": result.evidence.run_id}, ensure_ascii=False)
                        session.finish("evaluated", summary)
                        say("Đã nhớ kế hoạch làm việc cho lượt sau; đây không phải phê duyệt nhiệm vụ.")
                        break
                    say("Cần làm rõ:" if parsed.status == "NEEDS_INPUT" else "Yêu cầu chưa được hỗ trợ:")
                    for question in parsed.questions:
                        say("  " + question.question)
                    if parsed.status == "UNSUPPORTED_REQUIREMENT":
                        session.finish("abandoned", ", ".join(parsed.issues))
                        say("Nhập yêu cầu mới hoặc /quit.")
                        break
                    if round_index == max_clarifications or len(session.answers) >= 6:
                        say("Đã đạt giới hạn hỏi lại trong lượt này. Yêu cầu vẫn được giữ; bổ sung ở lượt sau hoặc /new.")
                        break
                    answer = read("Bạn bổ sung> ")
                    if answer is None:
                        break
                    if not answer:
                        say("Yêu cầu vẫn được giữ; hãy bổ sung ở lượt sau hoặc /new.")
                        break
                    session.answers.append(ClarificationTurn(question=" ".join(q.question for q in parsed.questions) or "Bổ sung yêu cầu",
                                                             answer=answer))
                except AssistantError as error:
                    say("Dừng yêu cầu: " + error.code + ". Không tự gọi lại model.")
                    say("Yêu cầu vẫn được giữ để bổ sung; /new bắt đầu yêu cầu khác.")
                    if error.code == "OPENROUTER_TIMEOUT":
                        say("Endpoint vượt thời gian cho phép. Có thể dùng --demo để trình diễn không cần API.")
                    break
                except (ValidationError, OSError, ValueError) as error:
                    say("Dữ liệu chưa hợp lệ: " + type(error).__name__ + ". Hãy bổ sung hoặc /new.")
                    break
    except (EOFError, KeyboardInterrupt):
        say("\nĐã kết thúc.")
        return 0


def run_remote_console(base_url="http://127.0.0.1:8000/api/assistant", session_id=None,
                      new_session=False, ask=input, say=print, confirm=input):
    """Thin terminal client for the same persistent session/run API as the web UI."""
    base_url=base_url.rstrip("/")
    cache_path=ROOT/"data/cache/assistant/terminal-session.txt"

    def api(method,path,**kwargs):
        response=requests.request(method,base_url+path,timeout=(10,None),**kwargs)
        if "application/json" in response.headers.get("content-type","").lower():
            response.encoding="utf-8"
        return response

    try:
        capabilities=api("GET","/capabilities")
        if not capabilities.ok:
            say("Assistant API chưa sẵn sàng: "+str(capabilities.status_code))
            return 2
        config=capabilities.json()
        if not config.get("assistant_enabled") or not config.get("provider_configured"):
            say("LLM chưa sẵn sàng. Kiểm tra ASSISTANT_ENABLED và cấu hình provider trong backend .env.")
            return 2
        if new_session:
            session_id=None
        if not new_session and not session_id and cache_path.is_file():
            session_id=cache_path.read_text(encoding="utf-8").strip() or None
        if session_id:
            response=api("GET",f"/sessions/{session_id}")
            if not response.ok:
                session_id=None
        if not session_id:
            response=api("POST","/sessions")
            if not response.ok:
                say("Không thể tạo phiên: "+str(response.status_code))
                return 2
            session=response.json()
            session_id=session["id"]
            cache_path.parent.mkdir(parents=True,exist_ok=True)
            cache_path.write_text(session_id,encoding="utf-8")
        else:
            session=response.json()
        say(f"HOSA assistant · {config['provider']} / {config['primary_model']}")
        say("Kiểm tra dấu: Mặt Trăng - chiếu sáng - Trái Đất - dữ liệu.")
        say(f"Phiên: {session_id}. Lệnh: /new, /unicode, /result, /apply <candidate_id>, /help, /quit")
        say("Ctrl+C khi đang chờ để hủy lượt. Số liệu chi tiết chỉ hiện khi nhập /result.")
        last_engine_result=next(((run.get("result") or {}).get("result") for run in reversed(session.get("runs",[]))
                                 if (run.get("result") or {}).get("result")),None)
        for message in session.get("messages",[]):
            say(("Bạn> " if message["role"]=="user" else "HOSA> ")+message["content"])

        def apply_candidate(candidate_id):
            current=api("GET",f"/sessions/{session_id}")
            if not current.ok:
                say("Không tải được trạng thái phiên.")
                return
            state=current.json()
            match=None
            for run in reversed(state.get("runs",[])):
                result=(run.get("result") or {}).get("result") or {}
                if result.get("apply_allowed"):
                    candidate=next((item for item in result.get("candidates",[])
                                    if item.get("candidate_id")==candidate_id and item.get("decision")=="PASS"),None)
                    if candidate:
                        match=(run,candidate)
                        break
            if not match:
                say("Không tìm thấy candidate PASS có thể áp dụng trong phiên này.")
                return
            if confirm(f"Áp dụng candidate {candidate_id}? [y/N] ").strip().lower() not in {"y","yes","có","c"}:
                say("Đã hủy; applied plan chưa đổi.")
                return
            payload={"run_id":match[0]["id"],"expected_applied_state":state.get("applied_state",{}),
                     "candidate":{"candidate_id":candidate_id}}
            result=api("POST",f"/sessions/{session_id}/apply",json=payload)
            if result.ok:
                say("Đã áp dụng candidate PASS và cập nhật applied plan.")
            else:
                say("Áp dụng bị từ chối: "+str(result.json().get("detail",{}).get("code","APPLY_FAILED")))

        while True:
            text=ask("\nBạn> ").strip()
            if text.lower() in QUIT:
                return 0
            if text=="/help":
                say("Nhập câu hỏi; /new tạo phiên mới; /unicode thử dấu tại máy, không gọi LLM; /result xem số liệu đã tính; /apply <candidate_id> yêu cầu xác nhận; /quit thoát.")
                continue
            if text=="/unicode":
                sample=ask("Gõ thử một câu tiếng Việt (không gửi tới LLM)> ")
                say("Bạn vừa nhập: "+sample)
                continue
            if text=="/result":
                say(json.dumps(last_engine_result,ensure_ascii=False,indent=2) if last_engine_result else "Phiên này chưa có kết quả tính toán.")
                continue
            if text=="/new":
                response=api("POST","/sessions")
                if not response.ok:
                    say("Không tạo được phiên mới: "+str(response.status_code))
                    continue
                session_id=response.json()["id"]
                last_engine_result=None
                cache_path.parent.mkdir(parents=True,exist_ok=True)
                cache_path.write_text(session_id,encoding="utf-8")
                say("Đã tạo phiên mới: "+session_id)
                continue
            if text.startswith("/apply "):
                apply_candidate(text.partition(" ")[2].strip())
                continue
            if not text:
                continue
            response=api("POST",f"/sessions/{session_id}/messages",headers={"Idempotency-Key":str(uuid.uuid4())},
                         json={"text":text})
            if response.status_code!=202:
                say("Yêu cầu chưa được nhận: "+str(response.json().get("detail",{}).get("code","MESSAGE_REJECTED")))
                continue
            run_id=response.json()["id"]
            previous_stage=None
            try:
                while True:
                    current=api("GET",f"/runs/{run_id}")
                    if not current.ok:
                        say("Không đọc được tiến độ run: "+str(current.status_code))
                        break
                    run=current.json()
                    if run.get("stage")!=previous_stage:
                        previous_stage=run.get("stage")
                        say("Đang xử lý: "+str(previous_stage))
                    if run["status"] in {"completed","partial","needs_input"} and run.get("result"):
                        result=run["result"]
                        say("\nHOSA> "+result.get("answer",""))
                        if result.get("provider"):
                            say("Model thực tế: "+str(result.get("model") or result["provider"]))
                        for citation in result.get("citations",[]):
                            say(f"Nguồn: {citation['path']} [{citation['source_id']}]")
                        if result.get("result"):
                            last_engine_result=result["result"]
                            say("Kết quả backend đã lưu. Nhập /result nếu muốn xem số liệu chi tiết.")
                        if run["status"]=="partial":
                            say("Kết quả tính đã lưu; phần giải thích LLM chưa hoàn tất.")
                        break
                    if run["status"] in {"failed","cancelled","interrupted"}:
                        say("Run kết thúc: "+str(run.get("error_code") or run["status"]))
                        break
                    import time
                    time.sleep(1.5)
            except KeyboardInterrupt:
                try:
                    api("POST",f"/runs/{run_id}/cancel")
                except requests.RequestException:
                    pass
                say("Đã gửi yêu cầu hủy; kết quả engine chưa được áp dụng.")
    except requests.RequestException as error:
        say("Không kết nối được HOSA API: "+type(error).__name__)
        return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8000/api/assistant")
    parser.add_argument("--session",help="Resume this server-side session ID")
    parser.add_argument("--new",action="store_true",help="Start a fresh persistent session")
    args = parser.parse_args(argv)
    return run_remote_console(args.base_url,args.session,args.new)


if __name__ == "__main__":
    configure_console_utf8()
    raise SystemExit(main())
