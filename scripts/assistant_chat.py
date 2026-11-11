"""Interactive terminal demo over the same service as /api/assistant."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"backend"))

from pydantic import ValidationError
from app.assistant.config import AssistantSettings, get_assistant_settings
from app.assistant.models import (Baseline, ClarificationTurn, ConversationTurn,
    EvaluateRequest, ParseRequest, PlanningContext, SiteCoordinates)
from app.assistant.sites import available_sites, resolve_coordinates
from app.assistant.provider import AssistantError, OpenRouterLLM
from app.assistant.service import AssistantService
from app.assistant.store import DraftStore
from scripts.demo_provider import DEMO_PROMPT, DemoLLM

QUIT = {"/quit", "/exit", "exit", "quit", "thoát"}
NEW = {"/new", "/reset"}


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
        updates = {"arrival_utc": spec.arrival_utc, "constraints": spec.constraints,
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
            say(json.dumps({"selected_site_ids": self.selected, "available_sites": available_sites()},
                           ensure_ascii=False, indent=2))
        elif text.startswith("/sites "):
            choice = text.partition(" ")[2].strip()
            try:
                if choice.startswith("coords "):
                    lat, lon = map(float, choice[len("coords "):].replace(",", " ").split())
                    sites = [resolve_coordinates(SiteCoordinates(lat_deg=lat, lon_e_deg=lon))]
                else:
                    sites = ["Site01_P1", "Site04_P1"] if choice == "all" else [
                        {"site01": "Site01_P1", "site04": "Site04_P1"}.get(part.strip().lower(), part.strip())
                        for part in choice.split(",")]
                if not sites or len(set(sites)) != len(sites) or any(
                        site not in {"Site01_P1", "Site04_P1"} for site in sites):
                    raise ValueError("Unsupported sites")
            except (ValueError, AssistantError):
                say("Chọn /sites Site04_P1, /sites all hoặc /sites coords <lat_deg> <lon_e_deg>. "
                    "Tọa độ chỉ nhận diện P1 đã xử lý trong sai số 1 m; không phân tích điểm tùy ý.")
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
    say("LunarSight | " + ("DEMO GIẢ LẬP LLM — không gọi OpenRouter." if demo else "OpenRouter thật — đọc model/key từ .env."))
    say(f"Kế hoạch làm việc: {session.baseline.arrival_utc}; {session.baseline.duration_hours:g} giờ; {session.baseline.current_site_id}.")
    say("Dữ liệu demo: 14/11–trước 28/11/2026 UTC, lưới 15 phút; nhiệm vụ 72 giờ.")
    say("Lệnh: /quit, /new, /reset, /baseline, /sites, /sites all, /sites Site04_P1, /sites coords <lat> <lon_e>.")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Explicit scripted LLM; real planning data, no API calls")
    parser.add_argument("--context", type=Path, default=ROOT/"tests/fixtures/assistant/request.json")
    parser.add_argument("--max-clarifications", type=int, choices=range(1,7), default=3)
    args = parser.parse_args(argv)
    context = json.loads(args.context.read_text(encoding="utf-8"))
    settings = AssistantSettings(assistant_enabled=True, _env_file=None) if args.demo else get_assistant_settings()
    if not args.demo and (not settings.assistant_enabled or not settings.openrouter_model or not settings.openrouter_api_key or not settings.openrouter_api_key.get_secret_value().strip()):
        print("Cần ASSISTANT_ENABLED=true, OPENROUTER_MODEL và OPENROUTER_API_KEY trong .env; hoặc chạy --demo.")
        return 2
    llm = DemoLLM() if args.demo else OpenRouterLLM(settings)
    return run_console(AssistantService(settings, llm, DraftStore()), context,
                       demo=args.demo, max_clarifications=args.max_clarifications)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
