# Hai request ngoài Site01/Site04: PASS và FAIL

Báo cáo lịch sử cho nhiệm vụ 6 giờ; các file `point-analysis-outside-pass/fail-request.json` hiện là nhiệm vụ 72 giờ, nên báo cáo này trỏ tới bản 6 giờ riêng để tái lập đúng phép thử.

Đã gọi trực tiếp `POST /api/lunar/point/analyze` bằng hai file request dưới đây. Cả hai trả HTTP 200 và `validation.passed=true`.

| Request | Tọa độ (vĩ độ, kinh độ Đông) | `decision` | Sun / Earth LOS | DEM |
|---|---|---|---|---|
| [PASS](../../examples/point-analysis-outside-6h-pass-request.json) | (-88.80771296769387, 123.81313283430084) | PASS | 6 / 6 giờ | 80 m |
| [FAIL](../../examples/point-analysis-outside-6h-fail-request.json) | (-87, 180) | FAIL | 0 / 0 giờ | 80 m |

Hai điểm đều ngoài footprint của cả hai DEM cục bộ Site01 và Site04. Điểm PASS cách hai điểm danh mục lần lượt khoảng 42,32 và 35,60 km; điểm FAIL cách khoảng 79,36 và 84,90 km. Đây là cặp được chọn sau khi thử nhiều điểm để kiểm chứng hai kết quả, không phải mẫu ngẫu nhiên đại diện cho toàn vùng.

Hai request chỉ khác tọa độ. Cấu hình chung: bắt đầu `2026-11-24T00:00:00Z`, nhiệm vụ 6 giờ, panel và antenna **cao 20 m**, yêu cầu chiếu sáng ít nhất 80%; có ít nhất một cửa sổ đủ 5 phút setup + 30 phút liên lạc và hoàn tất phiên đầu trong 120 phút. Không đổi ngưỡng kiểm định để đạt PASS.

PASS có một cửa sổ Earth LOS liên tục 360 phút, còn 355 phút sau setup. FAIL không có cửa sổ nào và không đạt yêu cầu chiếu sáng. Cả hai đều đạt tiêu chí phụ darkness <=12 giờ và blackout <=6 giờ; các tiêu chí phụ không đảo ngược FAIL của yêu cầu cứng.

Đã kiểm tra seam, bước góc 0,25° so với 0,125°, bán kính 400 so với 300 km và JPL 5 phút so với 1 phút. Sai lệch góc lớn nhất lần lượt khoảng 0,02999° và 0,01679°, đều dưới ngưỡng tạm thời 0,1°. Các kiểm tra hiện tại đạt không đồng nghĩa chứng nhận vận hành: đây vẫn là mô hình hình học lấy mẫu, ngưỡng PROVISIONAL, chưa có mô hình RF/điện/nhiệt.

Chạy từ thư mục gốc repository khi backend đang mở ở cổng 8000:

```bash
curl --fail-with-body -sS http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-outside-6h-pass-request.json \
  -o /tmp/point-pass-response.json

curl --fail-with-body -sS http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-outside-6h-fail-request.json \
  -o /tmp/point-fail-response.json
```

Đối chiếu result ID, số liệu và bằng chứng tại [outside-sites-acceptance.json](outside-sites-acceptance.json). Kết quả đầy đủ được lưu trong cache cục bộ tại các đường dẫn ghi trong file bằng chứng. Các lần gọi API kiểm tra lại trả đúng cùng result ID; chúng tái sử dụng cache kết quả có cùng đầu vào, checksum nguồn và phiên bản thuật toán.

Trong quá trình kiểm chứng đã sửa lỗi ghép biên sensitivity: một biên không được ghép lặp với nhiều biên phía còn lại, và phải giữ thứ tự thời gian. `sensitivity_version=ordered-events-1.0` được đưa vào định danh cache để tránh dùng lại quyết định theo cách ghép cũ. Bộ hồi quy science, point analysis, contact windows, planning và assistant đạt **217 test**.

Xem [hướng dẫn đọc response](../../demo/point-response-guide-vi.md) để phân biệt window/session, PASS/FAIL/INDETERMINATE và các metadata.
