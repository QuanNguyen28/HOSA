# Kiểm chứng bổ sung và chính sách hard FAIL

> Tài liệu này ghi lại vòng triển khai policy 1.x. Policy hiện tại 2.0 cho phép thêm các đoạn `?` nếu cận bất lợi vẫn đạt mọi hard requirement; Site04 trong bảng lịch sử bên dưới nay đã PASS cho yêu cầu Sun/Earth 80%. Xem [nhiệm vụ dài và computing](long-missions-and-compute.md) cùng `long-missions-live-report.json` để biết hành vi hiện tại.

Nhánh: `feat/merge-fe-be`. Dữ liệu kiểm thử: NASA LOLA đã kiểm tra hash và JPL Horizons thật, không dùng LLM để tạo số liệu.

## Quy tắc quyết định

- Có ít nhất một hard requirement là `FAIL` → trả `FAIL` ngay cả khi validation chưa đạt. Không cho Apply. Cảnh báo chất lượng vẫn được giữ; đây là kết luận theo mô hình mẫu, không phải xác nhận địa hình đã được kiểm chứng.
- Không có hard FAIL, nhưng bằng chứng thiếu khiến một yêu cầu chưa kết luận được → `INDETERMINATE`.
- Hard requirements đều đạt → chỉ `PASS` khi validation toàn vòng đạt hoặc kiểm chứng đường đi nhiệm vụ đạt theo chính sách bên dưới.
- Darkness/blackout preferences vẫn là tiêu chí phụ; việc chúng không đạt không tự biến nhiệm vụ thành FAIL.

Ví dụ: `total_sun_hours=[0,0]` với yêu cầu 80% là FAIL; `[0,72]` là thiếu bằng chứng và chưa thể kết luận FAIL chỉ vì cận dưới bằng 0. Nếu đồng thời một hard requirement khác đã FAIL thì quyết định chung vẫn FAIL.

Quy tắc dùng chung cho point, compare, search, contact requirements và assistant. Search không còn bỏ qua hard FAIL chỉ vì bộ lọc validation toàn vòng chưa đạt. CSV giữ cả `resolution_json` và `validation_json`.

## Ca đủ 72 giờ nắng nhưng vẫn INDETERMINATE

Bật `resolve_indeterminate: true`. API mặc định false để giữ việc tính bổ sung có chủ đích; UI mặc định bật. Có tối đa hai vòng refine, với lưới fine 0.0625° rồi 0.03125°. Các ngưỡng 0.1° / 5 phút / 10 phút giữ nguyên.

Nếu chỉ còn lỗi angular sensitivity, sau khi refine hệ thống kiểm tra thêm đúng đường đi Sun/Earth trên cả hai lưới JPL native 5/1 phút, kể cả timestamp cuối. Các kiểm tra radius, duration, event matching, trạng thái hard requirements, coverage, ENU và seam vẫn phải đạt.

Tại mỗi hướng quan sát, lấy envelope của ba profile coarse/fine/300 km. Nới envelope thêm **sai lệch horizon lớn nhất toàn vòng ở độ cao tương ứng + 0.1°**. Chỉ nhận đường đi luôn ở cùng một trạng thái V hoặc B, nằm ngoài envelope ở mọi mẫu, và độ lệch các profile trên đường đi không vượt 0.1°. Trường hợp sát horizon, đổi trạng thái hoặc thiếu mẫu không được giải quyết bằng cách này.

Đây là kiểm tra độ bền theo những cấu hình số đã tính, với ngưỡng **PROVISIONAL**. Envelope thực nghiệm không phải cận sai số vật lý DEM hoặc chứng minh không có sự kiện giữa các mẫu. Nó không chứng nhận landing safety, công suất điện, đĩa Mặt Trời hay RF.

API phân biệt rõ:

```json
{
  "decision": "PASS",
  "validation": {
    "passed": false,
    "reason_codes": ["azimuth_0.125_vs_0.0625:SENSITIVITY_FAILED"],
    "mission_path": {
      "passed": true,
      "scope": "requested_sampled_sun_and_earth_paths_only"
    }
  }
}
```

`validation.passed=false` vẫn mô tả kiểm chứng horizon toàn vòng; `mission_path.passed=true` chỉ áp dụng cho nhiệm vụ được yêu cầu. Đổi tọa độ, thời gian, phần cứng hoặc yêu cầu sẽ tạo danh tính kết quả khác và chạy lại kiểm chứng tương ứng.

## Kiểm thử dữ liệu thật

| Trường hợp | Đầu vào | Kết quả |
|---|---|---|
| Full sun, Site01_P1 | (-89.43892646479243, 222.90402192622227), 17–20/11/2026 UTC, panel 1 m / antenna 2 m, yêu cầu Sun/Earth 80% | Tắt tính bổ sung: INDETERMINATE. Bật: PASS, 72/72 giờ Sun và Earth, một vòng refine. Validation toàn vòng vẫn false. |
| Zero sun ngoài Site01/04 | (-86.61104682173548, 336.25717784632303), 24–27/11/2026 UTC, panel/antenna 20 m, yêu cầu Sun 80% và contact | FAIL, Sun/Earth 0/72 giờ, kể cả khi angular validation false; không cần refine. |
| Full sun, Site04_P1 | 17–20/11/2026 UTC, panel 1 m / antenna 2 m, yêu cầu Sun/Earth 80% | Vẫn INDETERMINATE sau hai vòng. Sun vượt envelope; Earth có mẫu chưa vượt được envelope. Không gán PASS chỉ vì số giờ nắng đã đủ. |

Ở Site01, sai lệch toàn vòng tại panel khoảng 0.55979°, nhưng độ lệch trên đường đi Sun khoảng 0.05647°. Sau khi nới envelope như trên, biên an toàn nhỏ nhất còn khoảng 0.75923° cho Sun và 0.48079° cho Earth.

Hai request có thể gọi trực tiếp:

```bash
curl -sS http://127.0.0.1:8001/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-revalidation-pass-request.json

curl -sS http://127.0.0.1:8001/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-revalidation-fail-request.json
```

Kiểm chứng lại point/compare/search/CSV, giữ nguyên input vật lý và tolerances giữa các lần gọi:

```bash
backend/.venv/bin/python scripts/verify_indeterminate_resolution.py \
  --base-url http://127.0.0.1:8001 --offline \
  --output docs/validation/lunarsight/indeterminate-resolution-live-report.json
```

`--offline` yêu cầu cache JPL khớp chính xác; bỏ tùy chọn này để fetch dữ liệu thật nếu chưa có cache. Các schema JSON trong `docs/examples` đã cập nhật field mới. Report cạnh tài liệu này lưu result IDs, metrics, cấu hình và chẩn đoán mission-path của hai ca đầu.
