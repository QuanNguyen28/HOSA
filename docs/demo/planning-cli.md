# Planning CLI — yêu cầu cứng về tổng thời gian, mong muốn mềm về tính liên tục

CLI gọi cùng PlanningService với API `/api/planning/compare` và
`/api/planning/windows/search`, không qua LLM và không cần key. Chạy từ gốc repo:

```bash
backend/.venv/bin/python scripts/planning_cli.py compare \
  --sites Site01_P1 Site04_P1 \
  --arrival 2026-11-17T00:00:00Z \
  --min-sunlit-fraction 0.8 --min-earth-los-fraction 0.8
```

Hai mức tối thiểu là **đầu vào bắt buộc**, thuộc [0,1]. Tổng giờ tương ứng bằng
fraction × 72; 0,8 tương đương 57,6 giờ trong nhiệm vụ 72 giờ. Giá trị 80% trong
ví dụ là lựa chọn minh họa, không phải yêu cầu do NASA quy định.

## Yêu cầu mềm tùy chọn

```bash
backend/.venv/bin/python scripts/planning_cli.py compare \
  --sites Site01_P1 --arrival 2026-11-14T00:00:00Z \
  --min-sunlit-fraction 0.8 --min-earth-los-fraction 0.1 \
  --max-darkness-hours 12 --max-earth-blackout-hours 6
```

Site01 có 72 giờ nắng và 11,25 giờ Earth LOS trong cửa sổ này nên đạt hai yêu cầu
cứng đã nhập. Khoảng mất LOS dài nhất là 60,75 giờ, vượt mong muốn 6 giờ, nhưng
phương án vẫn PASS và có thể được chọn. Vượt yêu cầu mềm được trả riêng trong
`soft_constraint_states` và `soft_violations`; `violations` chỉ chứa vi phạm cứng.
Bỏ hai cờ `--max-*` để không đặt mong muốn mềm.

## Nhập JSON hoặc gọi HTTP

Lưu payload thành `request.json`:

```json
{
  "scenario_id": "south_pole_demo_v1",
  "site_ids": ["Site01_P1", "Site04_P1"],
  "arrival_utc": "2026-11-17T00:00:00Z",
  "min_sunlit_fraction": 0.8,
  "min_earth_los_fraction": 0.8,
  "constraints": {
    "max_darkness_hours": 12,
    "max_earth_blackout_hours": 6
  },
  "rank_by": "total_earth_los_hours"
}
```

```bash
backend/.venv/bin/python scripts/planning_cli.py compare --request request.json
backend/.venv/bin/python scripts/planning_cli.py compare --request - < request.json
backend/.venv/bin/python scripts/planning_cli.py compare --request request.json \
  --base-url http://127.0.0.1:8000 --format csv --output result.csv
curl --fail-with-body http://127.0.0.1:8000/api/planning/compare \
  -H 'Content-Type: application/json' --data-binary @request.json
```

`constraints` là đối tượng mong muốn mềm tùy chọn. Không trộn `--request` với cờ
đầu vào. `--base-url` là địa chỉ server gốc, chưa bao gồm `/api`.

## Tìm ngày, xếp hạng và export

```bash
backend/.venv/bin/python scripts/planning_cli.py search \
  --sites Site01_P1 Site04_P1 \
  --arrival 2026-11-17T00:00:00Z --until 2026-11-24T00:00:00Z \
  --min-sunlit-fraction 0.8 --min-earth-los-fraction 0.8 \
  --rank-by total_earth_los_hours --max-results 3
backend/.venv/bin/python scripts/planning_cli.py capabilities
backend/.venv/bin/python scripts/planning_cli.py export RESULT_ID --format csv --output result.csv
backend/.venv/bin/python scripts/planning_cli.py compare --help
```

Chỉ phương án đạt cả hai yêu cầu cứng mới có thể được áp dụng. Mặc định xếp theo
`tổng giờ Earth LOS`; người dùng có thể chọn chỉ số khác. Khi chỉ số xếp hạng bằng
nhau, ưu tiên ít mong muốn mềm bị vượt hơn, rồi ít mong muốn chưa xác định hơn.
Đây là thứ tự ưu tiên minh bạch, không có điểm tổng hợp trọng số. Khoảng hạng vẫn
phản ánh riêng chỉ số được chọn. Near miss được xếp theo vi phạm cứng và vẫn FAIL.

`--until` loại trừ ngày bắt đầu cuối. Mặc định các lựa chọn cùng điểm không chồng
lấn; `--allow-overlap` cho phép chồng lấn. Ngày phải có múi giờ và nằm trên lưới
15 phút từ 14/11 đến trước 28/11/2026 UTC. Nhiệm vụ 72 giờ, panel 1 m, antenna 2 m.

Mã thoát 0 nghĩa là đã xử lý, kể cả kết quả FAIL. Mã 2 nghĩa là đầu vào, dữ liệu
hoặc HTTP lỗi; thông báo JSON ở stderr. JSON/CSV ở stdout hoặc tệp `--output`.

## Độ nhạy và dữ liệu thiếu

`sensitivity.scope` giữ đúng điểm, cửa sổ, hai mức tối thiểu và mong muốn mềm.
Backend áp dụng lại yêu cầu cứng cho profile 0,125° và ephemeris 1 phút:

- `STABLE_DECISION`: trạng thái các yêu cầu cứng không đổi ở các đối chiếu.
- `REVIEW`: ít nhất một yêu cầu cứng đổi trạng thái.
- `NOT_EVALUATED`: thiếu đối chiếu cho đúng cửa sổ hoặc yêu cầu còn chưa xác định.

Nếu chỉ đánh giá mong muốn mềm thay đổi, kết quả ghi
`soft_preferences_changed=true`; không biến một PASS cứng thành FAIL.
Ephemeris 1 phút hiện chỉ phủ 14–17/11/2026 UTC ở hai điểm. Không ngoại suy nhãn
ổn định sang cửa sổ khác; request không gọi JPL hoặc LLM. Với dữ liệu chưa biết,
cận dưới/ trên tổng Earth LOS lần lượt cộng V và V hoặc ?, không điền 0 cho ?.

## Thay đổi hợp đồng

Planning schema 2.0 dùng snapshot v0.3.0. Các client cũ phải bổ sung cả
`min_sunlit_fraction` và `min_earth_los_fraction`. Các trường `max_*` giữ tên nhưng
nay là mong muốn mềm; không dùng chúng để kết luận khả thi. Dữ liệu hình học
v0.2.0 được giữ nguyên. Chạy `scripts/build_planning_snapshot.py` để tái tạo v0.3.0
và kiểm tra checksum trong `data/processed/lunarsight/v0.3.0/derivation.json`.
