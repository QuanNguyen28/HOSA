# Tính toán theo tọa độ đầu vào

API mới chạy pipeline DEM → JPL Horizons → terrain horizon → visibility → metrics cho tọa độ có DEM phủ, không tra metric của Site01/Site04 để thay cho điểm mới. Các API snapshot/planning và trợ lý chat hiện có vẫn dùng catalog P1; chúng chưa tự chuyển sang API job này.

## Chuẩn bị và chạy

Từ gốc repo, dùng Python 3.11+:

```bash
backend/.venv/bin/python -m pip install -e 'backend[test]'
backend/.venv/bin/python scripts/prepare_point_data.py
```

Lệnh tải Site01/Site04 DEM 5 m, DEM 80 m và 240 m chính thức của NASA (~490 MB), lưu vào `data/raw/nasa` cùng receipt. Nó kiểm tra dung lượng đĩa, chữ ký TIFF, kích thước và SHA-256; cache có receipt không hợp lệ bị từ chối. API cũng nhận các vị trí `data/raw/Site01`, `data/raw/Site04`, `data/raw/global` hiện có. Không tự tải raster lớn trong request HTTP.

## API trực tiếp — một request trả thẳng số liệu

Khởi động lại backend sau khi cập nhật code. Endpoint đồng bộ nhận `PointAnalysisRequest`, trả `PointAnalysisResult` ngay trong response HTTP 200:

```bash
curl --max-time 600 -X POST http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-passing-request.json
```

Request mẫu này dùng tọa độ (-89.439, 222.905), ngày 17/11/2026 UTC, 72 giờ, panel **2 m**, antenna **2 m**, yêu cầu Sun/Earth tối thiểu 0,8. Đây là cấu hình riêng, khác mặc định panel 1 m. Lần đầu tính một điểm có thể mất vài phút; kết quả đã cache nhanh hơn. HTTP 429 `POINT_ANALYSIS_BUSY` nếu worker khác đang giữ khóa tính; HTTP 422 cho schema không hợp lệ. Không tạo job hoặc yêu cầu poll trạng thái.

Schema có sẵn trong Swagger `/docs`, OpenAPI `/openapi.json` và hai file độc lập:

- [JSON Schema đầu vào](../examples/point-analysis-request.schema.json).
- [JSON Schema đầu ra](../examples/point-analysis-response.schema.json).

## Yêu cầu chính: nắng + cửa sổ Earth LOS

`POST /api/lunar/point/analyze` nhận thêm `contact_requirements`. Request đã gọi thật và đạt gate được lưu ở [point-analysis-contact-request.json](../examples/point-analysis-contact-request.json):

```bash
curl --max-time 600 http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-contact-request.json
```

- `min_sunlit_fraction=0.8`: yêu cầu cứng nắng tối thiểu 57,6 giờ trong nhiệm vụ 72 giờ.
- `contact_requirements.min_contact_minutes=30`, `setup_minutes=5`: có cửa sổ Earth-centre LOS liên tục ít nhất 35 phút, gồm setup 5 phút và sử dụng 30 phút.
- `required_windows=1`: ít nhất một cửa sổ riêng biệt đạt độ dài đó trong toàn nhiệm vụ; không chia một cửa sổ dài thành nhiều cửa sổ.
- `first_contact_deadline_minutes=120`: phải hoàn thành setup và phiên đủ dài trước hoặc đúng phút 120, không chỉ bắt đầu trước deadline.
- `constraints.max_darkness_hours=12`, `max_earth_blackout_hours=6`: tiêu chí phụ; FAIL ở đây không loại một phương án đáp ứng yêu cầu cứng.
- Bỏ `min_earth_los_fraction` để tổng Earth LOS chỉ là metric bổ sung. Trường này vẫn được hỗ trợ nếu một client chủ động muốn thêm yêu cầu cứng về tổng LOS.

Response `constraint_checks` gộp yêu cầu nắng và các khóa `contact.*`; `decision`/`nominal_sampled_decision` là kết luận chung. `soft_constraint_checks` tách riêng tiêu chí phụ. `contact_analysis` chứa danh sách cửa sổ, metric, unknown và kiểm tra contact chi tiết, sử dụng cùng module standard-library với CLI `scripts/contact_windows.py`.

Kiểm định độ nhạy được chạy lại với các yêu cầu contact trên từng timeline biến thể, kể cả bước 1 phút. Nếu deadline đổi PASS/FAIL giữa các lưới, quyết định chung phải INDETERMINATE dù tổng giờ chỉ chênh dưới ngưỡng thời lượng. Không thay ngưỡng kiểm định hay thuật toán DEM/Horizons để tạo ca PASS.

Các con số 80%, 30/5/120 phút là ví dụ, không phải ngưỡng NASA bắt buộc. Đây là cửa sổ nhìn thấy tâm Trái Đất, chưa phải lịch trạm mặt đất hay xác nhận RF link budget.

## API job — tùy chọn cho tác vụ dài

Chạy backend như thường lệ rồi gửi request mẫu:

```bash
curl -i -X POST http://127.0.0.1:8000/api/lunar/point/analyses \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-request.json
```

HTTP 202 trả `job_id`, `status`, `stage`; header `Location` trỏ tới trạng thái job:

```bash
curl http://127.0.0.1:8000/api/lunar/point/analyses/JOB_ID
curl http://127.0.0.1:8000/api/lunar/point/analyses/JOB_ID/result
```

Thay `JOB_ID` bằng ID thật. Khi `status=succeeded`, `result_url` chứa URL lấy kết quả. Không gọi endpoint result trước khi job xong (HTTP 409). Hàng đợi tối đa 4 job/process, một worker/process và khóa file dùng chung giữa process để tránh tính trùng/tranh cache. HTTP 429 nếu hàng đợi đầy. Lần đầu có thể kéo dài vài phút, tùy DEM/ổ đĩa và JPL. Job status tồn tại trên đĩa; job đang dở khi process dừng không tự resume, được báo `POINT_JOB_INTERRUPTED` sau khi process cũ đã kết thúc.

Có thể chạy cùng pipeline trực tiếp, không cần Uvicorn:

```bash
backend/.venv/bin/python scripts/analyze_point.py \
  --request docs/examples/point-analysis-request.json \
  --output data/cache/point-analysis/example-result.json
```

## Hợp đồng đầu vào

- `latitude_deg`: vĩ độ (-90,90); loại trừ đúng hai cực vì azimuth tại cực không xác định duy nhất trong adapter hiện tại.
- `longitude_e_deg`: kinh độ đông [-180,360], chuẩn hóa về [0,360).
- `start_utc`: ISO 8601 có múi giờ, trên lưới UTC 5 phút, năm 2000–2100. Không bị giới hạn miền thời gian snapshot P1.
- `duration_hours`: số nguyên 1–72; mặc định 72. Hai chiều cao thiết bị dương, tối đa 20 m, mặc định 1 m/2 m.
- `min_sunlit_fraction`, `min_earth_los_fraction`: yêu cầu cứng tùy chọn [0,1]. Khi không cung cấp cả hai, `decision=null`: chỉ lấy số liệu, không tự đặt điều kiện nhiệm vụ.
- `constraints.max_darkness_hours`, `max_earth_blackout_hours`: tùy chọn mềm; không thay quyết định yêu cầu cứng.
- `offline=true`: chỉ dùng cache JPL đúng tọa độ, độ cao, dữ liệu và miền thời gian. Cache không khớp trả `HORIZONS_CACHE_MISS`, không thay thế bằng ephemeris điểm gần nhất.

Coverage thực tế phụ thuộc raster đã cài. DEM khu vực không có nghĩa là phủ toàn Mặt Trăng. Không có DEM trả `DEM_NOT_INSTALLED`; điểm không được phủ trả `OUTSIDE_DEM_COVERAGE`. Thiếu một phần dữ liệu dọc horizon/ephemeris được giữ là `?`, không điền zero hoặc tự xem là nhìn thấy.

## Kết quả và provenance

Kết quả gồm:

- Tọa độ yêu cầu nguyên gốc sau chuẩn hóa kinh độ, cao độ DEM và nguồn/resolution tại observer. Cao độ lấy ở pixel đăng ký gần nhất; không tự đổi observer sang P1 hay tâm pixel.
- `metrics_hours`: cận [lower,upper] của tổng giờ Sun/Earth visible, khoảng tối liên tục dài nhất, khoảng mất Earth LOS dài nhất và khoảng đồng thời Sun/Earth visible dài nhất.
- `availability_fraction`: cận tỷ lệ Sun/Earth theo thời lượng nhiệm vụ.
- `timeline`: khoảng nửa mở [start,end), góc az/el, horizon, clearance, trạng thái V/B/? và cờ coverage. Mốc terminal chỉ làm biên, không thêm một khoảng thời gian.
- `events`: các khoảng trạng thái liên tiếp theo target; `horizons`: profile 0,25° cho các chiều cao.
- `nominal_sampled_decision`, `constraint_checks`, `soft_constraint_checks`, `decision` có gate kiểm định riêng.
- `validation`: kiểm tra XYZ→ENU độc lập, kiểm tra overlap/datum tại đường chuyển DEM theo hai phase độc lập, độ nhạy 0,25/0,125°, 400/300 km và hai truy vấn JPL độc lập 5/1 phút trên cùng miền thời gian.
- `provenance`: SHA-256/URL/frame/unit/resolution từng DEM, request JPL, raw receipt, checksum geometry, method version và định danh đầu vào. Raw Horizons, ephemeris CSV, horizon CSV và interval CSV được giữ trong cache.

Kết quả được cache theo toàn bộ request khoa học, checksum các DEM và method version. Horizon có cache riêng, độc lập ngày/ngưỡng. `offline` là chính sách truy xuất, không thay giá trị khoa học nên không thuộc khóa số liệu. Cache bị thay đổi checksum bị từ chối, không trả kết quả cũ im lặng.

## Phương pháp và giới hạn

Dùng hệ MOON_ME/DE421, bán kính tham chiếu 1.737.400 m; kiểm tra CRS/registration/scale và đối chiếu echo frame, geodetic observer, radii, UT/UTC từ JPL. Horizon dựa trên hình học cầu XYZ/ENU, không trừ độ cong hai lần. Gần DEM 5 m: quét theo footprint từng phương vị, lùi 275 m khỏi biên và tối đa 8 km, bước 2,5 m; điểm quá sát biên dùng DEM vùng rộng nếu có; tiếp đến 200 km dùng DEM 80 m (hoặc 240 m) với bước 40 m (hoặc 120 m); đến 400 km dùng DEM 240 m với bước 120 m. Nodata fallback sang nguồn thô hơn có dữ liệu, không nội suy vùng trống. Độ phân giải thật được lưu trong provenance.

Kiểm định runtime dùng ngưỡng PROVISIONAL hiện có: sai khác góc tối đa 0,1°, dịch sự kiện 5 phút, sai khác thời lượng 10 phút; overlap median ≤10 m và p95 góc ≤0,15°. Không fit datum offset. Nếu thiếu coverage, datum chưa đạt hoặc kiểm tra độ nhạy không đạt, `decision` bị gate thành `INDETERMINATE`; không công bố PASS/FAIL khoa học từ metric exploratory. `nominal_sampled_decision` vẫn ghi quyết định thô để giải thích.

Tất cả kết quả vẫn PROVISIONAL. Cận thời lượng chỉ bao phủ unknown trong mô hình lấy mẫu; chưa bao phủ đầy đủ sai số DEM, sai số liên tục theo thời gian hay vật cản giữa các ray/ngoài 400 km. Đây là visibility tâm Sun/Earth, chưa mô hình đĩa Mặt Trời, điện/nhiệt, RF link budget hay chứng nhận điểm hạ cánh. Không đưa fixture tổng hợp vào dữ liệu sản xuất.

Nguồn chính thức: [NASA PGDA 78](https://pgda.gsfc.nasa.gov/products/78), [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90), [Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html), [Horizons manual](https://ssd.jpl.nasa.gov/horizons/manual.html).

## Kiểm thử

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest tests/test_point_analysis.py tests/test_science.py -q
```

Các test API tích hợp dùng DEM/horizon/ephemeris tổng hợp có ghi rõ, trong thư mục tạm; chúng không phải bằng chứng JPL/NASA thật. Nghiệm thu với hai tọa độ và NASA/JPL thật được ghi riêng tại [coordinate-analysis-acceptance.md](../validation/lunarsight/coordinate-analysis-acceptance.md); cả hai lượt trả số liệu nhưng vẫn INDETERMINATE do gate kiểm định, không công bố khoa học PASS.
