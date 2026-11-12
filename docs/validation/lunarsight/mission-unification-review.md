# Rà soát backend nhiệm vụ — 12/11/2026

Phạm vi: các mục 1–4 của kế hoạch thống nhất backend. Không mở rộng giao diện chat hoặc chuyển các API legacy trong mục 5.

## Các lỗi đã tái hiện và sửa

| Vấn đề | Trước | Sau |
|---|---|---|
| ID phương án coordinate | Compare dùng UTC, search dùng offset tương đối như `@0`; cùng nhiệm vụ khác ID, các miền tìm kiếm khác nhau có thể trùng ID | Cùng target và UTC có cùng ID; `start_index=null` cho coordinate |
| Thiếu file snapshot | Compare trả ứng viên chưa xác định nhưng bước preflight search ném lỗi | Cả hai giữ trạng thái chưa xác định, search không đề xuất phương án đó |
| Hash nguồn snapshot | Không bao gồm catalog dùng để phân giải tọa độ site | Catalog nằm trong fingerprint, thay tọa độ làm source hash thay đổi |
| Ephemeris không hợp lệ | `row_present=false` nhưng góc còn số có thể tạo V/B; giá trị vô hạn có thể mang cờ valid | Dòng thiếu hoặc góc không hữu hạn đều có trạng thái `?`, cờ missing ephemeris |
| Miền thời gian search | Chỉ kiểm tra nhiệm vụ đầu; nhiệm vụ cuối có thể vượt năm 2100 sau khi đã tính một số phương án | Kiểm tra nhiệm vụ cuối trước lần tính đầu, trả `INVALID_SEARCH_RANGE` |

7 ca test tái hiện (gồm 3 biến thể ephemeris) đều thất bại trước sửa và pass sau sửa. Bổ sung 4 ca đối chiếu cấu hình trong file request mẫu.

Toàn bộ bộ kiểm thử sau sửa đạt **260 passed**, với một cảnh báo deprecation từ thư viện TestClient/httpx; `git diff --check` sạch.

Phiên bản `mission-evaluation-1.0.1` và `planning-services-3.0.1` làm mới fingerprint quyết định. Cache hình học và JPL đúng đầu vào được giữ, không đổi ngưỡng khoa học để tạo PASS.

## Kiểm tra request và API

File point hiện là nhiệm vụ 72 giờ nhưng hai file planning còn là 6 giờ. Đã giữ file point, đồng bộ thời lượng planning thành 72 giờ và giữ bản 6 giờ riêng để tái lập báo cáo lịch sử. Các test request mẫu kiểm tra cùng tọa độ, phần cứng, thời gian và yêu cầu giữa point/compare/search.

Gọi route hiện tại qua FastAPI TestClient, dùng NASA DEM và cache JPL thật (`offline=true`):

- Điểm PASS: 72 giờ Sun và 72 giờ Earth LOS; validation đạt.
- Điểm FAIL: 0 giờ Sun và 0 giờ Earth LOS; validation đạt.
- Compare: PASS=1, FAIL=1; metric, yêu cầu và validation trùng API point.
- Search mẫu: 8 phương án, PASS=1, FAIL=1, INDETERMINATE=6 do thiếu cache cho các giờ bắt đầu khác. Phương án PASS trả về có cùng ID và kết quả với compare/direct.

Đầu vào và kết quả đối chiếu: [mission-unification-acceptance.json](mission-unification-acceptance.json). Kết quả đầy đủ cục bộ: `data/cache/point-analysis/review-acceptance.json`.

## Giới hạn đánh giá

Kiểm tra này xác nhận các đường gọi và các ca hồi quy được kiểm thử. Các ngưỡng vẫn PROVISIONAL; visibility lấy mẫu không phải chứng nhận vật lý tuyệt đối. API legacy và hợp đồng chat vẫn là công việc mục 5 như tài liệu kiến trúc đã nêu.
