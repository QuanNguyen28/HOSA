# Terminal chat qua backend session/run

Terminal gọi cùng HTTP API với các client khác, dùng provider cấu hình tại backend. Đây là flow live; script không dùng demo/template để thay câu trả lời LLM.

Tạo `.venv`, cài `./backend[test]`, cấu hình `.env` với `ASSISTANT_ENABLED=true` và provider keys theo [hướng dẫn BE/LLM](../assistant/BE_LLM_RELEASE.md). Không commit `.env` hoặc đưa key vào command line.

## Windows UTF-8

Từ root repo:

```powershell
pwsh -NoExit -File scripts/open_assistant_terminal.ps1 -New
```

Launcher cấu hình input/output UTF-8 cho riêng console, chạy terminal bằng Python UTF-8 và khởi động API loopback chạy nền nếu chưa có. Mặc định tôn trọng model/failover trong cấu hình. Chọn model NVIDIA cụ thể bằng `-Model`; dùng `-Strict` để yêu cầu tắt failover. Nếu API đang chạy với model hoặc failover không phù hợp, launcher báo rõ và yêu cầu khởi động lại server thay vì âm thầm thay tiến trình đang hoạt động.

Đầu terminal in model thực tế và một dòng tiếng Việt để kiểm tra dấu. `/unicode` cho nhập rồi echo tiếng Việt ngay tại máy, không gọi inference.

## Chạy thủ công hoặc trên hệ điều hành khác

Khởi động API từ thư mục backend với `uvicorn app.main:app --host 127.0.0.1 --port 8000`, sau đó chạy từ root:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/assistant_chat.py --new
```

Linux/macOS dùng `.venv/bin/python`. Có thể dùng `--base-url http://127.0.0.1:8000/api/assistant` và `--session <id>` để tiếp tục phiên cụ thể. Không có `--new` thì script thử khôi phục ID trong ignored `data/cache/assistant/terminal-session.txt`.

## Hội thoại và kết quả

Nhập câu hỏi tự nhiên ở `Bạn>`. Câu hỏi kiến thức được giải thích từ nguồn; yêu cầu tính toán đi qua mission/planning engine và kiểm tra đầu vào. Khi thiếu ngày/giờ hoặc thông tin bắt buộc, chatbot hỏi lại. Các mong muốn mềm tùy chọn không chặn tính toán.

- `/new`: tạo phiên mới; lịch sử phiên cũ vẫn ở server.
- `/result`: xem JSON số liệu của kết quả engine gần nhất trong phiên; mặc định terminal chỉ in lời giải thích và nguồn.
- `/apply <candidate_id>`: xác nhận trước khi áp dụng candidate PASS; backend kiểm tra phiên bản/nguồn.
- `/unicode`: thử dấu tiếng Việt tại máy.
- `/help`, `/quit`: trợ giúp và thoát.
- Ctrl+C khi đang chờ: gửi yêu cầu hủy run.

Một phép tính thường gồm lượt LLM hiểu đầu vào, engine tính và lượt LLM giải thích; repair/retry có thể thêm request và đều có trace. Không có deadline đọc/sinh tổng của ứng dụng. NIM có thể phản hồi rất chậm; terminal chỉ in câu trả lời sau khi JSON cuối đã được validate. Xem [latency đã quan sát và giới hạn nghiệm thu](../assistant/LLM_IMPLEMENTATION_STATUS.md).

`run_console` và các lớp rehearsal cũ còn trong module để giữ kiểm thử tương thích; entry point `main` dùng `run_remote_console`. Các công cụ live evaluation nằm riêng trong `scripts/assistant_eval.py` và không được tính pass bằng mock/template output.
