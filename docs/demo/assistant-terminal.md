# Demo tương tác terminal

Policy hiện tại: tổng thời gian có nắng và Earth LOS là yêu cầu cứng; baseline phải
có `min_sunlit_fraction` và `min_earth_los_fraction` (fixture minh họa đều là 0,8).
Các giới hạn tối/mất LOS liên tục trong `constraints` là mong muốn mềm, có thể
vượt mà phương án vẫn đạt yêu cầu cứng. Xem [hợp đồng mới](planning-cli.md).

Chạy từ thư mục gốc repo. Không cần khởi động Uvicorn; CLI gọi cùng AssistantService và bộ tính mà API dùng. Trên Linux:

```bash
backend/.venv/bin/python scripts/assistant_chat.py
```

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

- `/new`: bỏ yêu cầu đang chờ, giữ kế hoạch làm việc, vùng chọn và lịch sử.
- `/reset`: xóa lịch sử, yêu cầu đang chờ và khôi phục toàn bộ ngữ cảnh ban đầu.
- `/baseline`: xem kế hoạch làm việc, `selected_site_ids` và cấu hình tìm kiếm hiện tại.
- `/sites`: xem vùng chọn và tọa độ catalog (độ, vĩ độ và kinh độ đông).
- `/sites all`: chọn cả hai P1; không tự thay site hiện tại bằng kết quả xếp hạng.
- `/sites Site04_P1`: chọn Site04 và đặt site hiện tại trong kế hoạch làm việc thành Site04. Chấp nhận cả alias `Site01`, `Site04`.
- `/sites Site01_P1,Site04_P1`: chọn rõ danh sách hai điểm.
- `/sites coords -89.779800 203.733786`: nhận diện Site04_P1 bằng vĩ độ và kinh độ đông. Chấp nhận kinh độ -180 đến 360 độ; chỉ khớp P1 đã xử lý trong sai số nhập tối đa 1 m. Tọa độ khác bị từ chối, không thay thế bằng điểm gần nhất hoặc ngoại suy kết quả khoa học.
- /quit: kết thúc, kể cả đang chờ trả lời hoặc xác nhận.

Mốc gốc demo: 14/11/2026 00:00 UTC, 72 giờ, Site01_P1; panel 1 m, antenna 2 m; yêu cầu cứng nắng và Earth LOS đều tối thiểu 80%; mong muốn mềm tối 12 giờ và mất Earth LOS 6 giờ. Chỉ nhận ngày bắt đầu trên lưới 15 phút từ 14/11 đến trước 28/11/2026 UTC. Sau khi người dùng nhập `y` và đánh giá hoàn tất, CLI nhớ kế hoạch đã đánh giá làm baseline cho lượt sau (ngày, ngưỡng, vùng chọn, metric xếp hạng, khoảng tìm kiếm). Với một site, site đó trở thành site hiện tại; với hai site, giữ site hiện tại và vùng chọn hai site. Không tự áp dụng site/ngày được đề xuất từ kết quả xếp hạng. Đây là trạng thái làm việc để tiếp tục trao đổi, không phải phê duyệt nhiệm vụ; trạng thái FAIL hoặc thiếu dữ liệu vẫn được giữ đúng trong lịch sử. Hủy bản nháp không thay kế hoạch làm việc.

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

## 6. Hội thoại nhiều lượt

CLI gửi tối đa 8 lượt trước qua `ParseRequest.conversation_history`; mỗi lượt gồm lời người dùng, câu trả lời làm rõ, kết cục và tóm tắt kết quả. `baseline`, `selected_site_ids` và `planning_context` là trạng thái hiện tại có thẩm quyền. Model chỉ trích thay đổi của yêu cầu mới, không cộng lại các lần dịch ngày cũ. Ngày chính xác mới sẽ bỏ khoảng tìm kiếm cũ; thay ngưỡng không làm mất khoảng tìm kiếm đang dùng.

Thông tin thiếu vẫn được giữ qua lượt nhập sau; `/new` bỏ yêu cầu đang chờ. Tối đa 6 câu bổ sung cho một yêu cầu. Lỗi model không tự retry và không thay kế hoạch làm việc. Lệnh đọc `/baseline`, `/sites` dùng được khi hỏi lại hoặc chờ xác nhận; lệnh thay trạng thái khi chờ xác nhận hủy bản nháp cũ để tránh chạy với ngữ cảnh đã đổi.

Ví dụ:

```text
/sites Site04_P1
/baseline
Đổi lịch hạ cánh sang 2026-11-17T00:00:00Z, giữ nguyên phần cứng
y
Giảm tối liên tục tối đa xuống 8 giờ, giữ các thông tin khác
y
/baseline
```

Lượt cuối vẫn dùng Site04 và ngày 17/11; chỉ ngưỡng tối thay đổi. Có thể chọn site bằng ngôn ngữ tự nhiên hoặc tọa độ có nhãn vĩ độ/kinh độ đông; backend xác minh site sau khi model trích thông tin.

Ngữ cảnh chỉ tồn tại trong phiên CLI, chưa lưu qua lần thoát chương trình. API `/parse` cũng nhận `conversation_history` và `planning_context`, nhưng client API phải lưu/gửi lại trạng thái; không có lịch sử toàn cục dùng chung giữa người dùng. Các summary trong lịch sử không được dùng làm source_quote; chỉ lời người dùng được chấp nhận.
