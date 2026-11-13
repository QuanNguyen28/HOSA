# HOSA · LunarSight

HOSA phân tích chiếu sáng Mặt Trời và đường nhìn hình học tới Trái Đất tại cực nam Mặt Trăng, dùng địa hình NASA LOLA và ephemeris SPICE/JPL. Giao diện gồm Explore, Compare, Best dates và Assistant; số liệu và kết luận do backend tính.

Hướng dẫn này dành cho nhánh **`feat/merge-fe-be`**, chạy trên Linux/macOS hoặc WSL bằng Bash. Các lệnh đều chạy tại **thư mục gốc repo**, trừ khi có ghi khác.

## 1. Yêu cầu và tải source

Cần Git, Make, curl, **Python 3.11+**, **Node.js 22.12+** và **npm 10.5.1+**. `frontend/.nvmrc` chọn Node 22. Nếu máy đã có nvm, có thể dùng `nvm install 22` và `nvm use 22`.

```bash
git clone --branch feat/merge-fe-be https://github.com/QuanNguyen28/HOSA.git
cd HOSA
python3 --version
node --version
npm --version
```

Nếu đã có repo, chuyển sang nhánh này và cập nhật khi working tree sạch:

```bash
git switch feat/merge-fe-be
git pull --ff-only
```

Kết nối mạng cần cho cài dependency, tải DEM/kernel lần đầu và chat LLM nếu bật. Phép tính `solar_disc` dùng kernel cục bộ sau khi chuẩn bị xong.

## 2. Cài dependency và tạo cấu hình

```bash
make backend-install
make frontend-install
# Giữ nguyên .env nếu máy đã có cấu hình riêng.
test -f .env || cp .env.example .env
```

`backend-install` tạo `backend/.venv` và cài backend cùng dependency kiểm thử; `frontend-install` chạy `npm ci` theo lockfile. Không cần activate virtualenv nếu dùng các lệnh bên dưới.

Nếu `python3 -m venv` báo thiếu `ensurepip` trên Ubuntu/Debian, cài gói `python3-venv` phù hợp với phiên bản Python rồi chạy lại. Không cần cài trợ lý LLM để dùng Explore hay API tính toán. Giữ `ASSISTANT_ENABLED=false` khi chỉ kiểm tra backend.

## 3. Chuẩn bị dữ liệu

Có ba lớp dữ liệu khác nhau; clone source không đồng nghĩa đã có cache metrics 2000–2100.

| Thành phần | Nằm ở đâu | Có sẵn trong Git? | Cách chuẩn bị |
|---|---|---|---|
| Horizon và mesh cho 19 điểm mặc định + 4 điểm cũ | `data/processed/site-precompute/v1/` | Có, cả manifest và blobs | Dùng nguyên gói; chỉ rebuild khi đổi nguồn/thuật toán |
| Kernel thiên văn chính thức và bảng vector dùng chung | `data/cache/shared-ephemeris/` | Không | `make ephemeris-prepare`; bảng vector được sinh khi cần |
| Metrics và chart cho 2000–2100, viewer 2/10/20/30 m | `data/cache/point-analysis/prepared-metrics/` | Không | `make metrics-century-prepare` hoặc chép bộ cache tương thích |
| DEM NASA gốc và receipt | `data/raw/nasa/` | Không | `scripts/prepare_point_data.py` |

### 3.1. Cài kernel SPICE — cần cho chế độ solar-disc

```bash
make ephemeris-prepare
```

Lệnh tải kernel chính thức NAIF/JPL và lưu receipt/checksum. Có thể chạy lại để kiểm tra và dùng lại file đã cài. Kernel được kiểm tra coverage thật; backend không kẹp ngày ngoài coverage về ngày đầu/cuối.

### 3.2. Chuẩn bị metrics và chart cho toàn bộ 2000–2100

```bash
make metrics-century-prepare
```

Lệnh tính trước **19 tọa độ mặc định**, lần lượt **panel + antenna cùng ở 2, 10, 20 và 30 m**, từ `2000-01-01T00:00:00Z` đến **trước** `2101-01-01T00:00:00Z`, bao gồm toàn bộ năm 2100. Gói horizon có sẵn trong Git đủ để chuẩn bị các điểm này; không cần tải lại DEM chỉ để build metrics mặc định.

Nếu đang dùng gói địa hình cũ chưa có 30 m, cài đúng DEM gốc rồi chạy `make viewer-horizons-prepare` trước. Chi tiết và lệnh kiểm chứng: [viewer-height-precompute.md](docs/decisions/viewer-height-precompute.md).

Pipeline dùng lưới vật lý 5 phút, tạo checkpoint từng năm rồi ghép chỉ mục. Chạy lại sẽ tiếp tục các phần tương thích đã hoàn tất. Gói được công bố khi một tọa độ đã đủ toàn khoảng. Thời gian chuẩn bị phụ thuộc máy; đây là bước làm một lần trước khi phục vụ người dùng.

Cache được tách theo tọa độ và cặp độ cao, tổng cộng **76 cấu hình**. Bộ 76 cấu hình đã kiểm chứng dùng khoảng **1,76 GiB** chỉ mục tổng hợp và checkpoint năm; cache 20 m trước đây của các điểm cũ có thể vẫn nằm cạnh chúng. Dung lượng này chưa gồm kernel, bảng vector và các cache khác. Báo cáo của lần chạy được ghi vào `docs/validation/lunarsight/viewer-metrics-build.json`.

Nếu muốn thử một điểm trước hoặc giảm số process trên máy ít tài nguyên:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_long_range_metrics.py \
  --sites haworth --viewer-heights 2 10 20 30 --workers 1 \
  --report /tmp/hosa-haworth-century-build.json
```

Lệnh trên chỉ chuẩn bị Haworth ở bốn mức viewer. Chạy `make metrics-century-prepare` sau đó để hoàn tất các điểm còn lại. Mốc 2000–2100 là phạm vi **đã chuẩn bị nhanh**, không phải giới hạn thời lượng của API.

### 3.3. Cài DEM để phân tích tọa độ/độ cao ngoài gói có sẵn

```bash
backend/.venv/bin/python scripts/prepare_point_data.py
# Kiểm tra lại file và receipt đã cài, không tải mạng:
backend/.venv/bin/python scripts/prepare_point_data.py --offline
```

Mặc định tải DEM Site01/Site04 5 m cùng DEM vùng 80 m và 240 m, khoảng 0,5 GB. Điểm bất kỳ vẫn phải nằm trong coverage nguồn đã cài. Chỉ có mesh hiển thị không chứng minh đủ dữ liệu để kết luận khoa học.

Không cần `make data-acquire` để chạy MVP: đó là luồng tải bộ full-product rộng hơn. Khi thay dữ liệu NASA hoặc thuật toán horizon, cài nguồn đã xác minh rồi rebuild gói địa hình, sau đó tạo lại metrics tương ứng:

```bash
make precompute-catalog
make metrics-century-prepare
```

### 3.4. Tùy chọn: chuẩn bị chuỗi native cho Analyze

Cache cả thế kỷ ở bước 3.2 phục vụ metrics/chart; nó không lưu toàn bộ timeline native. Nếu thường đánh giá nhiệm vụ trong 2026–2028, có thể chuẩn bị thêm chuỗi vật lý của 19 điểm mặc định, thiết bị 20 m:

```bash
make physics-prepare
# Chỉ cần nếu có chuỗi vật lý cũ chưa được lập chỉ mục:
make metrics-prepare
```

Bước này tốn thêm dung lượng, không bắt buộc để gọi metrics cả thế kỷ và không thay validation theo từng request. Script `scripts/prepare_physical_series.py --help` có tùy chọn site, khoảng ngày, hardware và số worker.

Để chuẩn bị cả bằng chứng validation cho một khoảng nhiệm vụ cụ thể, dùng schema request hiện có:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_validation_evidence.py \
  --request docs/examples/point-site04-evaluation-request.json \
  --all-refinements --report /tmp/hosa-site04-validation-prepared.json
```

Cache này giữ số liệu so sánh và bằng chứng, không giữ PASS/FAIL theo ngưỡng. Đổi requirement trong cùng tọa độ, phần cứng và khoảng ngày sẽ kiểm tra lại từ bằng chứng đã có. Nó tách biệt với gói metrics 2000–2100; không có nghĩa mọi khoảng trong cả thế kỷ đã được validation trước. Xem [thiết kế và kiểm chứng cache validation](docs/decisions/validation-evidence-and-temporal-confirmation.md).

## 4. Khởi động backend và frontend

Mở hai terminal ở repo root.

**Terminal 1 — backend:**

```bash
make backend-run
```

Backend chạy tại `http://127.0.0.1:8000`, có reload cho phát triển.

**Terminal 2 — frontend:**

```bash
make frontend-run
```

Mở [Moon Explorer](http://127.0.0.1:5173). Vite chuyển tiếp `/api` tới backend cổng 8000. Kiểm tra:

```bash
curl --fail http://127.0.0.1:8000/api/health
```

Kết quả: `{"status":"ok","service":"hosa-api","version":"0.1.0"}`. Schema tương tác ở [Swagger UI](http://127.0.0.1:8000/docs), schema JSON ở `/openapi.json`.

Nếu cần dùng đúng cặp cổng **8001/5174** như phiên thử nghiệm hiện tại, thay hai lệnh chạy bằng:

```bash
# Terminal 1
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 8001
```

```bash
# Terminal 2
LUNARSIGHT_BACKEND_URL=http://127.0.0.1:8001 \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Mở [bản cổng 5174](http://127.0.0.1:5174). `LUNARSIGHT_BACKEND_URL` là biến của tiến trình Vite; cần khởi động lại Vite sau khi đổi. Các request mẫu bên dưới mặc định dùng cổng 8000; đổi thành 8001 nếu chạy cấu hình này.

## 5. Gọi API trực tiếp, không qua chat

### 5.1. Request metrics và chart cho toàn khoảng 2000–2100

File dùng ngay: [point-metrics-2000-2100-request.json](docs/examples/point-metrics-2000-2100-request.json).

```json
{
  "site_id": "Site04_P1",
  "illumination_model": "solar_disc",
  "start_utc": "2000-01-01T00:00:00Z",
  "end_utc": "2101-01-01T00:00:00Z",
  "panel_height_m": 20,
  "antenna_height_m": 20
}
```

Sau bước 3.2 và khi backend đang chạy:

```bash
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/lunar/point/metrics \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-metrics-2000-2100-request.json \
  -o /tmp/hosa-metrics.json
```

Đọc phần chính của response mà không in hàng trăm cột chart:

```bash
backend/.venv/bin/python - /tmp/hosa-metrics.json <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print(json.dumps({key: r[key] for key in (
    "evaluation_status", "decision", "metrics_hours", "joint_hours",
    "availability_fraction", "evaluation_stages", "timeline_transport"
)}, indent=2, ensure_ascii=False))
print("Chart bins:", len(r["timeline"]))
PY
```

Kết quả mong đợi: `evaluation_status="pending"`, `decision=null`, các bước đánh giá `not_started`, `execution.metrics_index_hit=true`, và tối đa **800 cột tổng hợp chứa cả Sun/Earth/Joint** trong `timeline`. Endpoint chỉ đọc chỉ mục, không tạo job validation. Nhãn tương ứng trên UI là **METRICS READY**.

Đổi `site_id` sang một ID trong `manifests/compare-sites.json`, hoặc `Site01_P1`. Cũng có thể thay `site_id` bằng cặp `latitude_deg`/`longitude_e_deg`; không gửi cả hai cách chọn điểm cùng lúc. Chỉ tọa độ khớp chính xác gói đã chuẩn bị mới có đường đọc nhanh này.

### 5.2. Request đánh giá requirements và validation

File dùng ngay: [point-site04-evaluation-request.json](docs/examples/point-site04-evaluation-request.json). Ví dụ dùng nhiệm vụ 72 giờ để kiểm tra luồng đánh giá, độc lập với request metrics cả thế kỷ:

```json
{
  "site_id": "Site04_P1",
  "illumination_model": "solar_disc",
  "start_utc": "2026-11-24T00:00:00Z",
  "duration_hours": 72,
  "panel_height_m": 20,
  "antenna_height_m": 20,
  "min_sunlit_fraction": 0.8,
  "evaluation_policy": "hard_first",
  "resolve_indeterminate": true
}
```

```bash
curl --fail-with-body --silent --show-error \
  'http://127.0.0.1:8000/api/lunar/point/analyze?view=display' \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-site04-evaluation-request.json \
  -o /tmp/hosa-evaluation.json
```

Đây là endpoint đồng bộ: response chỉ về khi đánh giá xong. `view=display` giới hạn chart hiển thị, không giảm lưới tính toán. Muốn chạy nền như frontend, POST cùng JSON đến `/api/lunar/point/analyses` để nhận `job_id` rồi dùng:

| Method | Endpoint | Nội dung |
|---|---|---|
| GET | `/api/lunar/point/analyses/{job_id}` | Trạng thái `queued/running/succeeded/failed`, stage, URL preview/result |
| GET | `/api/lunar/point/analyses/{job_id}/preview` | Metrics ban đầu khi đã có; có thể trả 409 trước khi sẵn sàng |
| GET | `/api/lunar/point/analyses/{job_id}/result?view=display` | Kết quả cuối và chart gọn; có thể trả 409 khi chưa hoàn tất |
| GET | `/api/lunar/point/analyses/{job_id}/interval?at_utc=2026-11-24T00:00:00Z` | Khoảng lấy mẫu gốc tại thời điểm yêu cầu, khi đã sẵn sàng |
| GET | `/api/lunar/point/analyses/{job_id}/intervals.csv` | CSV native sinh theo yêu cầu sau khi job thành công |

`hard_first` kiểm tra hard requirements trước; hard FAIL ở lưới 5 phút phải được xác nhận ở **cùng requirement trên lưới 1 phút** trước khi dừng và trả `hard_failure`. Kết quả loại sớm dùng metric/timeline 1 phút, kèm `validation.temporal_confirmation` của cả hai lưới. Nếu bất đồng hoặc chưa có hard fail được xác nhận, backend tiếp tục validation rồi soft preferences; FAIL chỉ có ở lưới 5 phút không được chốt thành loại bỏ cuối cùng. `evaluation_policy="complete"` giữ toàn bộ chẩn đoán. `resolve_indeterminate=true` cho phép kiểm tra mission-path bounds và các bước refinement đã có, không bảo đảm mọi điểm đều thành PASS/FAIL.

### 5.3. Quy tắc đầu vào và cách đọc số liệu

- Chọn **một** `site_id` hoặc **cả cặp** tọa độ. Kinh độ đông được chuẩn hóa về `[0,360)`; vĩ độ phải lớn hơn −90 và nhỏ hơn 90.
- `start_utc` và `end_utc` cần timezone rõ ràng, đúng lưới 5 phút. Dùng `duration_hours` hoặc `end_utc`; nếu gửi cả hai phải khớp. Thời lượng ít nhất 1 giờ, theo bước 5 phút, **không có giới hạn trên ở ứng dụng**; vẫn phải trong coverage nguồn và khả năng tài nguyên thực tế.
- Chiều cao panel/antenna của coordinate API là `>0` đến `30 m`. Gói địa hình của 19 điểm mặc định có `1/2/10/20/30 m`; cache metrics cả thế kỷ chuẩn bị riêng cho `2/2`, `10/10`, `20/20`, `30/30 m`. **Lander = 2 m**. Đổi viewer sẽ đổi đồng thời chiều cao panel và antenna để lấy đúng cache. Cặp độ cao khác vẫn tính được bằng Analyze khi đủ DEM, nhưng không mặc nhiên có metrics đã chuẩn bị.
- Danh sách mặc định có 19 điểm; đã bỏ `Site01_P1 · Connecting Ridge`, `Site04_P1 · Shackleton Rim`, `Example A`, `Example B`. Các ID cũ vẫn được API nhận khi chỉ định trực tiếp để giữ tương thích và các bài kiểm chứng; chúng không đồng nhất tọa độ với các điểm tên gần giống.
- Chỉ mục metrics nhanh hiện truy vấn trên biên ngày UTC đã lập chỉ mục. Khoảng có giờ đầu/cuối khác biên chỉ mục có thể trả `METRICS_NOT_PREPARED` dù vẫn nằm trong 2000–2100; dùng Analyze để tính đúng khoảng, backend không tự làm tròn.
- `min_sunlit_fraction=0.8` nghĩa là trung bình diện tích đĩa Mặt Trời nhìn thấy đạt 80%. Thấy nửa đĩa trong 100 giờ cho 50 giờ tương đương toàn đĩa. `total_sun_hours` dùng đơn vị giờ tương đương này; `total_earth_los_hours` và `joint_hours` là thời gian LOS/đồng thời nhìn thấy.
- Các cặp metric `[lower,upper]` là cận dưới/trên của mô hình lấy mẫu. `longest_dark_hours` đo khoảng không thấy phần nào của đĩa Mặt Trời; `longest_blackout_hours` đo khoảng mất Earth-centre LOS.
- `constraints.max_darkness_hours` và `constraints.max_earth_blackout_hours` là mong muốn mềm. Các tỷ lệ tối thiểu và `contact_requirements` là yêu cầu cứng khi được cung cấp.
- Trong contact requirements, `required_windows` đếm **cửa sổ LOS đủ điều kiện tách biệt**, không phải số phiên có thể chia trong một cửa sổ liên tục. Để trống nếu không cần bắt buộc số cửa sổ; ít cửa sổ không mặc nhiên xấu nếu LOS liên tục.

`timeline` tổng hợp dùng để vẽ chart; chiều cao cột là trung bình phần đĩa Sun hoặc tỷ lệ thời gian Earth/Joint nhìn thấy trong cột. Hatch thể hiện chênh lệch bounds. Không dùng cột trung bình nhiều ngày làm trạng thái tức thời. `warnings`, `scope` và các phần limitations trong provenance/validation mô tả phạm vi và hạn chế bằng chứng; không tự chúng đồng nghĩa FAIL.

Các API bổ sung: `/api/planning/compare`, `/api/planning/windows/search`, `/api/planning/results/{result_id}`. Ví dụ và CLI: [planning-cli.md](docs/demo/planning-cli.md), [backend-planning-services.md](docs/decisions/backend-planning-services.md).

## 6. Kiểm tra bằng giao diện

1. Mở **Explore → All sites**, chọn Haworth hoặc một điểm mặc định; thử lần lượt viewer **Lander / 10 m / 20 m / 30 m**.
2. Chọn **Define mission by → Target end date (UTC)**, nhập start `2000-01-01 00:00`, end `2101-01-01 00:00`.
3. Nếu cache đã chuẩn bị đúng, metrics và cả ba chart hiện với **METRICS READY**, không cần Analyze.
4. Muốn thử đánh giá, đổi sang khoảng ngắn như 72 giờ rồi bấm **Analyze point**: UI hiện tiến độ, metrics ban đầu và cuối cùng là kết luận hoặc hard failure.

Metrics sẵn không đồng nghĩa validation đã hoàn tất. Phân tích toàn bộ một thế kỷ vẫn cần tính native/refinement và nhiều tài nguyên; chỉ đường đọc metrics/chart đã được chuẩn bị nhanh. Màu ánh sáng 3D là preview; bằng chứng trạng thái hiện tại đến từ khoảng native của backend.

## 7. Bật Assistant với OpenRouter — tùy chọn

Trong `.env` ở repo root, chỉnh các dòng sau bằng cấu hình của bạn, không ghi nguyên placeholder:

```dotenv
ASSISTANT_ENABLED=true
ASSISTANT_PROVIDER=openrouter
OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY
OPENROUTER_MODEL=YOUR_OPENROUTER_MODEL_ID
OPENROUTER_RESPONSE_FORMAT=json_schema
```

`.env.example` mặc định chọn NVIDIA; cần đổi rõ `ASSISTANT_PROVIDER` nếu dùng OpenRouter. Các provider backend hỗ trợ là `nvidia`, `gemini`, `openrouter`. Với OpenRouter, để trống `OPENROUTER_MAX_TOKENS` nếu không muốn đặt ngân sách output riêng. Khởi động lại backend sau khi sửa `.env`.

```bash
curl --fail http://127.0.0.1:8000/api/assistant/capabilities
```

Kiểm tra `assistant_enabled=true`, `provider="openrouter"`, `provider_configured=true`. Endpoint này chỉ kiểm tra cấu hình và capability, không gọi model hay xác nhận key còn hoạt động. Sau đó dùng tab **Assistant** hoặc nút **Ask**. Không đặt key trong frontend, biến `VITE_*` hay Git.

Chat dùng cùng engine tính toán; LLM không quyết định hay thay số liệu khoa học. Lịch sử chat dùng SQLite; cấu hình lưu trữ thêm tại [BE_LLM_RELEASE.md](docs/assistant/BE_LLM_RELEASE.md) và [assistant-terminal.md](docs/demo/assistant-terminal.md). Hướng dẫn setup này không yêu cầu chạy live LLM test.

## 8. Kiểm thử

Sau khi cài dependency, từ repo root:

```bash
make verify
```

Lệnh chạy pytest, frontend tests, TypeScript typecheck và production build. Không cần key LLM cho bộ kiểm thử thông thường. Kết quả lần kiểm chứng tính năng 2000–2100: **423 backend tests pass, 1 skip; 47 frontend tests pass; build thành công**.

Sau khi chuẩn bị đủ 19 điểm × 4 mức viewer và khởi động backend, kiểm tra HTTP và đối chiếu native trên dữ liệu thật:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_long_range_metrics.py \
  --viewer-heights 2 10 20 30 --base-url http://127.0.0.1:8000 \
  --output /tmp/hosa-viewer-metrics-http.json
```

Script kiểm tra 76 cấu hình cả thế kỷ, 228 khoảng native ở hai đầu và qua năm, năm nhuận 2000, năm không nhuận 2100, tích phân chart và từ chối khoảng ngoài gói. Mỗi mức độ cao phải có source identity riêng; tăng độ cao không được làm giảm Sun/Earth/Joint visibility trong cùng mô hình. Không tạo job phân tích hoặc gọi LLM. Báo cáo viewer mới: [HTTP/native](docs/validation/lunarsight/viewer-metrics-http.json), [horizon 30 m](docs/validation/lunarsight/viewer-horizons-build.json).

Bằng chứng bản 20 m trước đây: [build](docs/validation/lunarsight/century-metrics-build.json), [HTTP/native](docs/validation/lunarsight/century-metrics-http.json), [coverage kernel](docs/validation/lunarsight/century-kernel-coverage.json), [đối chiếu JPL](docs/validation/lunarsight/century-jpl-validation.json). JPL chỉ được đối chiếu ở các cửa sổ chọn mẫu, không phải chứng nhận liên tục toàn thế kỷ.

## 9. Đưa sang máy khác hoặc deploy

1. Clone đúng phiên bản source, cài dependency theo bước 1–2.
2. Giữ nguyên gói `data/processed/site-precompute/v1/` gồm manifest và mọi blobs tham chiếu. `HOSA_PRECOMPUTE_ROOT` có thể trỏ tới một gói đầy đủ khác nếu được export vào môi trường backend.
3. Cài kernel bằng `make ephemeris-prepare` và build metrics bằng `make metrics-century-prepare`, hoặc chép nguyên các thư mục runtime tương thích từ máy đã build:
   - `data/cache/shared-ephemeris/` — kernel **kèm receipt**, và bảng vector nếu có;
   - `data/cache/point-analysis/prepared-metrics/` — chỉ mục, receipt và `.parts/` để truy vấn ngắn nhanh/tiếp tục build;
   - `data/cache/point-analysis/validation-evidence/` cùng `physical-series/` nếu muốn dùng lại bằng chứng đánh giá đã tính;
   - `data/raw/nasa/` **kèm receipt** nếu cần tính điểm/độ cao ngoài gói.
4. Cấp persistent writable storage cho `data/cache/`; giữ SQLite nếu cần bảo toàn chat. Các cache khớp theo tọa độ, hardware, source hash và method version, không chỉ tên site.
5. Build frontend bằng `npm --prefix frontend run build`; phục vụ `frontend/dist/` bằng web server, cấu hình `/api` reverse proxy tới backend và fallback route về `index.html` cho SPA.
6. Chạy backend từ repo root, không dùng reload:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

Đây là cấu hình một process phù hợp với job manager cục bộ hiện tại. Phải thiết kế lại quản lý queue/ownership trước khi tăng nhiều worker/replica.

`LUNARSIGHT_BACKEND_URL` chỉ cấu hình proxy của Vite dev/preview; production cần reverse proxy `/api` thực sự. Có thể xem thử bản build cục bộ bằng `npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173`; đó là bước kiểm tra bản build, không thay cấu hình web server production.

**Push Git chỉ đưa source, script và báo cáo lên GitHub.** Cache 2000–2100, kernel, DEM gốc và `.env` không nằm trong commit. Thiếu bước 3 thì máy deploy mới chưa có metrics tức thì dù code giống hệt máy local.

## 10. Xử lý lỗi thường gặp

| Hiện tượng / mã lỗi | Kiểm tra và xử lý |
|---|---|
| Không gọi được backend / UI không có số liệu | Kiểm tra `/api/health`, log uvicorn và proxy Vite; tránh nhầm cặp 8000/5173 với 8001/5174 |
| `EPHEMERIS_NOT_PREPARED` | Chạy `make ephemeris-prepare` trong đúng repo đang phục vụ |
| `METRICS_NOT_PREPARED` (409) | Chưa build/chép gói, sai tọa độ/độ cao/model, ngoài band hoặc không khớp biên chỉ mục; kiểm tra tọa độ, cặp độ cao 2/2, 10/10, 20/20 hoặc 30/30 m và chạy bước 3.2, hoặc dùng Analyze |
| `DEM_NOT_INSTALLED`, `DEM_RECEIPT_MISSING` | Cài DEM theo bước 3.3 và giữ receipt bên cạnh file |
| `OUTSIDE_DEM_COVERAGE` | Tọa độ không được nguồn hiện có bao phủ; cần ingest nguồn phù hợp, không đổi nhầm sang site gần nhất |
| `OUTSIDE_EPHEMERIS_COVERAGE` | Ngoài coverage kernel thực tế; phải chuẩn bị nguồn phù hợp, không kéo dài bằng cách lặp giá trị cuối |
| `*_INTEGRITY_FAILED` | Dừng dùng artifact hỏng; đối chiếu/cài lại nguồn hoặc build lại sản phẩm đúng phiên bản, không bỏ qua checksum |
| `POINT_PREVIEW_NOT_READY`, `POINT_RESULT_NOT_READY`, `POINT_INTERVAL_NOT_READY` | Kiểm tra trạng thái job; dữ liệu tương ứng chưa sẵn sàng, tiếp tục theo dõi status |
| `INDETERMINATE` sau Analyze | Đọc `validation.reason_codes`, `resolution`, bounds và nguồn; có thể thiếu dữ liệu hoặc chưa vượt gate. Bật `resolve_indeterminate` nếu phù hợp; không tự đổi nhãn |
| Assistant disabled / `OPENROUTER_NOT_CONFIGURED` | Kiểm tra `.env` repo root, enable/provider/key/model rồi restart backend; kiểm tra capabilities trước khi gọi model |
| Cổng đã được dùng | Dừng đúng tiến trình cũ hoặc dùng cấu hình cổng thay thế ở bước 4; không chạy hai backend cùng quản lý một job store |

## 11. Cấu trúc và tài liệu kỹ thuật

```text
backend/app/mission/          Schema, metrics và chính sách quyết định chung
backend/app/point_analysis/   Tính theo tọa độ, cache, metrics index và jobs
backend/app/planning/         Compare, tìm cửa sổ, xếp hạng và export
backend/app/assistant/        Provider LLM, chat, retrieval và lưu trạng thái
backend/app/precompute/       Đọc gói horizon/mesh đã xác minh
frontend/src/figma/           Giao diện tích hợp hiện tại
frontend/src/mvp/             API client và contract dùng bởi giao diện
manifests/                    Catalog, nguồn dữ liệu và cấu hình
scripts/                      Cài dữ liệu, precompute và kiểm chứng thực tế
tests/                        Kiểm thử backend và khoa học
```

- [Metrics và chart 2000–2100](docs/decisions/century-metrics.md), [metrics-first](docs/decisions/metrics-first.md), [progressive API](docs/decisions/progressive-point-analysis.md).
- [Hard-first và physical cache](docs/decisions/hard-first-physical-series.md), [precompute địa hình](docs/decisions/catalog-precompute.md), [solar-disc và shared ephemeris](docs/decisions/solar-disc-mean-and-shared-ephemeris.md).
- [Pipeline dữ liệu và validation](docs/validation/lunarsight/README.md), [release checklist](docs/release-checklist.md), [handover](docs/handover/release-handover.md).

Các API snapshot **legacy** `/api/scenarios`, `/api/analyze`, `/api/sites/{site_id}/profile` và `/api/results/{result_id}/export` vẫn giữ scenario `south_pole_demo_v1` với hai điểm P1, nhiệm vụ 72 giờ và lưới bắt đầu 15 phút. Chúng không đại diện cho phạm vi coordinate API mới và không dùng để gọi metrics 2000–2100. Một số tài liệu nghiệm thu cũ giữ cấu hình tại thời điểm phát hành; ưu tiên README này và schema `/docs` cho cách chạy nhánh hiện tại.

Kết quả còn `PROVISIONAL`: đây là mô hình chiếu sáng và Earth-centre LOS có lấy mẫu, chưa phải mô hình điện/nhiệt, RF link budget hay chứng nhận hạ cánh. Precompute tăng tốc đọc số liệu, không tự làm một nhiệm vụ thành PASS. Không commit credential, DEM lớn hoặc cache cá nhân; mọi dữ liệu khoa học cần provenance, đơn vị và checksum.
