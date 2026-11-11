# Nghiệm thu pipeline tọa độ — 10/11/2026

Pipeline đã được gọi qua HTTP bằng FastAPI TestClient (POST job → GET status → GET result), dùng bốn DEM NASA tải thật và response JPL thật. Sau đó đã khởi động Uvicorn trên cổng local tạm và gọi HTTP socket thật: POST trả 202, GET result trả 200, cache horizon/result được tái sử dụng; server thử nghiệm đã được dừng. Không dùng fixture tổng hợp trong hai lượt nghiệm thu này. Đây là nghiệm thu luồng xử lý và provenance; **không phải chứng nhận khoa học PASS cho hai tọa độ**.

## Dữ liệu đã cài

| Dataset | Bytes | SHA-256 |
|---|---:|---|
| Site01_dem | 40,980,810 | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| Site04_dem | 40,980,806 | `38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758` |
| dem80 | 189,158,392 | `82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a` |
| dem240 | 218,961,039 | `3f9663257b63022f2b0d5a623482ff3cadddceb91594a4e4ca14a94d8cec8b34` |

Nguồn/receipt nằm cạnh các file tại `data/raw/nasa`. Chạy `backend/.venv/bin/python scripts/prepare_point_data.py --offline` đã xác nhận cache đúng byte count và digest cả bốn dataset. Có dùng byte ranges song song cho hai raster vùng rộng; digest toàn file khớp receipt NASA đã lưu. Không thay manifest nguồn hay snapshot P1 bằng dữ liệu tổng hợp.

## Hai tọa độ ngoài catalog P1

Cả hai bắt đầu `2026-11-17T00:00:00Z`, panel 1 m, antenna 2 m, yêu cầu cứng Sun/Earth tối thiểu 0,8; ngưỡng tối/mất LOS là ưu tiên mềm.

| Tọa độ (lat, lon east) | DEM observer | Thời lượng | Sun hours [L,U] | Earth LOS hours [L,U] | Tối dài nhất [L,U] | Mất LOS dài nhất [L,U] | Quyết định có gate |
|---|---|---:|---|---|---|---|---|
| (-89.439, 222.905) | Site01_dem, 5 m | 72 h | [72,72] | [72,72] | [0,0] | [0,0] | INDETERMINATE |
| (-85, 0) | dem80, 80 m | 1 h | [0,0] | [0,0] | [1,1] | [1,1] | INDETERMINATE |

Các số trên là **metric của mô hình lấy mẫu**, không phải cận bảo đảm cho điều kiện liên tục thực tế.

- Điểm thứ nhất: ENU reference kiểm tra 170 blocker/height; sai khác độ cao góc ≤1,6e-9°. Cả bốn kiểm tra seam đạt. Coverage terrain/ephemeris đầy đủ. Tuy nhiên, sai khác góc 0,25/0,125° ở height 1 m đạt khoảng 0,58422°, vượt ngưỡng provisional 0,1°; gate giữ INDETERMINATE mặc dù metric thời lượng không đổi. Radius 400/300 km và time 5/1 phút đạt.
- Điểm thứ hai: kết quả tính được bằng DEM vùng rộng, không chuyển sang Site01/Site04. Kiểm tra seam chưa đạt tỷ lệ overlap 90% quanh đường chuyển 80/240 m; kiểm tra góc cũng chưa đạt. Không công bố FAIL khoa học chỉ từ metric exploratory, dù nominal requirements đều FAIL.

Đã dùng hai truy vấn JPL độc lập 5/1 phút cho mỗi target/tọa độ. Điểm 72 giờ có 865/4.321 mốc cho từng target; timestamp cuối chỉ là biên. Echo `MEAN_ME (high precision)`, east-positive, lunar radius và observer geodetic đều qua parser kiểm tra. Cache horizon được tái sử dụng khi tạo lại kết quả sau thay đổi logic chuẩn hóa sai số cộng dồn.

Bằng chứng đầy đủ cục bộ (không commit raw/cache):

- `data/cache/point-analysis/acceptance-live.json`, result `291a5b2fa249dbb79509791a381f32c9e2692540a24ecee1fe5b8ed5fdccb46f`.
- `data/cache/point-analysis/acceptance-regional.json`, result `7e9c27850a7037f09bbd3775b316885373201bbd0b963d7ef13865d3d52771a9`.
- `data/cache/point-analysis/acceptance-http-socket.json` ghi lượt HTTP socket thật và `cache_hit=true`.
- Các thư mục `results`, `geometry`, `raw/horizons`, `processed/ephemeris` giữ kết quả JSON, CSV và receipt theo identity/checksum.

## Kiểm thử tự động

- Regression science + coordinate + planning + assistant: **174 passed**.
- Sau các sửa cuối về response contract/float rounding/cache: coordinate + science **42 passed**, trong đó **25 test coordinate**.
- Các test tổng hợp chỉ kiểm tra hành vi/thuật toán, không được tính là bằng chứng NASA/JPL thật. Một deprecation warning hiện có từ FastAPI TestClient/httpx không ảnh hưởng kết quả.

Hướng dẫn gọi API và giới hạn phương pháp: [coordinate-analysis-pipeline.md](../../decisions/coordinate-analysis-pipeline.md).


## API trực tiếp: case dữ liệu thật đạt gate PASS

Đã thêm `POST /api/lunar/point/analyze`, cùng schema với API job và trả số liệu HTTP 200 trong một lần gọi. Kiểm tra qua socket HTTP/Uvicorn thật, không dùng TestClient/fixture cho ca này:

- Tọa độ: (-89.439°, 222.905° east), bắt đầu `2026-11-17T00:00:00Z`, 72 giờ.
- Cấu hình riêng: **panel 2 m, antenna 2 m**. Không thay đổi ngưỡng kiểm định; khác với ca panel 1 m ở trên.
- Yêu cầu cứng Sun/Earth tối thiểu 0,8; ngưỡng tối 12 giờ/mất LOS 6 giờ vẫn là ưu tiên mềm.
- `decision=PASS`, `validation.passed=true`, terrain/ephemeris đầy đủ. Cả kiểm tra ENU, seam và ba kiểm tra độ nhạy đều đạt.
- Tổng Sun [72,72] h; Earth LOS [72,72] h; tối dài nhất [0,0] h; mất LOS dài nhất [0,0] h; joint dài nhất [72,72] h.
- Lần đầu: 13,325 giây, có tính horizon và truy vấn JPL cần thiết. Lần cache: 0,137 giây. Đây là thời gian đo tại máy hiện tại, không phải cam kết latency cho điểm khác.
- Result ID: `c1eaabbb80b1391c6202e5295d7e43527bc12b63b4cc9d7b5b642f8b0dbd010d`.
- Bằng chứng cục bộ: `data/cache/point-analysis/acceptance-direct.json` và result cache tương ứng.

Đây là **PASS của mô hình sampled/provisional theo ngưỡng hiện tại**, không phải chứng nhận điều kiện liên tục/điểm hạ cánh. Không sửa kết quả INDETERMINATE của ca panel 1 m thành PASS.

Request có thể gọi lại trực tiếp: [point-analysis-passing-request.json](../../examples/point-analysis-passing-request.json). Schema đầu vào: [point-analysis-request.schema.json](../../examples/point-analysis-request.schema.json).

Sau khi thêm endpoint trực tiếp, bộ coordinate + science đạt **44 passed** (27 coordinate, 17 science). Bao gồm test trả số liệu/validation PASS với analytic fixture, schema OpenAPI, HTTP 422 cho đầu vào sai, HTTP 429 khi bận, HTTP 503 thiếu DEM, và hồi quy API job.


## API nắng + cửa sổ Earth LOS là yêu cầu chính

Đã gọi `POST http://127.0.0.1:8000/api/lunar/point/analyze` với
`docs/examples/point-analysis-contact-request.json`, bỏ min Earth total fraction,
đặt nắng tối thiểu 0,8 và contact 30 phút + setup 5 phút, ít nhất một cửa sổ,
hoàn thành phiên trước phút 120. Mọi ngưỡng tối/mất LOS vẫn là tiêu chí phụ.

- HTTP 200, `decision=PASS`, `validation.passed=true`.
- Các khóa `min_sunlit_fraction`, `contact.min_contact_minutes`,
  `contact.required_windows`, `contact.first_contact_deadline_minutes` đều PASS.
- Một cửa sổ liên tục 4.320 phút, usable 4.315 phút sau setup; thời gian chờ đầu 0 phút.
- Result: `67216c89a5965d6c345e6a37f5e580fd624d1c4f27a9385ba46a5c7806970a2a`.
- Bằng chứng cục bộ: `data/cache/point-analysis/acceptance-contact-api.json`.
- Pipeline + contact postprocess + science: **83 passed**. Đã kiểm tra riêng tổng
  LOS dương nhưng trượt deadline, Sun FAIL dù contact PASS, soft blackout FAIL
  không loại phương án, và deadline đổi trạng thái giữa lưới 5/1 phút phải gate
  INDETERMINATE. CLI contact cũ tiếp tục qua các test regression.

Kết quả vẫn tuân thủ giới hạn sampled/PROVISIONAL đã nêu ở trên.
