# HOSA · LunarSight

HOSA là ứng dụng phân tích chiếu sáng Mặt Trời và đường nhìn hình học tới tâm Trái Đất tại cực nam Mặt Trăng. Hệ thống dùng địa hình NASA LOLA/PGDA, ephemeris SPICE/JPL và backend tính toán xác định để trả metrics, cận bất định và kết luận **PASS / FAIL / INDETERMINATE** theo yêu cầu nhiệm vụ.

Giao diện gồm **Explore, Compare, Best dates và Assistant**. Explore có Moon / Pole / Ground / Horizon, mô phỏng theo thời gian và biểu đồ Sun / Earth / Joint. LLM là thành phần tùy chọn để hiểu và giải thích yêu cầu; các phép tính khoa học không cần API key.

Trong code hiện tại, **Compare** đánh giá các site tại cùng một thời điểm bắt đầu; **Best dates** thử nhiều thời điểm bắt đầu cho từng site và hiển thị cả các lần đã đánh giá. Viewer tải trạng thái Sun/Earth trên lưới 5 phút cho điểm có gói terrain, hoặc tính từng thời điểm cho tọa độ tùy chỉnh sau khi horizon sẵn sàng. Các luồng xem trước này tách khỏi kết luận nhiệm vụ của Analyze.

README này hướng dẫn từ máy mới đến hệ thống chạy local, theo code và cấu hình hiện có trên `main`. Mọi lệnh dùng **Bash**, chạy từ **gốc repo** trừ khi có ghi khác. Ví dụ đặt repo tại `~/HOSA`; thay đường dẫn này nếu bạn clone ở nơi khác.

## Mục lục

1. [Chọn lộ trình và hiểu các lớp dữ liệu](#1-chọn-lộ-trình-và-hiểu-các-lớp-dữ-liệu)
2. [Cài công cụ và lấy source](#2-cài-công-cụ-và-lấy-source)
3. [Cài dependency và cấu hình môi trường](#3-cài-dependency-và-cấu-hình-môi-trường)
4. [Chuẩn bị terrain, kernel và cache metrics](#4-chuẩn-bị-terrain-kernel-và-cache-metrics)
5. [Chạy backend và frontend để phát triển](#5-chạy-backend-và-frontend-để-phát-triển)
6. [Kiểm tra API và giao diện](#6-kiểm-tra-api-và-giao-diện)
7. [Setup DEM gốc và dựng lại terrain](#7-setup-dem-gốc-và-dựng-lại-terrain)
8. [Cache native và validation cho nhiệm vụ cụ thể](#8-cache-native-và-validation-cho-nhiệm-vụ-cụ-thể)
9. [Bật Assistant](#9-bật-assistant)
10. [Chuyển dữ liệu và cache sang máy khác](#10-chuyển-dữ-liệu-và-cache-sang-máy-khác)
11. [Chạy bản build local](#11-chạy-bản-build-local)
12. [Deploy local bằng Nginx và systemd](#12-deploy-local-bằng-nginx-và-systemd)
13. [Kiểm thử và vận hành sau khi cài](#13-kiểm-thử-và-vận-hành-sau-khi-cài)
14. [Xử lý lỗi thường gặp](#14-xử-lý-lỗi-thường-gặp)
15. [Contracts, cấu trúc source và tài liệu](#15-contracts-cấu-trúc-source-và-tài-liệu)

## 1. Chọn lộ trình và hiểu các lớp dữ liệu

| Mục tiêu | Các bước cần làm |
| --- | --- |
| Chạy thử có metrics nhanh cho Haworth, năm 2026, độ cao 20 m | Bước 2–3 → 4.1–4.3 → 5–6 |
| Chuẩn bị đầy đủ 27 mục NASA, bốn độ cao, năm 2000–2100 | Bước 2–3 → 4.1–4.2 → 4.4 → 5–6 |
| Dùng lại cache từ máy đã chuẩn bị | Bước 2–3 → 10 → 5–6 |
| Phân tích tọa độ hoặc độ cao ngoài gói có sẵn | Thêm bước 7; điểm vẫn phải nằm trong coverage DEM |
| Dùng hội thoại Assistant | Thêm bước 9 |
| Chạy frontend đã build | Bước 11; muốn service tự khởi động thì thêm bước 12 |

**Clone Git không mang theo đầy đủ dữ liệu runtime.** Cần phân biệt:

| Thành phần | Vị trí mặc định | Có trong Git? | Vai trò / cách chuẩn bị |
| --- | --- | --- | --- |
| Catalog và provenance | `manifests/` | Có | Tọa độ, nguồn, checksum và metadata; receipt trong Git không có nghĩa file gốc đã được cài |
| Terrain precompute | `data/processed/site-precompute/v1/` | Có | Manifest + blobs horizon/mesh cho các điểm và độ cao đã chuẩn bị |
| Snapshot legacy | `data/processed/lunarsight/v0.2.0/`, `v0.3.0/`, phần được theo dõi của `data/cache/lunarsight/v0.2.0/` | Có | Dữ liệu demo cũ; không thay thế cache coordinate API |
| Kernel và bảng vector SPICE | `data/cache/shared-ephemeris/` | Không | `make ephemeris-prepare`; bảng vector theo tháng được tạo khi cần |
| Metrics/chart đã chuẩn bị | `data/cache/point-analysis/prepared-metrics/` | Không | Build ở bước 4; không chứa kết luận nhiệm vụ được duyệt sẵn |
| DEM gốc và receipt đi kèm | `data/raw/nasa/`, `data/raw/<Site>/`, `data/raw/global/` | Không | Tải/import ở bước 7 khi cần quét địa hình mới |
| Geometry phát sinh | `data/cache/point-analysis/geometry/` | Không | Backend tạo khi thiếu horizon phù hợp |
| Chuỗi native, bằng chứng validation | `data/cache/point-analysis/physical-series/`, `validation-evidence/` | Không | Tạo theo request hoặc chuẩn bị ở bước 8 |
| Jobs, preview, kết quả và quỹ đạo | `data/cache/point-analysis/` | Không | Backend ghi trong quá trình sử dụng |
| Ảnh Moon Trek, mesh hiển thị phát sinh | `data/cache/moontrek/`, `data/cache/terrain-display/` | Không | Cache hiển thị, tách khỏi đầu vào tính toán khoa học |
| Chat, chỉ mục tra cứu | `data/cache/assistant/` | Không | SQLite được tạo khi dùng Assistant |
| Cấu hình và credential | `.env` | Không | Tự tạo từ `.env.example` |

Catalog mặc định có **27 mục NASA nhưng 26 tọa độ riêng biệt**: hai mục Leibnitz Beta Plateau cùng vị trí. Bốn preset viewer dùng cặp panel/antenna **2/2, 10/10, 20/20, 30/30 m**, tương ứng **104 cấu hình metrics**. Gói horizon còn có mức 1 m cho các luồng tương thích; mức này không nằm trong bộ 104 cấu hình.

Chuẩn bị dung lượng cho source, virtualenv, `node_modules`, kernel, metrics và các file tạm/checkpoint. Gói terrain hiện tại khoảng **302 MiB**; cache thế kỷ còn giữ các phần theo năm nên có thể chiếm vài GiB. DEM toàn catalog có thể lớn hơn nhiều. Đây không phải mức dung lượng cố định hay cấu hình phần cứng tối thiểu đã benchmark. Kiểm tra ổ đĩa trước khi tải; dùng ít worker nếu máy ít RAM/CPU. Không có GPU bắt buộc cho pipeline backend; trình duyệt cần WebGL để xem 3D.

## 2. Cài công cụ và lấy source

### 2.1. Yêu cầu môi trường

| Công cụ | Yêu cầu từ repo |
| --- | --- |
| Python | `>=3.11`; các ví dụ phù hợp Python 3.12 trên Ubuntu 24.04 |
| Node.js | `>=22.12.0`; `frontend/.nvmrc` chọn nhánh 22 |
| npm | `>=10.5.1` |
| Công cụ hệ thống | Git, Make, curl, CA certificates |
| Mạng | Cần khi cài dependency/tải dữ liệu lần đầu; ảnh Moon Trek chưa cache và LLM cũng cần mạng |

Ubuntu / Ubuntu trong WSL2:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates python3 python3-venv python3-pip
```

Nếu chưa có Node phù hợp, có thể cài qua [nvm theo hướng dẫn chính thức](https://github.com/nvm-sh/nvm#installing-and-updating):

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.41.0/install.sh \
  -o /tmp/hosa-install-nvm.sh
bash /tmp/hosa-install-nvm.sh
export NVM_DIR="${XDG_CONFIG_HOME:-$HOME}/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install 22
nvm use 22
```

Nếu đã có nvm ở vị trí khác, nạp `nvm.sh` từ vị trí đã cài. Trên macOS, cài Git, Make, Python và Node đáp ứng bảng trên; bỏ qua các lệnh `apt`. Trên Windows, dùng Ubuntu trong WSL2 và đặt repo trong filesystem Linux, ví dụ `~/HOSA`. Phần systemd/Nginx ở bước 12 dành cho Linux có systemd; hai cách chạy ở bước 5 và 11 không cần systemd.

```bash
python3 --version
node --version
npm --version
git --version
make --version
```

### 2.2. Clone source

```bash
cd ~
git clone --branch main https://github.com/QuanNguyen28/HOSA.git HOSA
cd ~/HOSA
git branch --show-current
git rev-parse HEAD
```

Với repo đã có trên máy, dùng checkout hiện tại phù hợp thay vì clone đè. Ghi lại commit khi tạo hoặc chuyển cache. Nếu cài một release/commit cụ thể, dùng cùng phiên bản đó trên máy build cache và máy chạy.

```text
HOSA/
├── backend/       FastAPI và engine khoa học
├── frontend/      React, TypeScript, Vite, Three.js
├── data/          raw, processed, cache
├── manifests/     Catalog, nguồn và provenance
├── scripts/       Tải dữ liệu, build cache, kiểm chứng
├── docs/          Contracts, quyết định kỹ thuật, ví dụ, báo cáo
├── tests/         Backend, khoa học, planning và Assistant tests
├── .env.example
└── Makefile
```

## 3. Cài dependency và cấu hình môi trường

### 3.1. Cài Python và frontend

```bash
cd ~/HOSA
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e 'backend[test]'
npm --prefix frontend ci
test -f .env || cp .env.example .env
mkdir -p .local/setup
backend/.venv/bin/python -m pip check
```

Không cần activate virtualenv; các lệnh bên dưới dùng trực tiếp Python trong `backend/.venv`. `npm ci` cài theo lockfile; dependency Python hiện dùng khoảng phiên bản trong `backend/pyproject.toml`, chưa có lockfile Python để bảo đảm tái tạo từng phiên bản tuyệt đối.

`make backend-install` và `make frontend-install` là hai target tương ứng. `scripts/requirements-lunarsight.txt` dành thêm cho notebook/EDA; không cần cài riêng để chạy web/backend thông thường.

### 3.2. Cấu hình lần đầu

Mở `.env` tại gốc repo và giữ:

```dotenv
APP_ENV=local
LOG_LEVEL=INFO
API_HOST=127.0.0.1
API_PORT=8000
DATA_ROOT=../data
MANIFEST_ROOT=../manifests
ASSISTANT_ENABLED=false
```

Các trường provider có thể giữ như `.env.example`, để key trống. Explore / Analyze / Compare / Best dates chạy không cần key. Không chép `.env` hoặc credential của người khác vào repo.

**Cách code đọc cấu hình cần lưu ý:**

- Lệnh backend trong README dùng `--env-file .env` để nạp rõ file ở gốc repo. Assistant cũng tìm `.env` theo vị trí source. Khởi động lại backend sau khi sửa cấu hình.
- Cổng Uvicorn do `--port` quyết định. Sửa `API_PORT` trong `.env` không tự đổi cổng của lệnh đang chạy.
- Các pipeline dữ liệu chính lấy `data/` và `manifests/` theo vị trí repo. `DATA_ROOT` / `MANIFEST_ROOT` hiện không phải công tắc chuyển toàn bộ storage. Giữ cấu trúc thư mục ở bảng bước 1 khi chuyển máy hoặc mount ổ đĩa.
- Gói terrain hỗ trợ `HOSA_PRECOMPUTE_ROOT`; cache mesh hiển thị hỗ trợ `HOSA_DISPLAY_CACHE_ROOT`. Nếu cần dùng, đặt biến trong môi trường tiến trình trước khi chạy script/server. `--root` của script build chỉ đổi nơi script đó ghi; API không tự dùng đường dẫn mới.
- Proxy frontend đọc `LUNARSIGHT_BACKEND_URL` từ môi trường của **tiến trình Vite**. Biến này không tự được export từ `.env` backend. Frontend gọi đường dẫn tương đối `/api`.

## 4. Chuẩn bị terrain, kernel và cache metrics

### 4.1. Xác minh terrain đã có trong Git

Máy mới **không cần tải DEM hoặc rebuild terrain để dùng các điểm/preset đã đóng gói**. Giữ cả `manifest.json` và thư mục `blobs/`:

```bash
cd ~/HOSA
OPENBLAS_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_nasa_catalog_cache.py \
  --output .local/setup/terrain-verification.json
```

Kết quả cuối mong đợi: `passed=true`, `default_entries=27`, `coordinates=26`, `verified_profiles=260`, `verified_meshes=286`. Đây là kiểm tra gói terrain; chưa chứng minh kernel hay cache metrics đã sẵn sàng.

Xem các site ID và tọa độ dùng cho precompute:

```bash
backend/.venv/bin/python scripts/precompute_catalog.py --list
```

### 4.2. Cài kernel runtime

```bash
make ephemeris-prepare
```

Script tải và xác minh năm file từ NAIF vào `data/cache/shared-ephemeris/kernels/`:

```text
naif0012.tls
pck00011.tpc
de440s.bsp
moon_pa_de440_200625.bpc
moon_de440_250416.tf
```

Mỗi file có receipt liền kề. Bảng vector giờ theo tháng nằm trong `data/cache/shared-ephemeris/tables/`, được tính từ kernel khi cần. Mô hình mặc định `solar_disc` dùng SPICE local; không gọi JPL Horizons cho từng request. `sun_center` là mô hình legacy riêng, có thể cần cache/network JPL Horizons đúng observer.

Nếu muốn làm nóng bảng vector cho năm 2026 trước khi mở web:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_shared_ephemeris.py \
  --start 2026-01-01T00:00:00Z --end 2026-12-31T23:00:00Z
```

Khoảng ngày ở đây chọn các tháng cần tạo bảng, không tạo metrics hoặc kết luận nhiệm vụ. Nếu kernel tồn tại nhưng thiếu/sai receipt, script dừng khi kiểm tra integrity; chạy lại không tự sửa một file có provenance sai.

### 4.3. Lộ trình nhanh: Haworth, năm 2026, 20 m

Dùng bước này để thử hệ thống trước khi tính cache cả thế kỷ:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_long_range_metrics.py \
  --sites haworth \
  --start 2026-01-01T00:00:00Z --end 2027-01-01T00:00:00Z \
  --viewer-heights 20 --workers 1 \
  --report .local/setup/haworth-2026-metrics-build.json
```

Report phải có `passed=true`, `sites_total=1`, `configurations_total=1`, một record. Sau đó chạy bước 5–6 và chọn **Haworth, panel 20 m, antenna 20 m, ngày trong năm 2026**. Chưa có cache nhanh cho toàn bộ site/độ cao/năm khác; Analyze vẫn có thể tính theo request nếu đủ đầu vào.

### 4.4. Lộ trình đầy đủ: 104 cấu hình, toàn bộ năm 2000–2100

Có thể chạy trực tiếp bước này sau 4.2, hoặc chạy sau khi thử xong 4.3:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_long_range_metrics.py \
  --start 2000-01-01T00:00:00Z --end 2101-01-01T00:00:00Z \
  --viewer-heights 2 10 20 30 --workers 2 \
  --report .local/setup/nasa27-metrics-build.json
```

Khoảng phủ là **`[2000-01-01, 2101-01-01)`**, bao gồm hết năm 2100. `--viewer-heights` tạo cặp panel/antenna cùng độ cao; 26 tọa độ × 4 cặp = 104 cấu hình. Cặp 2/20 m hoặc độ cao khác không thuộc bộ này.

Đây là bước tính toán dài; thời gian phụ thuộc CPU, RAM và cache đã có. Script tính metrics danh nghĩa trên lưới 5 phút, checkpoint từng năm trong `.parts/`, rồi mới công bố chỉ mục hoàn chỉnh cho khoảng yêu cầu. Nếu bị ngắt, chạy lại cùng lệnh để dùng lại các phần còn tương thích. Giữ `.parts/` để resume và đọc nhanh cửa sổ ngắn. Giảm xuống `--workers 1` nếu thiếu tài nguyên.

```bash
backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
report = json.loads(Path('.local/setup/nasa27-metrics-build.json').read_text())
assert report['passed'] is True
assert report['sites_total'] == 26
assert len(report['records']) == report['configurations_total'] == 104
print('READY: 26 coordinates, 104 configurations')
PY
```

Target rút gọn `make metrics-century-prepare` làm cùng loại build với **3 worker** và ghi report vào `docs/validation/lunarsight/nasa27-metrics-build.json`. Nếu dùng target đó, đổi đường dẫn report trong đoạn kiểm tra. README dùng `.local/setup/` để báo cáo cài máy không làm thay đổi tài liệu được Git theo dõi.

**Metrics có sẵn không đồng nghĩa nhiệm vụ đã được validation.** `/metrics` chỉ trả metrics/chart ban đầu; Analyze còn đánh giá requirements, bằng chứng và các gate theo đúng request. Bộ mặc định không build các target legacy `Site01_P1`, `Site04_P1`, Example A/B; muốn dùng chúng phải chọn rõ ID và chuẩn bị riêng.

## 5. Chạy backend và frontend để phát triển

Mở hai terminal, giữ cả hai chạy. Cặp mặc định: backend **8000**, frontend **5173**.

**Terminal 1 — backend:**

```bash
cd ~/HOSA
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  backend/.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --env-file .env \
  --host 127.0.0.1 --port 8000 --workers 1
```

**Terminal 2 — frontend:**

```bash
cd ~/HOSA
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite chuyển `/api` tới backend. `--strictPort` giúp phát hiện cổng bận thay vì tự chuyển sang cổng khác.

**Terminal 3 — kiểm tra kết nối:**

```bash
curl --fail-with-body http://127.0.0.1:8000/api/health
curl --fail-with-body http://127.0.0.1:5173/api/health
```

Cả hai phải trả `status="ok"`, `service="hosa-api"`. Đây chỉ là **liveness**: health không kiểm tra DEM/kernel/metrics hay gọi LLM. Kiểm tra dữ liệu ở bước 6.

API tương tác: [Swagger UI](http://127.0.0.1:8000/docs), [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

Có thể dùng `make backend-run` / `make frontend-run` cho phát triển. `backend-run` bật `--reload`; không nên dùng chế độ tự reload khi chạy job dài vì sửa file có thể khởi động lại tiến trình. Lệnh ở trên giữ một worker, không reload.

### Đổi cổng

Nếu backend 8000 hoặc frontend 5173 đã bận, dùng cặp 8001 / 5174:

```bash
# Terminal backend
cd ~/HOSA
backend/.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --env-file .env --host 127.0.0.1 --port 8001 --workers 1
```

```bash
# Terminal frontend
cd ~/HOSA
LUNARSIGHT_BACKEND_URL=http://127.0.0.1:8001 \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Mở [http://127.0.0.1:5174](http://127.0.0.1:5174); đổi cổng các request kiểm tra tương ứng. Gọi API qua proxy cùng origin như trên không cần mở rộng CORS. Nếu tự làm client gọi thẳng backend từ origin khác, cấu hình CORS hiện tại trong `backend/app/main.py` chỉ cho `localhost:5173` và `127.0.0.1:5173`.

Dừng bằng Ctrl+C trong từng terminal. Lần mở sau chỉ cần chạy lại server; không cài lại dependency/build lại cache nếu code, model và dữ liệu vẫn tương thích.

## 6. Kiểm tra API và giao diện

### 6.1. Catalog và coverage

```bash
curl --fail-with-body --silent --show-error http://127.0.0.1:8000/api/lunar/sites \
  -o .local/setup/legacy-sites.json
curl --fail-with-body http://127.0.0.1:8000/api/lunar/coverage
backend/.venv/bin/python scripts/precompute_catalog.py --list
```

`/api/lunar/sites` trả catalog snapshot legacy hai P1; `/api/lunar/coverage` cũng còn metadata snapshot và inventory raster. Hai endpoint này không phải danh sách 27 mục NASA hay kiểm tra readiness toàn bộ cache hiện tại. Danh sách mặc định của UI/engine nằm trong `manifests/compare-sites.json`; lệnh `--list` in 26 nhóm tọa độ của danh sách đó. Dùng kiểm tra terrain ở 4.1 và request metrics bên dưới để xác minh luồng hiện tại.

Catalog NASA dùng tâm vùng trong **Lunar Surface Data Book, ACD-50044 Revision A, bảng A2-2, trang 57–58**. Xem [tọa độ](manifests/nasa-south-pole-sites.csv) và [receipt nguồn](manifests/nasa-south-pole-sites.receipt.json). Đây là tọa độ NASA công bố, không phải điểm tối ưu địa hình hoặc điểm đáp đã được phê duyệt.

### 6.2. Metrics và chart, dùng được với lộ trình nhanh

```bash
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/lunar/point/metrics \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o .local/setup/haworth-metrics.json

backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('.local/setup/haworth-metrics.json').read_text())
assert r['execution']['metrics_index_hit'] is True
assert r['decision'] is None and r['evaluation_status'] == 'pending'
assert 0 < len(r['timeline']) <= 800
print(json.dumps({k: r[k] for k in (
    'evaluation_status', 'metrics_hours', 'joint_hours', 'evaluation_stages'
)}, indent=2, ensure_ascii=False))
PY
```

File mẫu dùng Haworth, 24/11/2026, 72 giờ, hai thiết bị 20 m. Endpoint `/metrics` vẫn nhận schema nhiệm vụ nhưng **chưa đánh giá requirements**, dù payload có ngưỡng 80%. `pending` và `decision=null` là đúng ở giai đoạn này. Chart tổng hợp tối đa 800 bin, không phải toàn bộ chuỗi native.

Sau khi hoàn tất bộ cache thế kỷ, kiểm tra thêm request toàn khoảng:

```bash
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/lunar/point/metrics \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-metrics-request.json \
  -o .local/setup/haworth-century-metrics.json
```

### 6.3. Phân tích và đánh giá nhiệm vụ

Dùng request Haworth nói trên với endpoint Analyze:

```bash
curl --fail-with-body --silent --show-error \
  'http://127.0.0.1:8000/api/lunar/point/analyze?view=display' \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o .local/setup/haworth-analysis.json

backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('.local/setup/haworth-analysis.json').read_text())
assert r['evaluation_status'] == 'complete'
assert r['decision'] in {'PASS', 'FAIL', 'INDETERMINATE'}
print('Decision:', r['decision'])
print('Validation:', json.dumps(r['validation'], ensure_ascii=False))
print('Warnings:', r['warnings'])
PY
```

Lần đầu có thể lâu hơn `/metrics` do phải tính validation/chuỗi native. Không dùng PASS làm tiêu chí cài đặt thành công: FAIL có thể là kết quả đúng theo requirements; INDETERMINATE có thể phản ánh bằng chứng chưa đủ. Request đã bật `resolve_indeterminate`, nhưng tính năng này không bảo đảm luôn kết luận được.

Đối với công việc dài, UI dùng API job:

| Thao tác | Endpoint |
| --- | --- |
| Gửi nhiệm vụ | `POST /api/lunar/point/analyses` → HTTP 202 và `job_id` |
| Đọc tiến độ | `GET /api/lunar/point/analyses/{job_id}` |
| Đọc preview khi có | `GET /api/lunar/point/analyses/{job_id}/preview` |
| Lấy kết quả gọn để hiển thị | `GET /api/lunar/point/analyses/{job_id}/result?view=display` |
| Tải native intervals | `GET /api/lunar/point/analyses/{job_id}/intervals.csv` |

HTTP 202 chỉ xác nhận đã nhận job; đợi `succeeded` hoặc đọc `error_code` nếu `failed`. Preview có thể sẵn sàng trước validation cuối cùng.

### 6.4. Kiểm tra trên web

1. Mở Explore, chọn Haworth, panel/antenna 20 m, bắt đầu `2026-11-24T00:00:00Z`, kéo dài 72 giờ.
2. Kiểm tra địa hình trong Moon / Pole / Ground, rồi mở Horizon để xem skyline 360° và quỹ đạo Sun/Earth.
3. Bấm Analyze point, chờ tiến độ và đọc kết quả cùng validation/warnings. Play/Pause/Replay điều khiển thời gian hiển thị.
4. Với Compare và Best dates, chọn điểm/thời gian có coverage; thử một tập nhỏ trước. Mỗi candidate còn phải đánh giá nhiệm vụ riêng, không chỉ đọc chart cache.
5. Kiểm tra export JSON/CSV và đối chiếu `result_id` với kết quả đang xem.

Trong Pole/Ground, gốc địa hình và đường nhìn Sun/Earth đi theo điểm đang chọn sau một khoảng chờ ngắn khi nhập tọa độ. Chờ địa hình/trạng thái của điểm mới tải xong trước khi đọc marker; không dùng trạng thái cũ của điểm trước cho tọa độ vừa chọn.

Horizon tự chuẩn bị ở nền khi chọn tọa độ/độ cao chưa có cache, không cần bấm Analyze trước; công việc này cần DEM nếu ngoài gói có sẵn. Quỹ đạo hiển thị tải theo phần tối đa 120 ngày: nhiệm vụ ngắn tối đa 7 ngày dùng mẫu 5 phút, nhiệm vụ dài hơn dùng mẫu 1 giờ. Đây là dữ liệu vẽ, không phải chuỗi dùng để thay thế validation khoa học.

Ảnh Moon Trek tải qua backend và cache từng tile. Máy offline có thể tính `solar_disc` với đầu vào local đầy đủ, nhưng không tự có mọi ảnh/LOD chưa tải hoặc khả năng gọi Assistant.

### 6.5. Trạng thái Sun/Earth tại thời điểm đang xem

Các endpoint dưới nhận cùng schema nhiệm vụ với Analyze và dùng `solar_disc`:

| Endpoint | Hành vi hiện tại |
| --- | --- |
| `POST /api/lunar/point/instants` | Trả toàn bộ trạng thái danh nghĩa theo bước 5 phút cho nhiệm vụ **không quá 31 ngày**, khi đúng tọa độ và hai độ cao có trong gói terrain. UI giữ chuỗi trong bộ nhớ để đổi thời điểm mà không gọi lại từng tick |
| `POST /api/lunar/point/instant?at_utc=...` | Trả một interval 5 phút chứa thời điểm đã chọn. Điểm có gói dùng horizon đóng gói; điểm tùy chỉnh dùng horizon của chính tọa độ đó đã được chuẩn bị ở nền |
| `GET /api/lunar/point/analyses/{job_id}/interval?at_utc=...` | Đọc interval native của kết quả Analyze. UI ưu tiên dữ liệu đã phân tích khi có |
| `GET /api/lunar/point/sky-vectors?at_utc=...` | Vector SPICE theo giờ của tháng tương ứng để vẽ chuyển động; không thực hiện đánh giá nhiệm vụ |

Giới hạn 31 ngày chỉ áp dụng cho `/instants`, **không phải giới hạn thời lượng Analyze**. Với khoảng dài hơn hoặc điểm chưa có terrain đóng gói, UI chuyển sang đọc trạng thái từng thời điểm. `/instant` không tự quét DEM: tọa độ tùy chỉnh cần horizon đã được preload; khi chưa sẵn sàng, API trả `HORIZON_NOT_PREPARED` và UI hiển thị đang chuẩn bị.

Kiểm tra bằng request Haworth 72 giờ đã dùng ở trên:

```bash
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/lunar/point/instants \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o .local/setup/haworth-instants.json

curl --fail-with-body --silent --show-error \
  'http://127.0.0.1:8000/api/lunar/point/instant?at_utc=2026-11-24T00%3A12%3A00Z' \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o .local/setup/haworth-instant.json

backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
series = json.loads(Path('.local/setup/haworth-instants.json').read_text())
assert series['sampling_minutes'] == 5
assert series['evidence_source'] == 'prepared_nominal'
assert len(series['rows']) == 72 * 12
row = json.loads(Path('.local/setup/haworth-instant.json').read_text())
assert row['sampling_minutes'] == 5
print('READY:', len(series['rows']), 'nominal intervals')
print('Selected interval:', row['start_utc'], row['end_utc'])
PY
```

Đây là trạng thái nominal phục vụ con trỏ và viewer, không phải PASS/FAIL, kết quả validation tinh chỉnh hay toàn bộ native timeline được lưu sẵn trong cache metrics thế kỷ. `prepared_nominal` chỉ nguồn terrain đã đóng gói; `computed_nominal` chỉ trạng thái tính cho tọa độ từ horizon đã cache. Thời điểm đọc phải nằm trong cửa sổ nhiệm vụ nửa mở `[start_utc, end_utc)`.

### 6.6. Compare và Best dates

**Compare** lấy cùng thời điểm bắt đầu, thời lượng, requirements và hardware cho các site đã tick. UI gọi `/api/planning/compare` lần lượt cho từng site, cập nhật kết quả và tiến độ khi mỗi site hoàn tất. Khi thêm site rồi chạy lại cùng request, câu trả lời đã có được giữ trong bộ nhớ của trang; tải lại trang sẽ mất cache frontend này, còn cache backend trên đĩa vẫn giữ.

**Best dates** gọi `/api/planning/windows/search` lần lượt cho từng site, thử các thời điểm bắt đầu theo bước đã chọn. Backend giới hạn **128 tổ hợp start × target trong mỗi request coordinate search**; UI tách request theo site và cho chọn 16/32/64/128 thời điểm mỗi site. `until_utc` là biên loại trừ của **thời điểm bắt đầu**, không phải thời điểm kết thúc toàn bộ nhiệm vụ. Phải có dữ liệu đến hết nhiệm vụ cuối cùng.

Search trả `evaluations` cho các lần thực sự đã đánh giá, kèm trạng thái và metrics gọn; `candidates` là danh sách lựa chọn được trả về sau lọc/xếp hạng. UI yêu cầu tối đa 10 lựa chọn và tránh các nhiệm vụ chồng lấn tại cùng site. Một ô đã đánh giá có thể không nằm trong danh sách lựa chọn cuối. Chỉ kết quả PASS được phép áp dụng; near miss FAIL vẫn giữ FAIL.

Kết quả gộp trên UI có thể gồm nhiều kết quả backend: JSON tải bản gộp, còn menu CSV cho chọn từng phần có ID riêng. Để gọi API/CLI trực tiếp, dùng `data_source="coordinate"`, gửi rõ hardware và ít nhất một hard requirement; đọc schema `/docs` cho đầy đủ trường. Cache metrics chuẩn bị ở bước 4 không biến Compare/Search thành thao tác chỉ đọc chart: mỗi nhiệm vụ còn cần bằng chứng và validation phù hợp.

## 7. Setup DEM gốc và dựng lại terrain

Chỉ cần bước này khi phân tích tọa độ/độ cao ngoài gói, mất gói terrain hoặc muốn tái tạo từ nguồn gốc. HTTP request không tự tải DEM gốc. Mesh nhìn thấy trên giao diện không chứng minh đủ coverage để kết luận khoa học.

### 7.1. Bộ DEM cơ bản cho coordinate analysis

```bash
cd ~/HOSA
backend/.venv/bin/python scripts/prepare_point_data.py
backend/.venv/bin/python scripts/prepare_point_data.py --offline
```

Script tải bốn nguồn vào **`data/raw/nasa/`**, cùng receipt `.receipt.json` liền kề:

| Dataset ID | Nội dung |
| --- | --- |
| `Site01_dem` | `Site01_final_adj_5mpp_surf.tif` |
| `Site04_dem` | `Site04_final_adj_5mpp_surf.tif` |
| `dem80` | `LDEM_80S_80MPP_ADJ.TIF`, vùng phía nam 80°S |
| `dem240` | `LDEM_60S_240MPP_ADJ.TIF`, vùng phía nam 60°S |

`--offline` kiểm tra file và receipt, không tải file còn thiếu. Có thể chọn từng nguồn bằng `--datasets`, ví dụ:

```bash
backend/.venv/bin/python scripts/prepare_point_data.py --datasets dem80 dem240
```

Bộ này không cài tất cả DEM 5 m của 27 mục NASA, cũng không tự tải lớp error/count cho mọi site. Điểm chỉ được tính trong coverage thật của raster có giá trị hợp lệ; độ phân giải quan sát có thể là 5/80/240 m tùy vị trí và nguồn đã cài.

### 7.2. Tải DEM 5 m, error và count cho catalog NASA

Để tái tạo bộ địa hình mặc định đầy đủ, cần cả DEM vùng ở 7.1 và bộ site:

```bash
backend/.venv/bin/python scripts/build_nasa_default_catalog.py
backend/.venv/bin/python scripts/acquire_pgda78_sites.py \
  --roles dem error count --workers 3 --range-workers 4
```

Script thường ghi vào `data/raw/<source_code>/`, ví dụ `data/raw/Haworth/`; nếu file đã tồn tại ở `data/raw/nasa/`, script có thể dùng vị trí đó. Backend hỗ trợ cả hai bố cục.

- `--workers`: 1–6 file song song; `--range-workers`: 1–16 byte range mỗi file. Tổng tải đồng thời tăng theo cả hai giá trị; giảm khi mạng/RAM hạn chế.
- Muốn tải thử một site: thêm `--sites Haworth`. Đây là **source code**, khác site ID `haworth` của script metrics/API.
- Kiểm tra lại không tải mạng: chạy cùng lệnh với `--offline`.
- Script cập nhật `manifests/datasets.csv`, `manifests/lunarsight/pgda78_selected_sites.json` và receipt theo dõi trong Git. Việc tải/kiểm tra có thể tạo diff provenance; xem diff trước khi commit.

`--roles dem error count` không yêu cầu ROI. Nếu chủ động tải ROI, lưu ý ROI Site06 là hạn chế nguồn đã biết và có thể làm acquisition báo lỗi; không thay dữ liệu thiếu bằng ROI của site khác. Site20 và Site20v2 cùng location group.

### 7.3. Rebuild horizon và mesh

Sau khi tải/kiểm tra xong nguồn cần thiết:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 GDAL_CACHEMAX=96 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/precompute_catalog.py \
  --workers 2 --report .local/setup/nasa27-terrain-build.json

OPENBLAS_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_nasa_catalog_cache.py \
  --output .local/setup/nasa27-terrain-verification.json
```

Hai target tương đương là `make precompute-catalog` và `make precompute-verify`; chúng ghi report vào `docs/validation/lunarsight/`. `precompute_catalog.py` mặc định ghi vào gói `data/processed/site-precompute/v1/` được Git theo dõi, đồng thời chuẩn bị các mesh polar-cap. Chạy khi backend đã dừng để kiểm soát phiên bản dữ liệu đang phục vụ.

Khi source/thuật toán thay đổi, kiểm tra và build lại metrics phù hợp theo 4.4. Identity bao gồm nguồn, profile, model và kernel; không đổi tên hash hoặc sửa receipt để ép dùng cache cũ. `make viewer-horizons-prepare` dành cho việc bổ sung preset vào gói cũ còn tương thích, không phải bước bắt buộc sau clone hiện tại.

### 7.4. Tải bộ full-product mở rộng

Registry: `manifests/lunarsight/full_product_sources.json`. Bộ này có quality layers, morphology, dữ liệu validation, asset hiển thị, SPICE và raster vùng. Nó không thay thế acquisition DEM site ở 7.2.

```bash
make data-plan
make data-acquire
make data-verify
```

Mặc định là profile `core`. Kiểm tra một dataset hoặc chọn profile khác:

```bash
backend/.venv/bin/python scripts/acquire_full_product_data.py \
  --profile extended --dry-run
backend/.venv/bin/python scripts/acquire_full_product_data.py \
  --only lola_dem_80s_80m --verify
```

`--only` chọn theo ID chính xác và được ưu tiên hơn profile. Bỏ `--dry-run` để tải profile đã chọn. `--verify` chỉ kiểm tra các file download đã cài, không materialize nguồn remote/on-demand. Receipt được ghi cạnh file và trong `manifests/lunarsight/full_product_receipts/`; report lần chạy ở `data/raw/full_product/acquisition_report.json`.

**Kernel full-product ở `data/raw/full_product/spice/` khác kernel runtime ở `data/cache/shared-ephemeris/kernels/`.** Sau `make data-acquire`, vẫn chạy `make ephemeris-prepare` theo 4.2 cho runtime hiện tại.

DEMs 10/20 m được giữ dạng remote COG để trích cửa sổ. Ví dụ rõ tọa độ, không phụ thuộc catalog GeoJSON phát sinh:

```bash
backend/.venv/bin/python scripts/materialize_dem_windows.py \
  --point 'haworth,-86.7639,337.223' --tier mid20 --dry-run
backend/.venv/bin/python scripts/materialize_dem_windows.py \
  --point 'haworth,-86.7639,337.223' --tier mid20
```

Output ở `data/raw/full_product/dem/windows/`. Đây là workflow trích dữ liệu mở rộng; **coordinate engine hiện chỉ đăng ký DEM site 5 m và DEM vùng 80/240 m** qua `terrain_sources()`. Tạo cửa sổ 10/20 m chưa tự đưa nó vào pipeline khoa học. `make data-sites` cũng là workflow catalog full-product riêng, không thay cho `build_nasa_default_catalog.py`.

### 7.5. Import từ bộ bàn giao NASA thay vì tải mạng

Nếu đã có thư mục bàn giao với `SOURCE_MANIFEST.json`, `DOWNLOAD_CHECKSUMS.json` và các ZIP tương ứng:

```bash
backend/.venv/bin/python scripts/import_nasa_delivery.py \
  --delivery-path /mnt/lunarsight-data \
  --datasets Site01 Site04 dem80 dem240
backend/.venv/bin/python scripts/prepare_point_data.py --offline
```

Thay `/mnt/lunarsight-data` bằng đường dẫn thật. Importer xác minh checksum archive, checksum/byte count từng member và receipt trước khi ghi vào `data/raw/nasa/`. Importer này chỉ nhận các group ở lệnh trên, không import toàn bộ catalog 27 mục.

Đặt `LUNARSIGHT_RAW_DATASET_PATH` chỉ cung cấp vị trí bộ bàn giao cho importer/tra cứu metadata; không tự import raster vào engine. Các script không mặc nhiên nạp `.env` của web, nên truyền `--delivery-path` như ví dụ hoặc export biến trong shell.

## 8. Cache native và validation cho nhiệm vụ cụ thể

Hai bước dưới là tùy chọn để giảm công việc lần đầu của Analyze, tách biệt với chỉ mục metrics/chart ở bước 4.

### 8.1. Chuẩn bị chuỗi vật lý native

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_physical_series.py \
  --sites haworth \
  --start 2026-11-24T00:00:00Z --end 2026-11-27T00:00:00Z \
  --panel 20 --antenna 20 --workers 1 \
  --report .local/setup/haworth-physical-series.json
```

Chuỗi nominal 5 phút được lưu trong `physical-series/`, không phê duyệt requirements. Không truyền ngày thì script mặc định chuẩn bị 2026–2027 (`end=2028-01-01`), không phải toàn thế kỷ. `prepare_metric_indexes.py` / `make metrics-prepare` chỉ lập chỉ mục từ chuỗi đã tồn tại; không thay cho build thế kỷ ở 4.4.

### 8.2. Chuẩn bị bằng chứng validation

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_validation_evidence.py \
  --request docs/examples/point-haworth-evaluation-request.json \
  --all-refinements --report .local/setup/haworth-validation.json
```

Bằng chứng chỉ dùng cho đúng tọa độ, hai độ cao, model, khoảng thời gian và nguồn tương thích. Đổi threshold có thể tái sử dụng phần số liệu, nhưng engine vẫn đánh giá lại requirements/gate. `--all-refinements` chuẩn bị thêm các mức tinh chỉnh được hỗ trợ. Không có bước validation toàn thế kỷ được ngầm thực hiện bởi lệnh build metrics.

## 9. Bật Assistant

Hoàn thành backend và dữ liệu trước, sau đó chọn **một provider** trong `.env`. `.env.example` chọn transport `openai` cho proxy tương thích OpenAI; tên transport không bảo đảm model do OpenAI cung cấp.

Ví dụ gateway tương thích OpenAI/LiteLLM; thay URL, key và model bằng cấu hình tài khoản thật:

```dotenv
ASSISTANT_ENABLED=true
ASSISTANT_PROVIDER=openai
ASSISTANT_STREAMING=true
ASSISTANT_FAILOVER_ENABLED=false
LLM_PROXY_BASE_URL=https://your-gateway.example/v1
LLM_PROXY_API_KEY=YOUR_KEY
LLM_PROXY_MODEL=YOUR_MODEL_ID
LLM_PROXY_RESPONSE_FORMAT=json_schema
```

URL ví dụ không phải gateway hoạt động. Base URL adapter này yêu cầu HTTPS, không chứa credential/query/fragment. Các provider còn lại được code hỗ trợ:

| `ASSISTANT_PROVIDER` | Biến cần cấu hình |
| --- | --- |
| `nvidia` | `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`; nếu bật failover sang Gemini thì cấu hình thêm Gemini |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, tùy chọn `OPENROUTER_RESPONSE_FORMAT=json_schema` |
| `openai` | `LLM_PROXY_API_KEY`, `LLM_PROXY_BASE_URL`, `LLM_PROXY_MODEL`, `LLM_PROXY_RESPONSE_FORMAT` |

Đây là cách cấu hình adapter trong repo; model cụ thể còn phụ thuộc quyền truy cập và khả năng hỗ trợ structured output của provider. Không đưa key vào frontend, biến `VITE_*` hay file được commit.

Khởi động lại backend, rồi kiểm tra cấu hình không phát sinh inference:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/assistant/capabilities
```

Mong đợi `assistant_enabled=true`, `provider` đúng lựa chọn, `provider_configured=true`. Endpoint này không chứng minh key/model gọi thành công. Thử một câu trong Assistant trên web sau khi kiểm tra cấu hình; thao tác này gọi provider thật và có thể phát sinh phí.

Lịch sử chat mặc định ở `data/cache/assistant/chat.sqlite3`, chỉ mục nguồn ở `knowledge.sqlite3`. Giữ cả thư mục nếu cần bảo toàn trạng thái. `ASSISTANT_DATABASE_PATH` có ảnh hưởng tới các luồng lưu/tra cứu khác nhau; để trống khi dùng bố cục mặc định. `ASSISTANT_NATURAL_EXPLANATIONS` và `ASSISTANT_ANSWER_REVIEW` có thể làm tăng số lần inference/độ trễ. Xem [Assistant release guide](docs/assistant/BE_LLM_RELEASE.md) và [gateway, retrieval, giải thích có nguồn](docs/decisions/litellm-grounded-chat.md).

## 10. Chuyển dữ liệu và cache sang máy khác

Dùng cách này để tránh tính lại cache dài. Ưu tiên cùng commit, terrain package và nguồn dữ liệu. Không chuyển virtualenv hoặc `node_modules`; cài dependency trên máy đích theo bước 3.

### 10.1. Gói runtime cho các điểm đã chuẩn bị

Trên máy nguồn, đợi job/build xong và dừng backend trước khi sao lưu:

```bash
cd ~/HOSA
git rev-parse HEAD > /tmp/hosa-runtime-source.txt
tar -cf /tmp/hosa-runtime-cache.tar \
  data/cache/shared-ephemeris \
  data/cache/point-analysis/prepared-metrics
(cd /tmp && sha256sum hosa-runtime-cache.tar > hosa-runtime-cache.tar.sha256)
```

Chuyển ba file `/tmp/hosa-runtime-source.txt`, `/tmp/hosa-runtime-cache.tar`, `/tmp/hosa-runtime-cache.tar.sha256` tới `/tmp` trên máy đích bằng công cụ truyền file của bạn. Archive chứa toàn bộ `prepared-metrics/`, gồm `.parts/`, receipt và cấu trúc hash; không chỉ chép `metrics.npz` riêng lẻ.

Trên máy đích sau khi cài source/dependency:

```bash
cd ~/HOSA
git rev-parse HEAD
cat /tmp/hosa-runtime-source.txt
(cd /tmp && sha256sum -c hosa-runtime-cache.tar.sha256)
tar -tf /tmp/hosa-runtime-cache.tar | head
```

Đối chiếu commit với phiên bản máy nguồn trước khi giải nén. Trên máy cài mới, backend đang dừng:

```bash
tar -xf /tmp/hosa-runtime-cache.tar -C ~/HOSA
make ephemeris-prepare
OPENBLAS_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_nasa_catalog_cache.py \
  --output .local/setup/restored-terrain-verification.json
```

Nếu máy đích đã có dữ liệu riêng, sao lưu các thư mục đích trước; giải nén có thể thay thế file trùng tên. `make ephemeris-prepare` dùng lại file/receipt hợp lệ đã chuyển. Gói terrain đi cùng Git; nếu máy nguồn dùng gói custom chưa commit, phải chuyển cả `manifest.json` và toàn bộ `blobs/` tương ứng.

Khởi động lại ở bước 5 rồi chạy kiểm tra metrics ở bước 6 hoặc kiểm tra đầy đủ ở bước 13. Cache không tương thích nguồn/thuật toán phải được build lại, dù tên site giống nhau.

### 10.2. Khi cần giữ thêm dữ liệu

| Nhu cầu | Chuyển thêm |
| --- | --- |
| Tính tọa độ/độ cao mới, rebuild terrain | Nguồn đã cài trong `data/raw/`, receipt liền kề và manifests tương ứng; không chỉ `data/raw/nasa/` nếu nguồn nằm ở thư mục site/global |
| Giữ chuỗi native và validation | `data/cache/point-analysis/physical-series/`, `validation-evidence/` |
| Giữ kết quả/job đã hoàn tất | Toàn bộ `data/cache/point-analysis/` từ snapshot nhất quán |
| Giữ chat và chỉ mục | `data/cache/assistant/`; dừng backend trước khi sao lưu SQLite/WAL |
| Dùng lại ảnh đã tải | `data/cache/moontrek/` |

Archive runtime ở 10.1 không chứa `.env`, key, DEM gốc hoặc chat. Đặt `.env` riêng trên máy đích. Job đang chạy không được bảo đảm tiếp tục sau khi restart; gửi lại request sau khi dịch vụ sẵn sàng, các cache hợp lệ vẫn được tái sử dụng.

## 11. Chạy bản build local

Nếu chỉ cần chạy và xem frontend đã build, giữ backend ở 8000 và dùng một terminal khác:

```bash
cd ~/HOSA
npm --prefix frontend run build
npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Mở [http://127.0.0.1:4173](http://127.0.0.1:4173), kiểm tra:

```bash
curl --fail-with-body http://127.0.0.1:4173/api/health
```

Preview cũng có proxy `/api`. Backend ở cổng khác thì đặt biến ở **lệnh preview**:

```bash
LUNARSIGHT_BACKEND_URL=http://127.0.0.1:8001 \
  npm --prefix frontend run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Output build nằm trong `frontend/dist/`. Chép thư mục này đi nơi khác chưa mang theo backend hay cache. Vite preview dùng để kiểm tra local; muốn phục vụ static và giữ backend tự chạy, dùng bước 12.

## 12. Deploy local bằng Nginx và systemd

Ví dụ dưới đây phục vụ ứng dụng trên **`http://127.0.0.1:8080`**, API ở **`127.0.0.1:8000`**. Thực hiện trên Ubuntu có systemd sau khi đã chuẩn bị dữ liệu. Giữ một tiến trình backend với **`--workers 1`** vì queue/ownership hiện nằm trong tiến trình; không tăng replica/worker như một cách tăng tốc mặc định.

### 12.1. Tạo user service cho backend

Dừng backend chạy thủ công ở bước 5 để nhường cổng 8000. Từ gốc repo, tạo service cho user hiện tại; block này thay `$PWD` bằng đường dẫn checkout thật:

```bash
cd ~/HOSA
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/hosa-api.service" <<EOF_SERVICE
[Unit]
Description=HOSA local API

[Service]
Type=simple
WorkingDirectory=$PWD
Environment=OPENBLAS_NUM_THREADS=1
Environment=OMP_NUM_THREADS=1
Environment=MKL_NUM_THREADS=1
ExecStart=$PWD/backend/.venv/bin/python -m uvicorn app.main:app --app-dir $PWD/backend --env-file $PWD/.env --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF_SERVICE

systemctl --user daemon-reload
systemctl --user enable --now hosa-api
systemctl --user status hosa-api --no-pager
curl --fail-with-body http://127.0.0.1:8000/api/health
```

Mẫu service giả định đường dẫn repo không có khoảng trắng, như `~/HOSA`. Backend chạy dưới user hiện tại, cần quyền ghi vào `data/cache/`. Nếu muốn service tiếp tục chạy sau logout và được khởi tạo khi boot:

```bash
sudo loginctl enable-linger "$USER"
```

Nếu WSL không có systemd/user manager hoạt động, dùng cách chạy thủ công ở bước 11 hoặc cấu hình systemd cho WSL trước khi dùng mục này.

### 12.2. Build và đưa static files vào thư mục web

```bash
cd ~/HOSA
npm --prefix frontend run build
sudo apt install -y nginx
sudo install -d -m 755 /var/www/hosa
sudo cp -R frontend/dist/. /var/www/hosa/
sudo chmod -R a+rX /var/www/hosa
```

Thư mục `/var/www/hosa` chỉ chứa output build. Cách này giúp Nginx đọc static files mà không cần mở quyền truy cập thư mục home của bạn.

### 12.3. Cấu hình SPA và API proxy

```bash
sudo tee /etc/nginx/sites-available/hosa-local >/dev/null <<'EOF_NGINX'
server {
    listen 127.0.0.1:8080;
    server_name localhost;
    root /var/www/hosa;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
        proxy_cache off;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF_NGINX
sudo ln -sfn /etc/nginx/sites-available/hosa-local /etc/nginx/sites-enabled/hosa-local
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

`proxy_pass` giữ nguyên prefix `/api`; không thêm dấu `/` sau cổng 8000 trong mẫu này. `proxy_buffering off` phục vụ streaming Assistant; timeout được đặt dài hơn cho các request tính toán. Với nhiệm vụ dài, vẫn ưu tiên API job thay vì giữ một request đồng bộ.

### 12.4. Xác minh và quản lý

```bash
curl --fail-with-body http://127.0.0.1:8080/
curl --fail-with-body http://127.0.0.1:8080/api/health
curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8080/api/lunar/point/metrics \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-haworth-evaluation-request.json \
  -o .local/setup/deployed-metrics.json
```

Mở [http://127.0.0.1:8080](http://127.0.0.1:8080). Khi chạy Nginx, không cần Vite dev/preview hoặc `LUNARSIGHT_BACKEND_URL`; Nginx định tuyến API. Swagger vẫn truy cập trực tiếp ở backend 8000.

```bash
journalctl --user -u hosa-api -n 100 --no-pager
systemctl --user restart hosa-api
systemctl --user stop hosa-api
# Chỉ khi muốn bỏ tự khởi động backend:
systemctl --user disable hosa-api
```

Đây là cấu hình local, bind loopback. Nếu đổi sang phục vụ LAN/public, cần thiết kế thêm giới hạn truy cập, TLS và quản lý dịch vụ phù hợp; code hiện chưa có lớp xác thực người dùng chung cho API. Cache và SQLite phải nằm trên ổ có quyền ghi và được giữ qua các lần deploy.

## 13. Kiểm thử và vận hành sau khi cài

### 13.1. Bộ kiểm thử thông thường

```bash
cd ~/HOSA
make verify
```

Target chạy backend tests, frontend tests, TypeScript và production build. Không cần key LLM cho bộ kiểm thử thông thường. Có thể chạy từng phần:

```bash
make test
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Các script có `--live` hoặc provider preflight có thể gọi dịch vụ thật; không thuộc quy trình setup tối thiểu ở README này.

### 13.2. Kiểm tra cache thế kỷ qua HTTP

Sau khi đã build đủ bộ 4.4 và backend đang chạy:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_long_range_metrics.py \
  --viewer-heights 2 10 20 30 --base-url http://127.0.0.1:8000 \
  --output .local/setup/nasa27-metrics-http.json
```

Script kiểm tra 104 cấu hình toàn khoảng, ba cửa sổ native mỗi cấu hình, tích phân chart, identity theo độ cao, năm nhuận và biên coverage; không tạo analysis job hay gọi LLM. Report thành công có `passed=true`, `no_jobs_created=true`. Chỉ chạy lộ trình một năm ở 4.3 thì chưa đủ đầu vào cho script này; dùng smoke ở 6.2.

### 13.3. Cập nhật source, dữ liệu và backup

1. Chờ job hoàn tất, dừng backend và sao lưu trạng thái cần giữ ở bước 10.
2. Xem thay đổi local, cập nhật đúng nhánh/commit khi đã xử lý các thay đổi riêng của bạn.
3. Cài lại dependency nếu manifest/lockfile thay đổi, xác minh terrain/kernel và build lại cache nếu identity đã đổi.
4. Chạy `make verify`, khởi động backend và chạy smoke API.
5. Nếu dùng Nginx, build lại frontend, chép `frontend/dist/.` vào `/var/www/hosa/` như 12.2. Không ghi dữ liệu runtime vào thư mục static.

```bash
git status --short
git diff --stat
# Chỉ cập nhật sau khi đã xử lý thay đổi local:
git pull --ff-only
backend/.venv/bin/python -m pip install -e 'backend[test]'
npm --prefix frontend ci
```

Để xem dung lượng (chỉ ghi những thư mục đã tồn tại trên máy):

```bash
df -h .
du -sh data/raw data/cache data/processed/site-precompute/v1
```

Không xóa toàn bộ `data/cache/` để xử lý một lỗi: thư mục còn chứa kernel, metrics, bằng chứng và lịch sử chat. Khi một artifact sai checksum, dừng dịch vụ, giữ lại file/receipt để đối chiếu, xác định nguồn bị lỗi rồi tải/build lại thành phần tương ứng. Khởi động lại backend sau khi thay nguồn để bỏ các cache trong bộ nhớ.

**Git push chỉ chuyển source và các artifact được theo dõi.** Máy deploy mới vẫn cần cài kernel và build/chuyển cache runtime; báo cáo JSON trong Git không thay thế dữ liệu tính toán trên đĩa.

## 14. Xử lý lỗi thường gặp

| Hiện tượng | Kiểm tra và cách xử lý |
| --- | --- |
| `ensurepip` / tạo venv thất bại | Cài `python3-venv` phù hợp phiên bản Python rồi tạo lại venv |
| `EBADENGINE`, Node quá cũ | Nạp nvm, dùng Node 22.12+; mở shell mới có thể phải `nvm use 22` trước `npm ci` |
| `ModuleNotFoundError: app` | Chạy từ gốc repo, đúng Python venv; Uvicorn có `--app-dir backend`, script yêu cầu thì thêm `PYTHONPATH=backend` |
| Cổng bận / `Address already in use` | Dừng tiến trình cũ hoặc đổi cặp cổng theo bước 5; không chạy backend thủ công trùng service |
| Vite báo proxy error / Nginx 502 | Kiểm tra backend health ở 8000, log service và đúng proxy target; restart Vite sau đổi biến môi trường |
| Health OK nhưng không có metrics | Health chỉ kiểm tra tiến trình; thực hiện 4 và smoke 6.2 |
| `EPHEMERIS_NOT_PREPARED` | Chạy `make ephemeris-prepare`; file trong `data/raw/full_product/spice/` chưa đủ cho runtime |
| `EPHEMERIS_INTEGRITY_FAILED` | Kiểm tra đủ năm kernel và receipt đúng URL/bytes/SHA-256; không tạo receipt giả để bỏ gate |
| `METRICS_NOT_PREPARED` (409) | Kiểm tra site/tọa độ, hai độ cao, model, thời gian và source identity. Cache 20/20 m không áp dụng cho 2/20 m; Site04 P1 cũ không thuộc build mặc định |
| Có cache nhưng request giờ lẻ không hit | Chỉ mục metrics tổng hợp chỉ phục vụ biên có trong index, thường theo ngày cho cây metrics. Lưới input 5 phút hợp lệ chưa bảo đảm index có biên đó; dùng Analyze để tính đúng request, không tự làm tròn |
| `DEM_NOT_INSTALLED` | Cài nguồn ở 7.1/7.2 nếu điểm/độ cao không có trong terrain package |
| `DEM_RECEIPT_MISSING`, `DEM_INTEGRITY_FAILED`, `DEM_SOURCE_UNREGISTERED` | Giữ file gốc cùng receipt và registry đúng nguồn; dùng acquisition/importer chính thức, không chép mỗi raster |
| `OUTSIDE_DEM_COVERAGE` | Kiểm tra coverage thực và nodata; DEM vùng/site không phủ toàn Mặt Trăng |
| `OUTSIDE_EPHEMERIS_COVERAGE` | Kernel không phủ khoảng cần dùng; không kẹp ngày hoặc ngoại suy để trả kết quả |
| `HORIZON_NOT_PREPARED` khi xem tọa độ tùy chỉnh | Chờ `POST /api/lunar/point/horizon-profile/preload` hoàn tất và kiểm tra DEM của đúng tọa độ/độ cao; `/instant` không tự quét terrain |
| `INSTANT_NOT_PREPARED` / `SERIES_TOO_LONG` | Chuỗi `/instants` cần terrain đóng gói, model `solar_disc` và khoảng tối đa 31 ngày. UI có luồng đọc từng thời điểm; không coi đây là giới hạn thời lượng Analyze |
| `SEARCH_TOO_LARGE` (422) | Giảm số thời điểm hoặc số target để không vượt 128 tổ hợp trong một request coordinate search; UI hiện tách request theo từng site |
| `PRECOMPUTE_*`, `PREPARED_METRICS_INTEGRITY_FAILED` | Kiểm tra manifest/blobs/receipt, cùng nguồn và phương pháp; xác minh rồi rebuild thành phần không tương thích |
| Download file đã có nhưng bị từ chối | Script bảo vệ file thiếu/sai provenance; đối chiếu artifact trước khi thay, chạy lại không tự chứng minh file đúng |
| `POINT_ANALYSIS_BUSY` (429) | Queue đầy hoặc request trùng đang được tính; đọc job hiện có/đợi hoàn tất rồi thử lại |
| Preview/result trả 409 | Job hoặc phần chi tiết chưa sẵn sàng; đọc `status`, `stage`, `preview_url`, `result_url` |
| Job lỗi sau restart | Tiến trình cũ không còn sở hữu công việc; kiểm tra `error_code`, gửi lại request và dùng lại cache hợp lệ |
| INDETERMINATE | Đọc `validation.reason_codes`, bounds, warnings, resolution; đây có thể là kết quả khoa học chứ không phải lỗi cài đặt |
| Ảnh NASA trống khi offline | Tile/LOD chưa cache cần mạng; ảnh không được dùng thay DEM/horizon khoa học |
| Assistant disabled/chưa cấu hình | Sửa `.env` ở gốc, enable/provider/key/model, restart backend rồi đọc capabilities |
| Capabilities configured nhưng chat lỗi | Cấu hình tồn tại không xác minh credential/quota/model/structured output; đọc mã lỗi provider |
| systemd service không khởi động | Xem journal; kiểm tra đường dẫn tuyệt đối trong unit, venv, `.env`, quyền ghi cache, cổng và user manager |
| Nginx refresh route trả 404 | Giữ SPA fallback `try_files ... /index.html`; API vẫn proxy nguyên `/api` |

## 15. Contracts, cấu trúc source và tài liệu

### Quy tắc đầu vào và cách đọc kết quả

- Chọn `site_id` **hoặc** cặp `latitude_deg` / `longitude_e_deg`. Vĩ độ thuộc `(-90,90)`; kinh độ đầu vào `[-180,360]` được chuẩn hóa về `[0,360)`.
- Thời gian phải có timezone và nằm đúng lưới UTC 5 phút. Nhiệm vụ ít nhất 1 giờ, theo bước 5 phút; gửi `duration_hours` hoặc `end_utc`, nếu gửi cả hai phải khớp. Không có trần thời lượng chung ở coordinate API, nhưng vẫn chịu coverage và tài nguyên.
- Panel/antenna nhận `0 < height <= 30 m`. API mặc định 1 m / 2 m, khác cặp 20/20 m trong ví dụ setup; luôn gửi rõ hai độ cao để kiểm tra đúng cache.
- `solar_disc` là mặc định. `min_sunlit_fraction=0.8` là trung bình diện tích đĩa Mặt Trời nhìn thấy đạt 80%; `total_sun_hours` là giờ tương đương toàn đĩa. Earth là Earth-centre LOS; Joint là thời gian đồng thời theo định nghĩa mô hình.
- Các cặp `[lower, upper]` là cận mô hình. Tổng thời gian khả dụng khác với tính liên tục. `max_darkness_hours` / `max_earth_blackout_hours` là mong muốn mềm; `required_windows` đếm các cửa sổ liên lạc đủ điều kiện tách biệt.
- `hard_first` chỉ kết luận loại sớm khi hard failure được xác nhận theo các bước lấy mẫu đã hỗ trợ. Metrics cache không bỏ qua validation. `resolve_indeterminate=true` cho phép thử các bước giải quyết, không biến mọi request thành PASS/FAIL.
- Compare/Search dùng `data_source="coordinate"` cho pipeline hiện tại. Chế độ snapshot và các endpoint legacy vẫn có cửa sổ/độ cao/coverage riêng; đọc capabilities/schema thay vì áp dụng giới hạn demo cũ cho coordinate API.

HOSA là prototype phục vụ học tập và lập kế hoạch sơ bộ. Kết quả còn PROVISIONAL, không phải chứng nhận hạ cánh, mô hình điện/nhiệt hay RF link budget. Earth-centre LOS không bảo đảm liên lạc vô tuyến thực tế. Đọc `scope`, `warnings`, `validation` và provenance cùng kết luận.

### Đọc code theo luồng dữ liệu

| Nơi đọc | Nội dung |
| --- | --- |
| `backend/app/main.py`, `core/config.py` | App startup, router, CORS, cấu hình |
| `backend/app/mission/` | Schema nhiệm vụ chung, metrics, evaluation và resolution |
| `backend/app/point_analysis/` | Pipeline tọa độ, nguồn DEM, horizon, cache, jobs, transport |
| `backend/app/precompute/` | Đọc/ghi gói terrain, kiểm tra identity và blob |
| `backend/app/services/lunarsight/` | Acquisition, DEM, Horizons/SPICE, visibility, imagery, legacy snapshot |
| `backend/app/planning/` | Compare, search, ranking và export |
| `backend/app/assistant/` | Provider, retrieval, giải thích có nguồn và lưu chat |
| `frontend/src/figma/` | UI tích hợp, viewer và các màn hình sản phẩm |
| `frontend/src/mvp/` | API client và frontend contracts |
| `scripts/`, `tests/` | Chuẩn bị/kiểm chứng dữ liệu và regression tests |

### Tài liệu liên quan

- [Catalog NASA hiện tại](docs/decisions/nasa-default-catalog.md), [terrain precompute](docs/decisions/catalog-precompute.md), [bốn độ cao viewer](docs/decisions/viewer-height-precompute.md).
- [Solar disc và shared ephemeris](docs/decisions/solar-disc-mean-and-shared-ephemeris.md), [metrics cả thế kỷ](docs/decisions/century-metrics.md), [metrics trước, đánh giá sau](docs/decisions/metrics-first.md).
- [Validation evidence](docs/decisions/validation-evidence-and-temporal-confirmation.md), [hard-first và physical series](docs/decisions/hard-first-physical-series.md), [progressive API](docs/decisions/progressive-point-analysis.md).
- [Cách đọc kết quả](docs/demo/point-response-guide-vi.md), [hướng dẫn data/validation](docs/validation/lunarsight/README.md), [scripts](scripts/README.md), [tests](tests/README.md).
- [Assistant hiện tại](docs/assistant/lunarsight-current-context.md), [Assistant release](docs/assistant/BE_LLM_RELEASE.md), [gateway và grounded chat](docs/decisions/litellm-grounded-chat.md).

Một số tài liệu demo, notebook và `frontend/README.md` mô tả các phiên bản tích hợp trước. Các endpoint `/api/scenarios`, `/api/analyze`, `/api/sites/{site_id}/profile` còn giữ snapshot demo riêng. Để setup và gọi luồng hiện tại, dùng README gốc này cùng schema `/docs` của backend đang chạy; không suy rộng coverage từ một snapshot hoặc từ việc có archive trên đĩa.
