# Nhiệm vụ dài, ngày kết thúc và tối ưu computing

Nhánh `feat/merge-fe-be`. Không có giới hạn trên do ứng dụng đặt cho `duration_hours` hoặc ngày kết thúc. Chỉ yêu cầu số hữu hạn, ngày UTC biểu diễn được, nhiệm vụ ít nhất 1 giờ, kết thúc sau bắt đầu và nằm trên lưới 5 phút. Giới hạn dữ liệu thực sự của JPL/DEM vẫn được kiểm tra khi tính.

Cập nhật resolution 2.1: kiểm mission bounds trước khi refinement; request ngắn có worker riêng. Xem [kiểm tra INDETERMINATE và thời gian thực tế](compute-and-resolution-audit.md), gồm cả trường hợp tọa độ mới vẫn mất thời gian quét DEM. Các report 2.0 bên dưới giữ làm bằng chứng lịch sử.

## Gọi API

`POST /api/lunar/point/analyze` nhận một trong hai cách:

```json
{
  "latitude_deg": -89.43892646479243,
  "longitude_e_deg": 222.90402192622227,
  "start_utc": "2026-11-17T00:00:00Z",
  "end_utc": "2026-11-27T00:00:00Z",
  "panel_height_m": 1,
  "antenna_height_m": 2,
  "min_sunlit_fraction": 0.8,
  "min_earth_los_fraction": 0.8,
  "resolve_indeterminate": true
}
```

Hoặc thay `end_utc` bằng `duration_hours: 240`. Nếu gửi cả hai thì phải mô tả cùng một khoảng thời gian. Có thể dùng số giờ lẻ theo bước 5 phút. Response chuẩn hóa cả `duration_hours` và `end_utc`.

Trong UI chọn **Define mission by → Target end date (UTC)** hoặc **Duration in hours**. Explore, Compare và Best dates dùng cùng khoảng nhiệm vụ. Trong Best dates, mốc kết thúc xác định thời lượng tại start đầu tiên; các start tiếp theo dịch cả khoảng nhiệm vụ với cùng thời lượng. `until_utc` vẫn là cận trên không bao gồm của khoảng tìm start, không phải ngày kết thúc nhiệm vụ.

Compare/search tự chuyển sang pipeline tọa độ khi thời lượng khác snapshot 72 giờ. Assistant nhận được thời lượng mới hoặc `mission_end_utc`, lưu vào ngữ cảnh cho turn tiếp theo và dùng pipeline tọa độ; bản snapshot demo vẫn là dữ liệu 72 giờ.

Ví dụ trực tiếp:

```bash
curl -sS http://127.0.0.1:8001/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-long-end-date-request.json
```

## Giải quyết thêm INDETERMINATE

Chính sách `sampled-mission-path-envelope-2.0` không còn đòi mọi mẫu phải chắc chắn cùng một trạng thái. Nó xét các profile coarse/fine/300 km trên native 1 phút và mô hình giữ mẫu của native 5 phút. Những mẫu chưa vượt envelope bảo thủ vẫn được giữ là `?`.

Envelope được nới bởi sai lệch angular lớn nhất của các cấu hình không gian đã tính, cộng thêm 0.1°. Từ V/B/? tính các cận thời lượng và contact requirements bằng cùng evaluator chính. Chỉ cho PASS khi **cận bất lợi vẫn đáp ứng mọi hard requirement**, kể cả contact liên tục và deadline nếu được yêu cầu. Numerical sensitivity toàn mô hình có thể chưa đạt và vẫn được ghi trong `validation.reason_codes`; không sửa thành full validation PASS.

Thiếu dữ liệu/so sánh, sai ENU, seam hoặc integrity vẫn chặn fallback này. Hard FAIL vẫn trả FAIL theo yêu cầu trước đó. Envelope là cận thực nghiệm theo các cấu hình số đã so sánh, không phải cận sai số vật lý DEM hoặc chứng nhận không có sự kiện giữa các mẫu. Ngưỡng còn **PROVISIONAL**.

Kết quả dữ liệu thật:

| Ca | Kết quả |
|---|---|
| Site01, 17–27/11/2026 UTC, 240 giờ | PASS; Sun và Earth LOS đều 240 giờ theo mẫu và cận mission-path. |
| Site04, 17–20/11/2026 UTC, yêu cầu Sun/Earth 80% | PASS thay cho INDETERMINATE của policy cũ. Sun 72 giờ; Earth LOS bảo thủ 69.4167–72 giờ, vẫn vượt 57.6 giờ yêu cầu. 155 phút chưa chắc chắn không bị biến thành V. |

`validation.passed` vẫn false ở hai ca này. Cận mới nằm trong `validation.mission_path.metrics_hours` và UI hiển thị riêng. Xem `long-missions-live-report.json` và request `point-analysis-bounded-site04-request.json`.

## Các tối ưu đã kiểm tra

- Kết quả cache đã kiểm tra hash được đọc trước compute lock, kể cả khi worker đang xử lý nhiệm vụ khác. Job cache-hit không cần xếp hàng. Các request pending giống nhau dùng chung job.
- Query planner dùng lại các khoảng JPL đã có cache khi observer, target, độ cao, DEM hash, native step và toàn bộ cấu hình query khớp. Mỗi raw response được adapter kiểm tra lại trước khi dùng. Khoảng mới được chia thành batch tối đa 40.000 interval; đây là kích thước một trang dữ liệu, không phải giới hạn nhiệm vụ. Giữ native 1/5 phút và kiểm tra sample tại điểm nối, không nội suy để bù thiếu dữ liệu.
- Contact analysis gom các interval kề nhau cùng trạng thái trước khi đánh giá; vẫn giữ native sampling step. Không cần serialize/parse timestamp của từng mẫu nhiều lần trong sensitivity checks. Event extraction cũng xét các vị trí đổi trạng thái thay vì lặp mọi row.
- Các cột trạng thái/coverage dùng categorical để giảm RAM. Parser JPL nhận được cả timestamp có giây và chỉ giờ/phút; vẫn kiểm tra toàn bộ UTC grid, duplicate, missing rows và terminal sample.
- Job lưu input khi chạy và hiện tiến độ `horizons_<step>min_<target>_batch_<n>_of_<total>`.

Benchmark trên dữ liệu thật 240 giờ, median 5 lần:

| Thành phần | Trước | Sau |
|---|---:|---:|
| Contact analysis, cùng output | 0.06786 s | 0.000528 s |
| RAM DataFrame timeline trong benchmark | 996.612 byte | 256.714 byte |

Request cache qua API trả khoảng 0.24 s trong lúc worker đang chạy request dài khác; point/compare/search/CSV khớp nhau. Đây là microbenchmark theo thành phần, không phải cam kết tăng tốc toàn pipeline 128 lần. Tải JPL mới và quét địa hình lần đầu vẫn có chi phí riêng.

Tái kiểm tra benchmark với result theo policy hiện tại (bảng 240 giờ ở trên là report lịch sử):

```bash
curl -fsS http://127.0.0.1:8001/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-revalidation-pass-request.json \
  -o /tmp/current-point-result.json
backend/.venv/bin/python scripts/benchmark_compute_backend.py \
  /tmp/current-point-result.json --output /tmp/current-compute-performance.json
```

Raw, params, header, coverage và hash vẫn được giữ theo [JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html). Kết quả hiệu năng/API chi tiết ở `compute-performance-report.json` và `long-missions-api-report.json` cạnh tài liệu này.
