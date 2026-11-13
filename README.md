# HOSA · LunarSight

HOSA phân tích chiếu sáng Mặt Trời và đường nhìn hình học tới Trái Đất tại cực nam Mặt Trăng, dựa trên địa hình NASA LOLA và ephemeris SPICE/JPL. Web gồm **Explore, Compare, Best dates và Assistant**; backend tính metrics, kiểm tra yêu cầu và trả PASS / FAIL / INDETERMINATE.

README này hướng dẫn **một máy mới** chạy nhánh **`feat/merge-fe-be`** từ đầu. Đi theo bước **1–7** để chạy web với đầy đủ cache của 19 điểm mặc định. DEM cho tọa độ mới và LLM là các bước tùy chọn ở phía sau.

Nếu đã có cache từ máy đang chạy, làm bước 1–3, chuyển cache theo [bước 11](#11-chuyển-cache-sang-máy-khác), rồi tiếp tục bước 5–7 để tiết kiệm thời gian chuẩn bị.

**Clone Git chưa mang theo cache metrics.** Gói horizon/mesh có trong Git; kernel và cache 2000–2100 phải được tạo hoặc chuyển từ máy đã chuẩn bị. Riêng các chỉ mục của 76 cấu hình chiếm khoảng **1,76 GiB**, chưa gồm dependency, kernel, bảng vector và DEM.

## 1. Cài công cụ trên máy mới

| Công cụ                | Phiên bản dùng cho hướng dẫn                                               |
| ------------------------ | -------------------------------------------------------------------------------- |
| Hệ điều hành / shell | Ubuntu 24.04, Bash; Windows dùng Ubuntu trong WSL2                              |
| Python                   | 3.11 trở lên; có thể dùng Python 3.12 của Ubuntu 24.04                     |
| Node.js                  | Nhánh 22, ít nhất 22.12                                                       |
| npm                      | Ít nhất 10.5.1                                                                 |
| Khác                    | Git, Make, curl, kết nối mạng để cài dependency và tải kernel lần đầu |

Trên Ubuntu, chạy:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates python3 python3-venv python3-pip
```

Nếu chưa có Node phù hợp, cài bằng nvm theo [hướng dẫn chính thức](https://github.com/nvm-sh/nvm#installing-and-updating):

```bash
export NVM_DIR="$HOME/.nvm"
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.41.0/install.sh -o /tmp/hosa-install-nvm.sh
bash /tmp/hosa-install-nvm.sh
. "$NVM_DIR/nvm.sh"
nvm install 22
nvm use 22
```

Kiểm tra trước khi tiếp tục:

```bash
python3 --version
node --version
npm --version
git --version
make --version
```

**Windows:** cài WSL theo [hướng dẫn Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install), mở Ubuntu rồi chạy các lệnh Bash trong README ở đó. Đặt repo trong thư mục Linux như `~/HOSA`. **macOS:** cài Git, Make, Python và Node đáp ứng bảng trên bằng công cụ của máy, rồi bắt đầu từ bước 2; block `apt` dành cho Ubuntu.

## 2. Tải đúng source

Hướng dẫn dùng `~/HOSA` làm thư mục cài. Nếu chọn đường dẫn khác, thay các lệnh `cd ~/HOSA` tương ứng.

```bash
cd ~
git clone --branch feat/merge-fe-be --single-branch https://github.com/QuanNguyen28/HOSA.git HOSA
cd ~/HOSA
git branch --show-current
```

Dòng cuối phải trả `feat/merge-fe-be`. Mọi lệnh chuẩn bị dữ liệu bên dưới chạy từ **gốc repo**, nơi có `Makefile`, `backend/`, `frontend/` và `manifests/`.

Nếu máy đã có checkout thay vì clone mới, chỉ cập nhật khi đã xử lý xong các thay đổi riêng của máy:

```bash
git switch feat/merge-fe-be
git pull --ff-only
```

## 3. Cài dependency và tạo cấu hình

```bash
cd ~/HOSA
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e 'backend[test]'
npm --prefix frontend ci
test -f .env || cp .env.example .env
backend/.venv/bin/python -m pip check
```

Không cần activate virtualenv: các lệnh dùng thẳng `backend/.venv/bin/python`. `npm ci` dùng lockfile đã commit. Hai lệnh `make backend-install` và `make frontend-install` cũng cài dependency tương ứng.

Trong lần chạy đầu, giữ `ASSISTANT_ENABLED=false` trong `.env`. Explore, tính metrics, Analyze, Compare và Best dates không cần API key LLM. Chưa cần điền key provider; không dùng `.env` của người khác.

## 4. Chuẩn bị kernel và cache tính toán

### 4.1. Thành phần nào có sẵn?

| Thành phần                                                         | Đường dẫn                                                                                  | Có trong Git?               | Máy mới cần làm gì?                                      |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------- |
| Horizon và mesh địa hình                                         | `data/processed/site-precompute/v1/`                                                         | Có, gồm manifest và blobs | Giữ nguyên cả gói                                         |
| Catalog và dữ liệu snapshot phiên bản cũ                       | `manifests/`, `data/processed/lunarsight/`, phần cache legacy được theo dõi trong Git | Có                          | Được tải cùng source                                     |
| Kernel và bảng vector dùng chung                                  | `data/cache/shared-ephemeris/`                                                               | Không                       | Chạy bước 4.2 hoặc chuyển cache ở bước 11             |
| Chỉ mục metrics/chart 2000–2100                                   | `data/cache/point-analysis/prepared-metrics/`                                                | Không                       | Chạy bước 4.3 hoặc chuyển cache ở bước 11             |
| DEM NASA gốc và receipt                                            | `data/raw/nasa/`                                                                             | Không                       | Chỉ cần tải ở bước 8 khi tính ngoài gói địa hình  |
| Bằng chứng validation, chuỗi native, kết quả và lịch sử chat | `data/cache/`                                                                                | Không                       | Backend tạo khi sử dụng; có thể giữ trên ổ persistent |

**Không cần tải lại DEM hoặc chạy `make precompute-catalog` để dùng 19 điểm mặc định ở các mức viewer đã có.** Gói trong Git đã chứa horizon cần thiết, gồm cả 30 m.

### 4.2. Cài kernel chính thức

```bash
cd ~/HOSA
make ephemeris-prepare
```

Lệnh tải các kernel NAIF/JPL, lưu receipt và kiểm tra checksum. Mạng cần ở lần tải này. Sau đó mô hình `solar_disc` tính từ kernel cục bộ; bảng vector được tạo khi cần. Nếu đã có file kernel nhưng thiếu/sai receipt, cần khắc phục đúng artifact, không bỏ qua bước kiểm tra.

### 4.3. Tạo đầy đủ cache cho 19 điểm × 4 độ cao

```bash
cd ~/HOSA
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_long_range_metrics.py \
  --viewer-heights 2 10 20 30 --workers 2 \
  --report /tmp/hosa-viewer-metrics-build.json
```

Lệnh chuẩn bị **76 cấu hình**, từ `2000-01-01T00:00:00Z` đến **trước** `2101-01-01T00:00:00Z`, tức bao gồm toàn bộ năm 2100. Mỗi cấu hình đặt **panel và antenna cùng độ cao**:

| Viewer | Panel | Antenna |
| ------ | ----: | ------: |
| Lander |   2 m |     2 m |
| 10 m   |  10 m |    10 m |
| 20 m   |  20 m |    20 m |
| 30 m   |  30 m |    30 m |

Đây là bước tốn thời gian và CPU nhất khi cài mới. Script tính trên lưới 5 phút, lưu checkpoint từng năm; một cấu hình chỉ được công bố khi đủ khoảng yêu cầu. Nếu bị ngắt, chạy lại nguyên lệnh để tiếp tục các phần còn tương thích. Dùng `--workers 1` nếu máy ít tài nguyên.

Kiểm tra kết thúc thành công:

```bash
backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('/tmp/hosa-viewer-metrics-build.json').read_text())
assert r['passed'] and len(r['records']) == r['configurations_total'] == 76
print('READY:', r['sites_total'], 'sites,', len(r['records']), 'configurations')
PY
```

Có thể dùng `make metrics-century-prepare` thay cho block build trên. Target này dùng 3 worker; nếu chọn cách này, thay đường dẫn báo cáo trong block kiểm tra bằng `docs/validation/lunarsight/viewer-metrics-build.json`.

**Muốn thử sớm một điểm:** thêm `--sites haworth` vào block build và giữ bốn độ cao. Khi đó chỉ Haworth có cache cả thế kỷ; report có 4 cấu hình, không dùng assertion 76 ở trên. Chạy lại lệnh không có `--sites` khi muốn hoàn tất 19 điểm.

Cache này chứa metrics và chart tổng hợp, **không chứa kết luận nhiệm vụ được duyệt sẵn**. Analyze vẫn kiểm tra requirements và validation theo từng request. Site01_P1, Site04_P1, Example A và Example B đã bỏ khỏi danh sách mặc định; các ID cũ vẫn được API nhận, nhưng lệnh build mặc định không chuẩn bị cache cho chúng.

## 5. Chạy backend và frontend

Mở hai terminal và giữ chúng chạy. Dùng một cặp cổng nhất quán: hướng dẫn chính là **backend 8000 / frontend 5173**.

**Terminal 1 — backend:**

```bash
cd ~/HOSA
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --port 8000 --workers 1
```

**Terminal 2 — frontend:**

```bash
cd ~/HOSA
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite chuyển `/api` tới backend 8000. `--strictPort` giúp phát hiện cổng bận thay vì tự chuyển sang một URL khác.

**Terminal 3 — kiểm tra kết nối:**

```bash
cd ~/HOSA
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:5173/api/health
```

Cả hai phải trả trạng thái `ok`, service `hosa-api`. API tương tác: [Swagger UI](http://127.0.0.1:8000/docs); schema JSON: [openapi.json](http://127.0.0.1:8000/openapi.json).

Những lần mở web sau, chạy lại hai terminal backend/frontend ở bước này. Không cần cài lại dependency hay tính lại cache nếu môi trường và nguồn tính toán vẫn tương thích. Dùng Ctrl+C trong terminal tương ứng để dừng server; cache đã ghi hợp lệ vẫn được giữ trên đĩa.

**Nếu dùng cặp 8001 / 5174**, thay hai lệnh chạy bằng:

```bash
# Terminal backend
cd ~/HOSA
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --port 8001 --workers 1
```

```bash
# Terminal frontend
cd ~/HOSA
LUNARSIGHT_BACKEND_URL=http://127.0.0.1:8001 \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Khi đó mở [http://127.0.0.1:5174](http://127.0.0.1:5174) và đổi các request mẫu từ 8000 sang 8001. `LUNARSIGHT_BACKEND_URL` cần nằm trong môi trường tiến trình Vite; sửa biến này rồi khởi động lại Vite. Cổng uvicorn được chọn bằng `--port`, không tự đổi theo `API_PORT` trong `.env`.

## 6. Kiểm tra API bằng request có sẵn

Hai file bên dưới dùng **Haworth**, thuộc đúng bộ cache mặc định ở bước 4. Không cần bật chat.

### 6.1. Metrics và cả ba chart cho toàn bộ 2000–2100

Request: [point-haworth-metrics-request.json](docs/examples/point-haworth-metrics-request.json).

```json
{
  "site_id": "haworth",
  "illumination_model": "solar_disc",
  "start_utc": "2000-01-01T00:00:00Z",
  "end_utc": "2101-01-01T00:00:00Z",
  "panel_height_m": 20,
  "antenna_height_m": 20
}
```

```bash
cd ~/HOSA
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/lunar/point/metrics \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-metrics-request.json \
  -o /tmp/hosa-metrics.json

backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('/tmp/hosa-metrics.json').read_text())
assert r['execution']['metrics_index_hit'] and r['decision'] is None
print(json.dumps({k: r[k] for k in (
    'evaluation_status', 'decision', 'metrics_hours', 'joint_hours', 'evaluation_stages'
)}, indent=2, ensure_ascii=False))
print('Chart bins:', len(r['timeline']))
PY
```

Kết quả mong đợi: `metrics_index_hit=true`, `decision=null`, `evaluation_status="pending"` và tối đa 800 cột Sun/Earth/Joint trong `timeline`. `pending` ở endpoint này nghĩa là **chưa đánh giá nhiệm vụ**; metrics/chart đã có. Endpoint không tự tạo job validation.

Đổi cả hai chiều cao sang 2, 10 hoặc 30 để thử các preset khác. Đổi `site_id` sang một trong 19 điểm đang hiện trên web, hoặc gửi cặp `latitude_deg` / `longitude_e_deg` thay cho `site_id`. Đường đọc nhanh chỉ có khi tọa độ, hardware, mô hình và khoảng ngày khớp cache đã chuẩn bị.

### 6.2. Đánh giá requirements và validation cho nhiệm vụ 72 giờ

Request: [point-haworth-evaluation-request.json](docs/examples/point-haworth-evaluation-request.json), dùng ngày 24–27/11/2026 UTC, panel/antenna 20 m và tỷ lệ đĩa Mặt Trời trung bình tối thiểu 80%.

```bash
curl --fail-with-body --silent --show-error \
  'http://127.0.0.1:8000/api/lunar/point/analyze?view=display' \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o /tmp/hosa-evaluation.json

backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('/tmp/hosa-evaluation.json').read_text())
print(json.dumps({
    'decision': r['decision'],
    'metrics_hours': r['metrics_hours'],
    'validation_passed': r['validation'].get('passed'),
    'reason_codes': r['validation'].get('reason_codes', [])
}, indent=2, ensure_ascii=False))
PY
```

Đây là request đồng bộ, chờ đánh giá xong mới trả response. `view=display` giảm kích thước chart truyền về, giữ nguyên lưới tính toán. Kết luận dựa trên dữ liệu và requirements của request; dữ liệu không đủ có thể trả INDETERMINATE.

Frontend chạy nền bằng POST cùng body tới `/api/lunar/point/analyses`. Luồng API tương ứng:

| Method | Endpoint                                                                    | Nội dung                             |
| ------ | --------------------------------------------------------------------------- | ------------------------------------- |
| POST   | `/api/lunar/point/analyses`                                               | Tạo job, nhận `job_id`            |
| GET    | `/api/lunar/point/analyses/{job_id}`                                      | Trạng thái và stage hiện tại     |
| GET    | `/api/lunar/point/analyses/{job_id}/preview`                              | Metrics ban đầu khi đã sẵn sàng |
| GET    | `/api/lunar/point/analyses/{job_id}/result?view=display`                  | Kết quả cuối và chart             |
| GET    | `/api/lunar/point/analyses/{job_id}/interval?at_utc=2026-11-24T00:00:00Z` | Khoảng native tại một thời điểm |
| GET    | `/api/lunar/point/analyses/{job_id}/intervals.csv`                        | CSV native sau khi job hoàn tất     |

Preview/result/interval có thể trả 409 khi phần tương ứng chưa sẵn sàng; xem status job trước. Schema đầu vào và response đầy đủ nằm ở `/docs` và [docs/examples](docs/examples/).

## 7. Kiểm tra trên web

1. Vào **Explore → All sites**, chọn **Haworth**. Danh sách có 19 điểm mặc định và tùy chọn nhập tọa độ riêng.
2. Giữ start `2026-11-24 00:00 UTC`, mission 72 giờ. Thử **Lander / 10 m / 20 m / 30 m**: cả panel và antenna phải đổi theo bảng ở bước 4.
3. Sau khi đọc cache, metrics và ba chart Sun/Earth/Joint hiện với trạng thái **METRICS READY**, chưa cần bấm Analyze.
4. Để thử dài hạn, chọn **Define mission by → Target end date (UTC)**, start `2000-01-01 00:00`, end `2101-01-01 00:00`. Metrics/chart vẫn dùng chỉ mục đã chuẩn bị.
5. Đổi lại nhiệm vụ ngắn 72 giờ rồi bấm **Analyze point** để thử requirements/validation. Compare và Best dates cũng tính đánh giá theo request, không được preapprove bởi cache metrics.

Nhãn có thể được dịch nếu đang dùng bản giao diện đa ngôn ngữ. Màu chiếu sáng 3D là preview; metrics và quyết định lấy từ backend. Chart cả thế kỷ là trung bình theo cột hiển thị, không phải trạng thái tức thời tại từng phút.

## 8. Tùy chọn: phân tích tọa độ hoặc độ cao ngoài gói

Chỉ cần bước này nếu muốn tính điểm bất kỳ, chiều cao khác preset, hoặc rebuild địa hình theo dữ liệu mới:

```bash
cd ~/HOSA
backend/.venv/bin/python scripts/prepare_point_data.py
# Những lần sau: kiểm tra dữ liệu và receipt đã có, không tải mạng.
backend/.venv/bin/python scripts/prepare_point_data.py --offline
```

Script chuẩn bị DEM Site01/Site04 5 m và DEM vùng 80/240 m, kèm receipt. Điểm phải nằm trong coverage thực của nguồn đã cài. API không tự gán tọa độ bất kỳ về điểm mặc định gần nhất; mesh hiển thị không tự chứng minh đủ coverage cho kết luận khoa học.

Sau khi đổi nguồn hoặc thuật toán horizon, rebuild địa hình rồi metrics tương ứng:

```bash
make precompute-catalog
make metrics-century-prepare
```

`make viewer-horizons-prepare` chỉ dùng để bổ sung 30 m vào một gói địa hình cũ còn tương thích, khi đã cài đúng DEM gốc. Clone mới của nhánh hiện tại đã có các profile này. `make data-acquire` phục vụ bộ full-product rộng hơn, không bắt buộc cho luồng cài MVP ở trên.

Có thể chuẩn bị validation cho **một cửa sổ nhiệm vụ cụ thể**:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_validation_evidence.py \
  --request docs/examples/point-haworth-evaluation-request.json \
  --all-refinements --report /tmp/hosa-haworth-validation.json
```

Bước này lưu bằng chứng số liệu để tái sử dụng khi đổi requirements; không lưu PASS/FAIL được duyệt sẵn và không validation toàn thế kỷ. Chuỗi native có thể chuẩn bị thêm bằng `scripts/prepare_physical_series.py`; đây cũng là bước tùy chọn, tách biệt với cache metrics/chart.

## 9. Tùy chọn: bật Assistant qua OpenRouter

Mở `.env` ở gốc repo, sửa các biến sau bằng key và model của bạn:

```dotenv
ASSISTANT_ENABLED=true
ASSISTANT_PROVIDER=openrouter
OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY
OPENROUTER_MODEL=YOUR_OPENROUTER_MODEL_ID
OPENROUTER_RESPONSE_FORMAT=json_schema
```

`.env.example` chọn provider NVIDIA; muốn dùng OpenRouter phải đổi rõ `ASSISTANT_PROVIDER`. Có thể để `OPENROUTER_MAX_TOKENS` không được khai báo nếu không đặt ngân sách output riêng. Key chỉ nằm ở backend, không đưa vào frontend, `VITE_*` hoặc Git.

Dừng backend bằng Ctrl+C và chạy lại lệnh ở bước 5 để nạp cấu hình. Kiểm tra mà không gọi model:

```bash
curl --fail http://127.0.0.1:8000/api/assistant/capabilities
```

Mong đợi `assistant_enabled=true`, `provider="openrouter"`, `provider_configured=true`. Đây là kiểm tra cấu hình, không xác nhận key còn hoạt động hay model gọi thành công. Sau đó có thể dùng **Assistant / Ask** trên web. README không yêu cầu live LLM test.

Lịch sử chat mặc định ở `data/cache/assistant/chat.sqlite3`; giữ file này nếu muốn giữ phiên qua lần khởi động sau. Xem thêm [hướng dẫn Assistant](docs/assistant/BE_LLM_RELEASE.md).

## 10. Kiểm thử sau khi cài

Từ gốc repo, chạy bộ kiểm thử và build thông thường:

```bash
cd ~/HOSA
make verify
```

Lệnh chạy backend tests, frontend tests, TypeScript và production build. Không cần API key LLM cho bộ kiểm thử thông thường.

Sau khi đã chuẩn bị **đủ 76 cấu hình** và backend đang chạy, kiểm tra HTTP trên dữ liệu thật:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_long_range_metrics.py \
  --viewer-heights 2 10 20 30 --base-url http://127.0.0.1:8000 \
  --output /tmp/hosa-viewer-metrics-http.json
```

Script kiểm tra 76 cấu hình toàn khoảng, 228 cửa sổ đối chiếu native, tích phân chart, identity từng độ cao, năm nhuận và biên coverage. Không tạo job phân tích hay gọi LLM. Bằng chứng đã lưu: [build cache](docs/validation/lunarsight/viewer-metrics-build.json), [HTTP/native](docs/validation/lunarsight/viewer-metrics-http.json), [horizon và mesh](docs/validation/lunarsight/viewer-catalog-verification.json).

## 11. Chuyển cache sang máy khác

Có thể bỏ qua việc tính lại bước 4 nếu dùng cache từ **cùng phiên bản source, terrain package và nguồn dữ liệu**. Trên máy đã chuẩn bị, tạo archive chỉ gồm dữ liệu runtime cần thiết:

```bash
cd ~/HOSA
git rev-parse HEAD > /tmp/hosa-runtime-source.txt
tar -cf /tmp/hosa-runtime-cache.tar \
  data/cache/shared-ephemeris \
  data/cache/point-analysis/prepared-metrics
```

Chuyển archive và file ghi commit sang máy mới bằng công cụ truyền file của bạn. Trên máy mới, hoàn tất bước 1–3, dùng đúng phiên bản source rồi giải nén tại gốc repo **trước khi chạy backend**:

```bash
cd ~/HOSA
git rev-parse HEAD
cat /tmp/hosa-runtime-source.txt
tar -xf /tmp/hosa-runtime-cache.tar -C ~/HOSA
make ephemeris-prepare
```

Đối chiếu commit để biết phiên bản code đã tạo cache; ưu tiên dùng cùng phiên bản thuật toán và dữ liệu. Backend kiểm tra tính tương thích bằng hash nguồn, profile, model và kernel. `make ephemeris-prepare` xác minh kernel/receipt đã chuyển; khi đủ file hợp lệ sẽ dùng lại chúng. Sau đó chạy bước 5–7, không cần tính lại cache metrics tương thích. Giữ `.parts/`, receipt và cấu trúc thư mục, không chỉ chép các file `metrics.npz` riêng lẻ.

Nếu cần tọa độ mới, chuyển thêm `data/raw/nasa/` cùng receipt hoặc tải ở bước 8. Nếu muốn tái sử dụng validation đã tính, chuyển thêm `validation-evidence/` và `physical-series/` trong `data/cache/point-analysis/`. Archive trên không chứa `.env`, key hoặc lịch sử chat.

## 12. Chạy bản frontend build và deploy

Để kiểm tra bản build cục bộ, giữ backend ở 8000 rồi chạy:

```bash
cd ~/HOSA
npm --prefix frontend run build
npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Mở [http://127.0.0.1:4173](http://127.0.0.1:4173). Preview dùng cùng proxy Vite tới backend; có thể đặt `LUNARSIGHT_BACKEND_URL` trước lệnh nếu backend ở cổng khác.

Khi deploy, phục vụ `frontend/dist/` bằng web server, cấu hình `/api` reverse proxy tới backend và fallback SPA về `index.html`. Giữ backend một worker như bước 5; cần thiết kế queue/ownership trước khi tăng nhiều worker/replica. Dữ liệu cache và SQLite cần ổ persistent có quyền ghi. Vite dev/preview không thay cho cấu hình production này.

**Push Git chỉ chuyển source, gói horizon/mesh và báo cáo.** Cache metrics, kernel, DEM gốc và `.env` không nằm trong Git; máy deploy vẫn cần bước 4 hoặc bước 11 trước khi có metrics đã chuẩn bị.

## 13. Xử lý lỗi thường gặp

| Hiện tượng                                                       | Cách xử lý                                                                                                                                                                                |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python3 -m venv` thiếu `ensurepip`                            | Cài `python3-venv` đúng phiên bản Python rồi tạo lại venv                                                                                                                          |
| Node/npm quá cũ, `EBADENGINE`                                   | Nạp nvm, chạy `nvm install 22`, `nvm use 22`, rồi `npm --prefix frontend ci`                                                                                                        |
| `ModuleNotFoundError: app`                                        | Chạy từ gốc repo bằng Python trong venv; với uvicorn dùng `--app-dir backend`, với script dùng `PYTHONPATH=backend` như ví dụ                                                 |
| Cổng bận hoặc web không gọi được API                        | Kiểm tra cả hai health URL; dùng thống nhất 8000/5173 hoặc đổi cả cặp theo bước 5                                                                                                |
| `EPHEMERIS_NOT_PREPARED`                                          | Chạy bước 4.2 hoặc chuyển đủ kernel cùng receipt                                                                                                                                     |
| `METRICS_NOT_PREPARED` (409)                                      | Kiểm tra đã build đúng điểm, hai độ cao, model và khoảng ngày chưa. Request Site04 cũ không được chuẩn bị bởi lệnh mặc định mới; dùng request Haworth ở bước 6 |
| Có cache nhưng khoảng giờ lẻ không đọc được              | Chỉ mục nhanh cần biên thời gian được hỗ trợ; khoảng trong năm 2000–2100 chưa chắc khớp biên chỉ mục. Dùng Analyze để tính đúng khoảng, không tự làm tròn      |
| `DEM_NOT_INSTALLED`, `DEM_RECEIPT_MISSING`, ngoài DEM coverage | Cài/kiểm tra nguồn ở bước 8; dữ liệu chỉ được dùng trong coverage thực                                                                                                         |
| `OUTSIDE_EPHEMERIS_COVERAGE`                                      | Khoảng yêu cầu nằm ngoài kernel đã cài; không kẹp ngày để tạo kết quả                                                                                                        |
| `*_INTEGRITY_FAILED`                                              | Kiểm tra đúng phiên bản, file và receipt; cài lại artifact hợp lệ hoặc rebuild, không bỏ qua checksum                                                                           |
| Preview/result chưa sẵn sàng (409)                               | Xem status và stage của job; chờ phần dữ liệu tương ứng hoàn tất                                                                                                                  |
| INDETERMINATE sau Analyze                                           | Đọc `validation.reason_codes`, bounds và `resolution`; đây có thể là thiếu bằng chứng hoặc gate chưa đạt, không phải lỗi setup mặc định                             |
| Assistant disabled hoặc OpenRouter chưa cấu hình                | Kiểm tra `.env` gốc repo, enable/provider/key/model, restart backend rồi đọc capabilities                                                                                             |

## 14. Quy tắc đầu vào và ý nghĩa kết quả

- Chọn một `site_id` hoặc cặp tọa độ; không gửi cả hai. Kinh độ đông được chuẩn hóa về `[0,360)`; vĩ độ nằm giữa −90 và 90, không gồm hai cực.
- Thời điểm có timezone rõ ràng, đúng lưới 5 phút. Dùng `duration_hours` hoặc `end_utc`; gửi cả hai thì phải khớp. Nhiệm vụ ít nhất 1 giờ, theo bước 5 phút, không có giới hạn trên ở ứng dụng; vẫn chịu coverage và tài nguyên tính toán.
- Panel/antenna nhận độ cao `>0` đến `30 m`. Cache nhanh mặc định có các cặp 2/2, 10/10, 20/20, 30/30 m. Cặp khác có thể cần DEM và tính mới.
- `min_sunlit_fraction=0.8` là trung bình **diện tích đĩa Mặt Trời nhìn thấy** đạt 80%. `total_sun_hours` là giờ tương đương toàn đĩa; Earth/Joint là thời gian LOS/đồng thời nhìn thấy. Các cặp `[lower, upper]` biểu diễn cận mô hình.
- `required_windows` đếm cửa sổ liên lạc đủ điều kiện **tách biệt**, không đếm các phiên tự chia trong một cửa sổ liên tục. `constraints.max_darkness_hours` và `max_earth_blackout_hours` là ưu tiên mềm.
- `hard_first` chỉ loại sớm sau khi cùng hard requirement được xác nhận FAIL ở lưới 5 phút và 1 phút. Cache metrics không tự vượt validation; `resolve_indeterminate=true` cho phép các bước giải quyết đã hỗ trợ, không bảo đảm mọi điểm thành PASS/FAIL.

Kết quả còn PROVISIONAL: mô hình có lấy mẫu, chưa phải chứng nhận hạ cánh, mô hình điện/nhiệt hay RF link budget. Earth-centre LOS không tự bảo đảm đường truyền vô tuyến. `warnings`, `scope` và limitations cần được đọc cùng kết luận.

## 15. Cấu trúc và tài liệu

```text
backend/app/mission/          Schema, metrics và chính sách quyết định
backend/app/point_analysis/   Pipeline tọa độ, cache, chỉ mục và jobs
backend/app/planning/         Compare, tìm cửa sổ, xếp hạng và export
backend/app/assistant/        Provider LLM, chat, retrieval và lưu trạng thái
backend/app/precompute/       Gói horizon/mesh đã xác minh
frontend/src/figma/           Giao diện tích hợp
frontend/src/mvp/             API client và contracts
manifests/                    Catalog và nguồn dữ liệu
scripts/                      Chuẩn bị dữ liệu/cache và kiểm chứng
tests/                        Kiểm thử backend và khoa học
```

- [Cache bốn độ cao viewer](docs/decisions/viewer-height-precompute.md), [metrics 2000–2100](docs/decisions/century-metrics.md).
- [Validation evidence và xác nhận 5/1 phút](docs/decisions/validation-evidence-and-temporal-confirmation.md), [hard-first](docs/decisions/hard-first-physical-series.md).
- [Solar-disc / shared ephemeris](docs/decisions/solar-disc-mean-and-shared-ephemeris.md), [terrain precompute](docs/decisions/catalog-precompute.md), [progressive API](docs/decisions/progressive-point-analysis.md).
- [Planning API/CLI](docs/demo/planning-cli.md), [dữ liệu và validation](docs/validation/lunarsight/README.md), [Assistant](docs/assistant/BE_LLM_RELEASE.md).

Các endpoint snapshot legacy như `/api/scenarios`, `/api/analyze`, `/api/sites/{site_id}/profile` vẫn giữ scenario demo hai P1, 72 giờ và lưới start 15 phút. Chúng không đại diện cho coordinate API mới. Một số tài liệu nghiệm thu cũ phản ánh phiên bản trước; dùng README này và schema `/docs` của backend đang chạy cho luồng setup hiện tại.
