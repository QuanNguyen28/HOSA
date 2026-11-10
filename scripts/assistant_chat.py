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
from app.assistant.models import Baseline, ClarificationTurn, EvaluateRequest, ParseRequest
from app.assistant.provider import AssistantError, OpenRouterLLM
from app.assistant.service import AssistantService
from app.assistant.store import DraftStore
from scripts.demo_provider import DEMO_PROMPT, DemoLLM

QUIT = {"/quit", "/exit", "exit", "quit", "thoát"}
NEW = {"/new", "/reset"}


def set_sites(command, context, say):
    choice = command.partition(" ")[2].strip()
    sites = ["Site01_P1","Site04_P1"] if choice == "all" else [part.strip() for part in choice.split(",") if part.strip()]
    if not sites or len(set(sites)) != len(sites) or any(site not in {"Site01_P1","Site04_P1"} for site in sites):
        say("Dùng /sites all hoặc /sites Site01_P1,Site04_P1.")
        return False
    context["selected_site_ids"] = sites
    say("Vùng chọn: "+", ".join(sites))
    return True


def run_console(service, initial_context, ask=input, say=print, demo=False, max_clarifications=3):
    context = deepcopy(initial_context)
    baseline = Baseline.model_validate(context["baseline"])
    say("LunarSight | "+("DEMO GIẢ LẬP LLM — không gọi OpenRouter." if demo else "OpenRouter thật — đọc model/key từ .env."))
    say(f"Kế hoạch gốc: {baseline.arrival_utc}; {baseline.duration_hours:g} giờ; {baseline.current_site_id}.")
    say("Dữ liệu demo: 14/11–trước 28/11/2026 UTC, lưới 15 phút; nhiệm vụ 72 giờ.")
    say("Lệnh: /quit, /new, /baseline, /sites all hoặc /sites Site01_P1.")
    if demo:
        say("Nhấn Enter để dùng câu mẫu: "+DEMO_PROMPT)
    try:
        while True:
            text = ask("\nBạn> ").strip()
            if text.lower() in QUIT:
                return 0
            if text in NEW:
                say("Đã bắt đầu yêu cầu mới; kế hoạch gốc giữ nguyên.")
                continue
            if text == "/baseline":
                say(json.dumps(context["baseline"], ensure_ascii=False, indent=2))
                continue
            if text.startswith("/sites"):
                set_sites(text, context, say)
                continue
            if not text:
                if demo:
                    text = DEMO_PROMPT
                else:
                    continue
            history, calls = [], 0
            for round_index in range(max_clarifications+1):
                try:
                    request = ParseRequest(text=text, baseline=baseline,
                        selected_site_ids=context.get("selected_site_ids"), clarifications=history)
                    say("Đang hiểu yêu cầu...")
                    parsed = asyncio.run(service.parse(request))
                    calls += parsed.llm_calls
                    if parsed.status == "READY":
                        spec = parsed.spec
                        say("Kế hoạch đã hiểu:")
                        say(f"  Bắt đầu: {spec.arrival_utc}; kết thúc: {spec.end_utc}")
                        if spec.search_from_utc:
                            say(f"  Được tìm ngày từ {spec.search_from_utc} đến trước {spec.search_until_utc}")
                        say("  Điểm: "+", ".join(spec.site_ids))
                        say(f"  Tối tối đa {spec.constraints.max_darkness_hours:g} giờ; mất Earth LOS tối đa {spec.constraints.max_earth_blackout_hours:g} giờ.")
                        say("  Phần cứng giữ nguyên; nhiệm vụ 72 giờ.")
                        answer = ask("Chạy đánh giá kế hoạch này? [y/N] ").strip().lower()
                        if answer in QUIT:
                            return 0
                        if answer not in {"y","yes","có","c"}:
                            say("Đã hủy; chưa chạy bộ tính hoặc lượt giải thích.")
                            break
                        say("Đang tính và giải thích...")
                        result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,
                            spec_hash=parsed.spec_hash, baseline=baseline, confirmed=True)))
                        calls += result.llm_calls-1
                        say("Kết quả: "+result.evidence.status)
                        for line in result.explanation:
                            say("  "+line)
                        say(f"Giải thích: {result.explanation_mode}; lượt xử lý LLM được ghi nhận: {calls}"+
                            (" (giả lập; API thật = 0)." if demo else "."))
                        say("Đây là đánh giá demo; kế hoạch gốc chưa bị cập nhật.")
                        break
                    say("Cần làm rõ:" if parsed.status == "NEEDS_INPUT" else "Yêu cầu chưa được hỗ trợ:")
                    for question in parsed.questions:
                        say("  "+question.question)
                    if parsed.status == "UNSUPPORTED_REQUIREMENT":
                        say("Nhập yêu cầu mới hoặc /quit.")
                        break
                    if round_index == max_clarifications:
                        say("Đã đạt giới hạn hỏi lại. Hãy nhập một yêu cầu mới đầy đủ hơn.")
                        break
                    answer = ask("Bạn bổ sung> ").strip()
                    if answer.lower() in QUIT:
                        return 0
                    if answer in NEW:
                        break
                    if answer.startswith("/sites"):
                        if not set_sites(answer, context, say):
                            break
                        answer = "Vùng đã chọn: "+", ".join(context["selected_site_ids"])
                    if not answer:
                        say("Câu trả lời trống; nhập lại yêu cầu để tiếp tục.")
                        break
                    history.append(ClarificationTurn(question=" ".join(q.question for q in parsed.questions),
                                                     answer=answer))
                except AssistantError as error:
                    say("Dừng yêu cầu: "+error.code+". Không tự gọi lại model.")
                    if error.code == "OPENROUTER_TIMEOUT":
                        say("Endpoint vượt thời gian cho phép. Có thể dùng --demo để trình diễn không cần API.")
                    break
                except (ValidationError, OSError, ValueError) as error:
                    say("Dữ liệu chưa hợp lệ: "+type(error).__name__+". Hãy nhập lại yêu cầu.")
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
