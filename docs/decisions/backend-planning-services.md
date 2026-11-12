# Backend planning dùng chung — PolarWindow và BroBYW

Chính sách quyết định và hợp đồng bên dưới được thay thế bởi
[availability-hard-continuity-soft](availability-hard-continuity-soft.md):
snapshot v0.3.0/schema 2.0 bắt buộc tổng nắng và Earth LOS tối thiểu; các giới hạn
tối/mất LOS liên tục là mong muốn mềm. Phần còn lại giữ vai trò lịch sử thiết kế.

Phạm vi đã chốt: dùng snapshot v0.2.0, hai điểm P1, phần cứng và nhiệm vụ 72 giờ hiện có. Bổ sung backend so sánh, tìm cửa sổ, xếp hạng bất định, xuất kết quả và nối vào một LLM hai lượt.

## Ý tưởng tham khảo và cách áp dụng

| Nguồn | Ý tưởng giữ lại | Triển khai trong dự án |
| --- | --- | --- |
| PolarWindow: compare_service, metrics | Chi tiết và so sánh dùng cùng bộ tính; xếp hạng theo một chỉ số, công bố khoảng hạng khi bất định chồng lấn | planning/analysis.py, metrics.py, ranking.py |
| PolarWindow: lớp API và công cụ AI | Route chỉ nhận/kiểm tra dữ liệu rồi gọi service; AI chỉ dùng bằng chứng có định danh | planning/router.py, assistant/engine.py, evidence.py, explanations.py |
| BroBYW: finder | Quét các cửa sổ nhiệm vụ, lọc đạt ràng buộc trước khi chọn; tránh trả nhiều cửa sổ chồng lấn của cùng điểm | planning/finder.py đọc CSV mỗi điểm một lần, sau đó chỉ tải chi tiết cho các lựa chọn được trả về |
| BroBYW: metrics | Các khoảng [bắt đầu, kết thúc); ghi nhận sự kiện chạm biên | analysis.py trả metric_context và timeline; không tuyên bố đã đo được đêm nằm ngoài cửa sổ nhiệm vụ |

BroBYW đặt phần tính chính trong thư viện TypeScript của ứng dụng web. Ở đây ý tưởng được viết lại thành service Python phía backend; không sao chép nguyên cấu trúc frontend hoặc chuyển sang nhiều agent. Không triển khai pin hoặc thay chiều cao thiết bị trong phạm vi đã chọn.

Không dùng điểm tổng hợp có trọng số để che đánh đổi. rank_min/rank_max phản ánh so sánh trên chỉ số rank_by; thứ tự hiển thị và đề xuất vận hành là chính sách riêng. Khi không có PASS, chính sách gần đạt ưu tiên mức vi phạm tương đối lớn nhất thấp nhất, nhưng vẫn giữ FAIL/apply_allowed=false. Điểm INDETERMINATE không được xếp như đã biết.

Thời lượng tối trong bộ dữ liệu này là thời lượng **bên trong 72 giờ nhiệm vụ**. Sự kiện chạm biên có thể còn tiếp diễn ngoài nhiệm vụ; trả cờ để tránh diễn giải thành toàn bộ chiều dài đêm. Không tự thay cận trong cửa sổ thành vô hạn vì đó sẽ là một đại lượng khác.

## Tổ chức file

| Module | Trách nhiệm |
| --- | --- |
| backend/app/planning/models.py | Schema nghiệp vụ dùng chung cho API và assistant |
| backend/app/planning/metrics.py | Kiểm tra cận, quyết định PASS/FAIL/INDETERMINATE, lượng vi phạm |
| backend/app/planning/ranking.py | Quan hệ tốt hơn chắc chắn, khoảng hạng và thứ tự hiển thị |
| backend/app/planning/repository.py | Đọc snapshot, hash nguồn, lưu/xuất kết quả có phiên bản |
| backend/app/planning/analysis.py | Gọi bộ tính hiện có; kiểm tra kết quả và sự kiện; tạo dữ liệu chi tiết |
| backend/app/planning/finder.py | Quét tập ngày cho phép và chọn các cửa sổ không chồng lấn |
| backend/app/planning/service.py | Điều phối compare/search; kiểm tra nguồn trước và sau tính |
| backend/app/planning/router.py | HTTP routes độc lập với LLM |
| backend/app/assistant/normalization.py | Chuyển RequestPatch thành yêu cầu đã khóa theo baseline |
| backend/app/assistant/engine.py | Adapter mỏng sang PlanningService |
| backend/app/assistant/evidence.py | Rút kết quả thành facts gắn candidate_id và sự kiện |
| backend/app/assistant/explanations.py | Chặn tham chiếu/kết luận sai, dựng câu từ số liệu backend |
| backend/app/assistant/service.py | Điều phối hai lượt LLM, xác nhận, cache kết quả/lỗi draft |
| backend/app/core/errors.py | Mã lỗi chung, tránh domain phụ thuộc provider LLM |

models.py của assistant nhập lại các kiểu chung để giữ các import và payload cũ. API /api/analyze tiếp tục hoạt động. Hàm lưu kết quả cũ chỉ được sửa phần tên file tạm để hai request giống nhau không tranh cùng một file; công thức khoa học giữ nguyên.

## API đã triển khai

- GET /api/planning/capabilities: scenario, giới hạn, chỉ số xếp hạng và phiên bản nguồn.
- POST /api/planning/compare: so sánh một ngày bắt đầu chính xác.
- POST /api/planning/windows/search: tìm trong khoảng ngày bắt đầu được phép.
- GET /api/planning/results/{result_id}?format=json hoặc csv: xuất cùng kết quả đã lưu.

Các API planning không cần API key LLM. Request bị chặn nếu sai múi giờ, ngoài coverage, lệch lưới 15 phút, lặp điểm hoặc yêu cầu phần cứng/thời lượng khác scenario.

Payload compare:

```json
{
  "scenario_id": "south_pole_demo_v1",
  "site_ids": ["Site01_P1", "Site04_P1"],
  "arrival_utc": "2026-11-17T00:00:00Z",
  "constraints": {
    "max_darkness_hours": 12,
    "max_earth_blackout_hours": 6
  },
  "rank_by": "total_sun_hours"
}
```

Để tìm ngày, gửi cùng các trường trên tới windows/search và bổ sung:

```json
{
  "until_utc": "2026-11-24T00:00:00Z",
  "max_results": 3,
  "non_overlapping": true
}
```

arrival_utc bao gồm, until_utc loại trừ **ngày bắt đầu**; đây không phải ngày kết thúc hoạt động. Server quét toàn bộ các mốc hợp lệ trong phạm vi, thống kê cả PASS/FAIL/INDETERMINATE rồi chọn tối đa max_results (giới hạn 20). Chi tiết/timeline chỉ tải cho các lựa chọn được trả về. Khoảng hạng trong kết quả tìm kiếm so sánh các lựa chọn được trả về, không khẳng định hạng trên toàn bộ lưới.

result_id phụ thuộc request đã chuẩn hóa và hash nguồn. Response công bố source_hash, dataset_version, method_version, coverage, vi phạm từng điều kiện và cảnh báo. JSON/CSV xuất cùng đơn vị giờ và cấu hình phần cứng thực tế. Dữ liệu thiếu giữ trạng thái chưa đủ; nguồn đổi trong lúc tính bị chặn.

## Luồng LLM

1. Lượt 1 hiểu yêu cầu và đề xuất RequestPatch. Chỉ khi người dùng cho phép đổi ngày trong khoảng xác định mới đặt search_from_utc/search_until_utc.
2. Backend chuẩn hóa; người dùng kiểm tra và xác nhận draft.
3. Adapter gọi cùng PlanningService mà HTTP API dùng; không có bộ tính riêng cho AI.
4. Lượt 2 nhận facts rút gọn, không nhận toàn bộ timeline; trả ExplainPlan gồm candidate_id, lý do và fact_ids.
5. Backend kiểm tra đúng phương án **điểm + ngày**, đúng điều kiện vi phạm và đúng kết luận. Sai thì dùng mẫu, không gọi lượt thứ ba.

Ví dụ có quyền tìm ngày: “Cho phép đổi ngày hạ cánh trong khoảng 2026-11-17T00:00:00Z đến trước 2026-11-24T00:00:00Z, giữ phần cứng và đổi điểm trong vùng này; ưu tiên có nhiều nắng.”

Chỉ nói “lùi ba ngày” vẫn giữ một ngày chính xác; backend không tự mở rộng tìm kiếm. Mỗi phương án có candidate_id riêng để không nhầm bằng chứng giữa hai ngày tại cùng một điểm. Đối với yêu cầu ngày cố định, các fact ID cũ theo site vẫn được giữ.

## Chạy và kiểm thử

Từ G:\My Drive\H1\HOSA:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8001 --reload --reload-dir backend/app
.\.venv\Scripts\python.exe -m pytest tests/assistant tests/planning -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

Mở http://127.0.0.1:8001/docs. Cấu hình OpenRouter trong .env được giữ nguyên; không có key trong code hoặc tài liệu. Các kiểm thử offline kiểm tra được API, thuật toán, dữ liệu thật, lỗi và cấu trúc nhưng không thay thế đánh giá LLM thật.

Các test mới kiểm tra: số đọc CSV và số lần tải chi tiết được giới hạn; cửa sổ không chồng lấn; missing coverage; so sánh không lệch API cũ; khoảng hạng chồng lấn không có tính bắc cầu; dữ liệu đổi; giải thích sai điều kiện; hai ngày cùng site; draft lỗi không kẹt vĩnh viễn; ghi file đồng thời.

Ca cũ yêu cầu raw DEM Site01 vẫn cần cài dữ liệu gốc; bộ planning/assistant dùng sản phẩm đã xử lý hiện có. Không tạo raster giả để làm xanh test.

## Nguồn mã đã đối chiếu

- [PolarWindow metrics](https://github.com/MdAhbab/PolarWindow/blob/main/backend/app/core/metrics.py), blob aa5b81ab0f1a57d591a458fb9e160de3c597bc54.
- [PolarWindow compare_service](https://github.com/MdAhbab/PolarWindow/blob/main/backend/app/services/compare_service.py), blob 6ebbe884987e49f10e27ec61a5d02cf3202a91d9.
- [PolarWindow window routes](https://github.com/MdAhbab/PolarWindow/blob/main/backend/app/api/v1/routes/windows.py), blob dee47ab4ab05a95554d3b092a986fc7e383e0903.
- [BroBYW finder](https://github.com/BroBYW/CLPS-Lunar-Mission-Website/blob/main/web/src/lib/finder.ts), blob 5b882b7e529dbebf068c08d041842806fd5e9b28.
- [BroBYW metrics](https://github.com/BroBYW/CLPS-Lunar-Mission-Website/blob/main/web/src/lib/metrics.ts), blob e0767a361af22c4b3391277c90e4011ac94d0ca6.

Ngày rà soát: 10/11/2026. Việc đọc mã không chứng nhận độc lập kết quả khoa học của hai repo nguồn.


## Kết quả xác minh cuối

- Planning + assistant: **80 passed** (62 assistant, 18 planning).
- Toàn bộ backend: **112 passed, 1 failed, 3 skipped**. Ca lỗi là test coverage cũ yêu cầu DEM Site01 gốc chưa được cài; không thay test hoặc tạo dữ liệu giả để che lỗi.
- Các API compare/search/export được kiểm tra qua TestClient và thêm một server HTTP localhost thật; không cần LLM key để chạy planning.
- Kiểm thử LLM thật A15 với model hiện có: chưa đạt. Lần cuối trả OPENROUTER_TIMEOUT ở lượt 1; không chạy bộ tính và không gọi lượt giải thích tiếp theo. Không công bố bộ LLM thật đã pass chỉ dựa trên các fixture offline.

Báo cáo cục bộ: data/cache/assistant/backend-final-validation.xml, data/cache/assistant/live-window-search-final.json và data/cache/planning/http-smoke.json.

OpenRouter adapter gửi schema rõ ràng ngay cả ở JSON mode; báo riêng đầu ra bị cắt và schema sai, không tự retry ở lớp transport. Cấu hình thử nghiệm ban đầu dùng `OPENROUTER_TIMEOUT_SECONDS` để giới hạn tổng thời gian. Cấu hình hiện tại chỉ giới hạn thời gian thiết lập kết nối bằng `ASSISTANT_CONNECT_TIMEOUT_SECONDS`; HOSA không đặt giới hạn đọc phản hồi hay giới hạn tổng thời gian. `OPENROUTER_REASONING_ENABLED` là tùy chọn; bỏ qua để giữ mặc định của provider.

Chạy lại ca tìm ngày thật (tối đa hai lượt, không tự sửa lỗi):

```powershell
.\.venv\Scripts\python.exe scripts/assistant_eval.py --live --cases tests/fixtures/assistant/search_prompts.json --limit 1
```

Khi parse yêu cầu làm rõ, response có cả patch để người dùng xem các trường model đã đề xuất. patch là đề xuất; chỉ spec đã kiểm tra và được xác nhận mới được chạy.

Tài liệu provider đã đối chiếu: [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs), [reasoning controls và token budget](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
