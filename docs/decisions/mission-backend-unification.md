# Thống nhất backend — phạm vi mục 1 đến 4

Đã thực hiện: schema nhiệm vụ chung, lõi đánh giá chung, chính sách kiểm định chung và đưa compare/search qua lõi này. Chưa thực hiện mục 5: chuyển toàn bộ endpoint cũ, CLI và hợp đồng chat sang schema mới.

## Luồng xử lý

```text
Point API / job ─────────────── MissionRequest ── DEM/JPL pipeline ─┐
                                                               ├─ mission.evaluation
Planning compare/search ────── MissionRequest ── DEM/JPL pipeline ─┤  metric + contact
                                └────────────── SnapshotProvider ─┘  validation + decision
```

`backend/app/mission/models.py` định nghĩa `MissionTarget`, `MissionRequest`, `ContactRequirements` và các kiểu dùng chung. Một target là `site_id` hoặc cặp `latitude_deg`, `longitude_e_deg`; nhập cả hai dạng bị từ chối. Site được phân giải thành đúng tọa độ catalog. Tọa độ tự nhập không bị gán sang site gần nhất.

API point giữ tên schema `PointAnalysisRequest` để tương thích; đây là lớp kế thừa schema nhiệm vụ chung. Nó nhận được cả `site_id` và tọa độ. Thời gian, chiều cao thiết bị, yêu cầu cứng và tiêu chí phụ cùng dùng validator của `MissionRequest`.

## Compare và search

Endpoint giữ nguyên:

- `POST /api/planning/compare`
- `POST /api/planning/windows/search`

Đầu vào planning giữ các tên cũ `arrival_utc`, `hardware` và `site_ids`. Chúng được chuyển thành `MissionRequest` cho từng phương án. Có thể thay `site_ids` bằng danh sách `targets`; không gửi cả hai.

`data_source` được chọn tường minh:

| Giá trị | Nguồn | Giới hạn |
|---|---|---|
| `snapshot` (mặc định tương thích) | Timeline và profile chuẩn bị sẵn | Site01/Site04, 72 giờ, phần cứng 1/2 m, lưới bắt đầu 15 phút, phạm vi scenario |
| `coordinate` | Cùng pipeline DEM/JPL với API point | Site trong catalog hoặc tọa độ được DEM phủ, nhiệm vụ nguyên 1–72 giờ, chiều cao >0 đến 20 m, lưới UTC 5 phút |

Không tự chuyển nguồn khi snapshot thiếu dữ liệu. Hai nguồn có thể có hình học/lưới khác nhau; cùng tọa độ và yêu cầu chưa đủ để đòi metric bằng nhau nếu nguồn bằng chứng khác nhau. Với `coordinate`, `analysis_result_id` trỏ đúng kết quả mà API point tính cho cùng nhiệm vụ, kể cả khi gọi từ search.

Cả hai nguồn hỗ trợ `min_sunlit_fraction`, `min_earth_los_fraction` tùy chọn và `contact_requirements`. Planning cần ít nhất một yêu cầu cứng. Point API có thể chỉ lấy số liệu và trả `decision=null`. Bỏ `min_earth_los_fraction` nếu muốn dùng cửa sổ liên lạc làm yêu cầu Earth chính. `constraints.max_darkness_hours` và `max_earth_blackout_hours` vẫn là tiêu chí phụ.

Search dùng khoảng bắt đầu `[arrival_utc, until_utc)`. Mỗi thời điểm tạo một nhiệm vụ riêng; `until_utc` không phải thời điểm kết thúc nhiệm vụ. `start_step_minutes` mặc định 15, nguồn coordinate cho phép bội số của 5. Độ dài khoảng tìm kiếm phải chia hết cho bước. `non_overlapping` áp dụng giữa các nhiệm vụ của cùng target.

Nguồn coordinate giới hạn **128 phép đánh giá/request**, tính bằng số target × số thời điểm bắt đầu; vượt giới hạn trả HTTP 422 `SEARCH_TOO_LARGE` trước khi tính. Compare tối đa 20 target. Đây vẫn là API đồng bộ; điểm hoặc miền thời gian chưa cache có thể mất nhiều thời gian. Horizon cache được dùng lại giữa các ngày; chỉ dùng cache JPL khi khớp observer/chiều cao/miền thời gian. `offline=true` không tự tải JPL, thiếu cache được giữ là ứng viên INDETERMINATE có issue.

## Chính sách quyết định và kiểm định

`mission.evaluation` là nơi duy nhất đánh giá các timeline mới của point/compare/search:

1. Tính metric từ các interval liên tục, nửa mở, đúng toàn miền nhiệm vụ.
2. Tính cửa sổ Earth LOS từ timeline đầy đủ; không dùng timeline hiển thị đã giảm mẫu.
3. Đánh giá từng yêu cầu cứng, lưu `nominal_sampled_decision`; đánh giá tiêu chí phụ riêng.
4. So sánh 0,25/0,125°, 400/300 km và 5/1 phút trên đúng miền thời gian, cùng các yêu cầu của request, kể cả contact/deadline.
5. Chỉ giữ PASS/FAIL khi coverage, ENU, seam và mọi so sánh bắt buộc đạt; còn lại INDETERMINATE. `validation.reason_codes` ghi nguyên nhân.

Ngưỡng vẫn PROVISIONAL: góc 0,1°, dịch sự kiện 5 phút, metric 10 phút. Không đổi ngưỡng để tạo PASS. Ghép biên dùng cùng thuật toán có thứ tự, một-một. Lệch góc xét toàn bộ profile 360°, nên nominal metric ổn định vẫn có thể không đạt gate.

Snapshot được kiểm tra checksum output của derivation, ENU từ blocker, seam của chiến lược đã thực sự chọn và bằng chứng so sánh đúng ngày. Không dùng một báo cáo 1 phút của ngày khác để xác nhận nhiệm vụ hiện tại. Thiếu profile radius của Site04 là thiếu bằng chứng, không mặc định đạt. Kiểm tra hình học Site01 được giữ làm gate cho snapshot Site04.

Search có thể loại nhanh toàn bộ các thời điểm của một target khi phát hiện điều kiện kiểm định chắc chắn không đạt, như thiếu profile hoặc lệch góc quá ngưỡng. Các trường hợp này được đếm INDETERMINATE, không biến thành FAIL hay đề xuất áp dụng. Các phương án còn lại dùng cùng analyzer như compare; không có lần tính metric riêng để lựa chọn rồi tính lại theo thuật toán khác.

Candidate thêm `nominal_sampled_decision`, `validation`, `contact_analysis`, `coordinate`, `analysis_result_id`. Chỉ PASS sau gate được xem khả thi. FAIL có thể là phương án gần đạt nhưng `apply_allowed=false`; INDETERMINATE không được đề xuất áp dụng.

Identity kết quả bao gồm phiên bản evaluation/validation/sensitivity. Cache quyết định cũ không được dùng thay kết quả theo policy mới; cache DEM/horizon/JPL vẫn được giữ khi đầu vào hình học không đổi.

## Chạy hai trường hợp ngoài Site01/Site04

Hai request mẫu cùng cấu hình đã kiểm chứng trước đó (24/11/2026 UTC, 6 giờ, panel/antenna 20 m):

```bash
curl --fail-with-body -sS http://127.0.0.1:8000/api/planning/compare \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/planning-compare-coordinate-request.json \
  -o /tmp/planning-compare-response.json

curl --fail-with-body -sS http://127.0.0.1:8000/api/planning/windows/search \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/planning-search-coordinate-request.json \
  -o /tmp/planning-search-response.json
```

Compare trả một PASS và một FAIL, cả hai validation đạt. Search mẫu chỉ xét một thời điểm bắt đầu cho hai target, đếm PASS=1/FAIL=1 và trả phương án PASS. Đây là kiểm tra tích hợp, không phải bằng chứng tối ưu toàn bộ miền địa lý/thời gian.

[Bằng chứng API thật](../validation/lunarsight/mission-unification-acceptance.json) lưu result ID, metric và validation để đối chiếu. Kết quả đầy đủ nằm trong `data/cache/point-analysis/unified-acceptance.json`. Dữ liệu khoa học là NASA DEM và cache JPL thật; fixture tổng hợp chỉ được dùng trong test tạm.

## Phần còn lại sau mục 4

Chat vẫn có hợp đồng site/scenario cũ, chưa nhận coordinate/contact mới. Nó đã kế thừa gate mới qua PlanningService, nên các snapshot trước đây nominal PASS có thể nay là INDETERMINATE. Các API legacy `/api/analyze`, site catalog/timeline và export legacy chưa được chuyển thành adapter của MissionRequest. Frontend và script chat chưa có luồng chọn nguồn/schema mới. Đây là công việc mục 5, không nằm trong thay đổi này.
