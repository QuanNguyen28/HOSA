# Biên bản chốt cổng G0 — HOSA

Trạng thái: **PENDING APPROVAL**  
Phiên bản dữ liệu/phương pháp: `v0.2.0` / `lunar-sphere-enu-v2`  
Phạm vi áp dụng: nguyên mẫu giáo dục hai điểm `Site01_P1` và `Site04_P1`.

Biên bản này là hồ sơ phê duyệt cấu hình đầu vào và ngưỡng kiểm thử. Không đổi
nhãn `PROVISIONAL` trong cấu hình, giao diện hoặc báo cáo cho tới khi phần ký xác
nhận được điền đầy đủ.

## 1. Cấu hình xin phê duyệt

| Hạng mục | Giá trị khóa cho MVP | Nguồn cấu hình |
|---|---:|---|
| Miền mốc bắt đầu | 2026-11-14 00:00 đến 2026-11-28 00:00 UTC | `scenario.json` |
| Miền dữ liệu cần thiết | 2026-11-14 00:00 đến 2026-12-01 00:00 UTC | `scenario.json` |
| Thời lượng hoạt động | 72 giờ, khoảng nửa kín `[start,end)` | `scenario.json` |
| Bước mô hình | 5 phút | `scenario.json` |
| Bước mốc bắt đầu | 15 phút; 1.344 mốc/site | `scenario.json` |
| Điểm phân tích | `Site01_P1`, `Site04_P1` | `scenario.json` |
| Chiều cao tâm panel | 1 m | `geometry_config.json` |
| Chiều cao tâm antenna | 2 m | `geometry_config.json` |
| Ngưỡng tối minh họa | tối đa 12 giờ liên tục | `scenario.json` |
| Ngưỡng mất Earth LOS minh họa | tối đa 6 giờ liên tục | `scenario.json` |
| Sai biệt chân trời cho kiểm thử | `tol_horizon_deg = 0.1°` | `geometry_config.json` |
| Sai lệch thời điểm sự kiện | `tol_event_minutes = 5` | `geometry_config.json` |
| Sai lệch thời lượng | `tol_duration_minutes = 10` | `geometry_config.json` |

## 2. Cách hiểu bắt buộc

- Sun visibility dùng tâm Mặt Trời và chân trời địa hình tại độ cao panel 1 m;
  không phải mô hình công suất, điện năng hoặc nhiệt.
- Earth LOS dùng tâm Trái Đất và chân trời địa hình tại độ cao antenna 2 m;
  không phải link budget hoặc bảo đảm liên lạc.
- `PASS`, `FAIL`, `INDETERMINATE` chỉ có ý nghĩa trong scenario, hai site, miền
  thời gian và phiên bản phương pháp nêu trên; không phải chứng nhận an toàn hạ cánh.
- Hai ngưỡng 12 giờ và 6 giờ là ngưỡng minh họa phục vụ tác vụ học tập, không phải
  yêu cầu của một tàu vũ trụ thật.

## 3. Bằng chứng trước phê duyệt

- Báo cáo kiểm định khoa học:
  `docs/validation/lunarsight/v0.2.0/reports/scientific_validation.md`.
- Báo cáo nghiệm thu ứng dụng:
  `docs/validation/lunarsight/v0.2.0/reports/application_acceptance.md`.
- Độ nhạy Site01:
  `docs/validation/lunarsight/v0.2.0/reports/sensitivity.json`.
- Độ nhạy độc lập Site04:
  `docs/validation/lunarsight/v0.2.0/reports/Site04_sensitivity.json`.
- Release audit:
  `docs/validation/lunarsight/v0.2.0/reports/release_audit.json`.

Kết quả hiện tại cần lưu ý: quyết định tại ca kiểm tra 72 giờ không đổi khi so
lưới phương vị 0,25°/0,125° và bước thời gian 5 phút/1 phút. Một số sai biệt góc
cực đại vượt `0.1°`, vì vậy sản phẩm phải giữ nhãn cảnh báo độ nhạy góc dù quyết
định không đổi.

## 4. Quyết định và chữ ký

Chọn đúng một phương án:

- [ ] **APPROVED** — cho phép đổi scenario và tolerance status từ `PROVISIONAL`
  sang `APPROVED`, sau đó chạy lại toàn bộ pipeline và `make release-check`.
- [ ] **APPROVED WITH CONDITIONS** — ghi điều kiện bên dưới; chưa đổi trạng thái
  cho tới khi các điều kiện được xác nhận hoàn tất.
- [ ] **REJECTED / REWORK** — không dùng bộ cấu hình này để khóa bản nộp.

Điều kiện hoặc yêu cầu sửa đổi:  
`..............................................................................`

| Vai trò | Họ tên | Quyết định | Ngày giờ và múi giờ | Chữ ký/xác nhận |
|---|---|---|---|---|
| Mission/Product owner | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| GIS/Science owner | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| QA/Release owner | REQUIRED | REQUIRED | REQUIRED | REQUIRED |

Commit/release candidate được phê duyệt: `REQUIRED`  
Người cập nhật trạng thái cấu hình sau phê duyệt: `REQUIRED`

