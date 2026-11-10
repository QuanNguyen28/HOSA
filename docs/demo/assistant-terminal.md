# Demo tương tác terminal

Chạy từ `G:\My Drive\H1\HOSA`. Không cần khởi động Uvicorn; CLI gọi cùng AssistantService và bộ tính mà API dùng.

## 1. Dùng OpenRouter thật

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/assistant_chat.py
```

Nhập, ví dụ:

> Đổi lịch hạ cánh sang ngày 17/11, giữ phần cứng và đổi điểm trong vùng này.

Khi được hỏi, bổ sung:

> 2026-11-17T00:00:00Z

CLI hiện kế hoạch đã hiểu. Nhập `y` để chạy tính và giải thích; nhập `n` để hủy. Model/key lấy từ .env; CLI không tự gọi lại sau lỗi model hoặc timeout.

## 2. Chạy kịch bản demo ổn định, không gọi API

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/assistant_chat.py --demo
```

Thao tác: **Enter → nhập 2026-11-17T00:00:00Z → y → /quit**.

Chế độ này ghi rõ **DEMO GIẢ LẬP LLM**: chỉ phần hiểu ngôn ngữ/ExplainPlan được dựng theo kịch bản cố định. Bộ tính và dữ liệu chiếu sáng/LOS vẫn là snapshot thật hiện có. Không dùng chế độ này để chứng minh chất lượng model; câu khác kịch bản mẫu được báo chưa hỗ trợ.

## 3. Các lệnh

- /new hoặc /reset: bỏ yêu cầu hiện tại, bắt đầu lại; giữ kế hoạch gốc.
- /baseline: xem mốc gốc đang dùng.
- /sites all: chọn cả hai P1.
- /sites Site01_P1 hoặc /sites Site01_P1,Site04_P1: thay danh sách điểm được chọn.
- /quit: kết thúc, kể cả đang chờ trả lời hoặc xác nhận.

Mốc gốc demo: 14/11/2026 00:00 UTC, 72 giờ, Site01_P1; panel 1 m, antenna 2 m, ngưỡng tối 12 giờ và mất Earth LOS 6 giờ. Chỉ nhận ngày bắt đầu trên lưới 15 phút từ 14/11 đến trước 28/11/2026 UTC. CLI không tự áp dụng kết quả để đổi baseline.

Dùng `--context <file.json>` nếu muốn thay ngữ cảnh theo schema mẫu tại tests/fixtures/assistant/request.json. `--max-clarifications 3` giới hạn số vòng hỏi lại; tối đa 6.

## 4. Cơ chế hỏi lại

LLM lượt 1 ghi unresolved_fields và clarification_questions khi thiếu thông tin; backend cũng dựng câu hỏi dự phòng cho lỗi ngày, vùng chọn, coverage hoặc cấu hình. Có câu hỏi chưa giải quyết thì không tạo draft READY và không chạy bộ tính.

ParseRequest có clarifications gồm question/answer; mỗi lượt client gửi cả yêu cầu ban đầu và các câu trả lời. Mốc dịch ngày vẫn tính từ baseline gốc, không cộng dồn sau mỗi lần hỏi. Source quote được kiểm tra trong lời người dùng hoặc câu trả lời, không lấy ví dụ do assistant đặt ra làm dữ liệu của người dùng.

ParseResponse có questions và patch để client hiển thị. Khi đủ dữ liệu, client kiểm tra spec rồi gọi evaluate với confirmed=true.

**Số lượt gọi:** yêu cầu đủ thông tin dùng 2 lượt (hiểu + giải thích). Nếu có một vòng hỏi lại thì có 3 lượt: hiểu ban đầu, hiểu sau bổ sung, giải thích. Mỗi lần bổ sung là một lần chạy lại bước hiểu; không phải thêm agent hoặc tự sửa bằng lượt giải thích thứ ba. CLI công bố số lượt được ghi nhận; demo có API thật = 0.

## 5. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/assistant/test_terminal.py -q
.\.venv\Scripts\python.exe -m pytest tests/assistant -q
```

Đã chạy kịch bản terminal qua stdin tới FEASIBLE, không có API LLM thật. Transcript thử nằm trong data/cache/assistant/terminal-demo-transcript.txt. Model miễn phí hiện tại từng timeout ở lần thử trước; dùng --demo để diễn tập luồng hỏi đáp khi không muốn phụ thuộc endpoint.
