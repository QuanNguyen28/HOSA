# HOSA

HOSA là nguyên mẫu hỗ trợ so sánh điều kiện chiếu sáng Mặt Trời và đường nhìn hình học tới Trái Đất tại các vị trí ứng viên ở cực nam Mặt Trăng.

## MVP frontend–backend tích hợp

Nhánh `feat/merge-fe-be` ghép `feature/lunarsight-frontend` với `feat/fix-compute-backend`, gồm các sửa lỗi đã rà soát. Giao diện giữ product shell gốc tại `frontend/src/figma/`, gọi API thật cho Explore, Compare, Best dates và Assistant; các hàm mô phỏng horizon/ephemeris/metric và chat heuristic của bản Figma đã được gỡ bỏ.

Yêu cầu Python 3.11+, Node 22.12+, npm 10.5.1+:

```bash
make backend-install
make frontend-install
backend/.venv/bin/python scripts/prepare_point_data.py
make ephemeris-prepare
```

Chạy ở hai terminal:

```bash
make backend-run
```

```bash
make frontend-run
```

Mở `http://127.0.0.1:5173`. Hai điểm Example A/B là hai request NASA/JPL đã kiểm chứng với nhiệm vụ **72 giờ, panel/antenna 20 m**; bấm Analyze point để lấy kết quả backend. Đổi ngày/tọa độ không tự dùng lại metric của điểm cũ.

```bash
make verify
make mvp-smoke
```

Assistant cần cấu hình `.env` từ `.env.example`; khóa OpenRouter chỉ nằm ở backend. Assistant nhận tên hoặc mã điểm từ cùng danh mục với Compare, tối đa hai điểm mỗi lượt. Mặc định solar-disc tính theo tọa độ, kể cả Site01_P1/Site04_P1; snapshot legacy dành cho yêu cầu `sun_center` tương thích. Các giới hạn và hướng dẫn đầy đủ: [MVP tích hợp](docs/demo/fe-be-mvp.md), [frontend](frontend/README.md).

Các phần dưới mô tả thêm pipeline dữ liệu và API snapshot legacy, không phải toàn bộ phạm vi của giao diện MVP mới.

API Point/Planning và chat mới mặc định dùng `illumination_model: "solar_disc"`: yêu cầu `min_sunlit_fraction` là **trung bình theo thời gian của phần diện tích đĩa Mặt Trời nhìn thấy**, gồm địa hình và Trái Đất che khuất. Thấy nửa đĩa suốt nhiệm vụ là 50%, không đạt yêu cầu 80%. `total_sun_hours` giữ tên tương thích nhưng mang nghĩa giờ tương đương toàn đĩa; `illumination` giải thích định nghĩa trong response. Earth LOS vẫn xét tâm Trái Đất. Snapshot cũ chỉ dùng với `illumination_model: "sun_center"` rõ ràng; request solar-disc được chuyển qua engine tọa độ.

`make ephemeris-prepare` tải kernel chính thức NAIF/JPL một lần, lưu checksum và nguồn. Backend sinh bảng vector MOON_ME theo giờ/từng tháng khi cần và tái sử dụng cho các tọa độ, chiều cao, ngày khác nhau. Không gọi mạng trong phép tính solar-disc; không giới hạn trên thời lượng nhiệm vụ ở ứng dụng, nhưng ngày phải nằm trong coverage kernel đã cài. Cần bảng mở rộng thì chạy lại pipeline với kernel phù hợp; backend không kẹp ngày về biên dữ liệu.

Chi tiết và kiểm thử: [quyết định mô hình](docs/decisions/solar-disc-mean-and-shared-ephemeris.md), [nghiệm thu](docs/validation/lunarsight/solar-disc-backend.md).

Gói `data/processed/site-precompute/v1/` đi cùng repo chứa horizon cho **23 tọa độ mặc định**, chiều cao **1/2/10/20 m**, đủ các mức refinement hiện có, và **255 mesh hiển thị** (11 cấu hình mỗi tọa độ + 2 mesh toàn vùng cực nam). Backend đọc artifact có checksum; đổi ngày, thời lượng hay yêu cầu không cần scan lại DEM cho các cấu hình này. GET mesh dùng gzip/ETag, frontend tái sử dụng dữ liệu khi đổi điểm. Tọa độ khác hoặc chiều cao khác vẫn dùng DEM và cache runtime. Khi cập nhật DEM/thuật toán, tạo lại gói bằng `make precompute-catalog`. Hướng dẫn deploy và giới hạn: [precompute catalog](docs/decisions/catalog-precompute.md).

Explore hiển thị số liệu Sun/Earth/Joint ban đầu ngay sau lưới 5 phút, với nhãn `EVALUATING`; validation, requirement và refinement tiếp tục ở worker nền. Kết luận cuối chỉ xuất hiện khi hoàn tất đánh giá. Nhiệm vụ dài hạn dùng tối đa 800 cột timeline cho hiển thị; khi kéo thời gian, trạng thái hiện tại lấy mẫu gốc qua API riêng. Không giảm số mẫu tính toán và không thêm giới hạn thời lượng. Xem [API progressive và kiểm thử 10 năm](docs/decisions/progressive-point-analysis.md).

Mặc định `evaluation_policy: "hard_first"`: kiểm tra hard requirements trước, dừng tại hard FAIL đã được chứng minh trên giới hạn trên của mô hình lấy mẫu, trả `hard_failure` cùng các khoảng thời gian hỗ trợ; validation và soft preferences ghi rõ bị bỏ qua. Nếu chưa có hard fail, backend chạy validation rồi soft preferences. Dùng `evaluation_policy: "complete"` khi cần toàn bộ chẩn đoán. Chuỗi vật lý được cache bền vững, độc lập với requirement và hỗ trợ đọc khoảng con; `make physics-prepare` chuẩn bị 23 điểm, thiết bị 20 m, trong 2026–2028 trước deploy. Khoảng khác vẫn tính bình thường. CSV native chỉ sinh khi gọi `/api/lunar/point/analyses/{job_id}/intervals.csv`. Xem [cách thực thi, deploy và benchmark](docs/decisions/hard-first-physical-series.md).

Explore tự lấy metrics và chart Sun/Earth/Joint đã chuẩn bị qua `POST /api/lunar/point/metrics` khi chọn điểm hoặc đổi ngày, hiển thị `METRICS READY` mà không chờ validation. Chỉ mục theo ngày giữ nguyên bounds và các khoảng tối dài qua nửa đêm; `make metrics-prepare` tạo chỉ mục cho chuỗi vật lý đã có. `make metrics-century-prepare` chuẩn bị gọn 23 tọa độ mặc định, thiết bị 20 m, từ đầu năm 2000 đến hết năm 2100; cần mang cả cache đã tạo lên môi trường deploy. Bấm Analyze để đánh giá requirements và kết luận. Phạm vi chưa có chỉ mục vẫn tính qua Analyze bình thường. Xem [metrics-first](docs/decisions/metrics-first.md) và [phạm vi 2000–2100, cách deploy và bằng chứng](docs/decisions/century-metrics.md).

## Mục tiêu của bộ khung

Bộ khung này tách rõ các lớp dữ liệu, tính toán và giao diện để nhóm có thể phát triển theo trình tự:

1. kiểm tra dữ liệu và provenance;
2. tích hợp JPL Horizons;
3. tạo geometric baseline;
4. tính terrain horizon từ DEM;
5. tính visibility, metric và mission windows;
6. kết nối giao diện Explore và Compare; Plan là backlog sau MVP.

Pipeline hình học đã chạy cho Site01 và Site04 trên Kaggle. Snapshot v0.3.0 kế thừa hình học v0.2.0 và dùng tổng thời gian có nắng/Earth LOS làm yêu cầu cứng; các khoảng tối/mất LOS liên tục là mong muốn mềm. Kịch bản vẫn `PROVISIONAL`. Xem [quyết định về metric](docs/decisions/availability-hard-continuity-soft.md) và [bằng chứng kiểm định hình học](docs/validation/lunarsight/README.md).

## Cấu trúc

```text
HOSA/
├── backend/                  # API và logic nghiệp vụ Python
│   ├── app/
│   │   ├── api/              # HTTP routes
│   │   ├── core/             # cấu hình và logging
│   │   ├── models/           # schema request/response
│   │   ├── services/         # xử lý dữ liệu và tính toán
│   │   └── main.py           # entrypoint FastAPI
│   └── pyproject.toml
├── frontend/                 # giao diện Explore, Compare, Plan
│   ├── src/
│   └── package.json
├── data/
│   ├── raw/                  # dữ liệu gốc, bất biến, không commit
│   ├── processed/            # hình học v0.2.0 và metric/quyết định v0.3.0
│   └── cache/                # snapshot phản hồi Horizons và thư mục chạy cục bộ
├── manifests/                # catalog, checksum, request config
├── scripts/                  # runner dữ liệu và notebook Kaggle
├── docs/                     # quyết định kỹ thuật, validation, giới hạn
├── tests/                    # kiểm thử khoa học và fixture tổng hợp
├── .env.example
├── .gitignore
└── Makefile
```

## Khởi chạy backend

Yêu cầu Python 3.11 trở lên.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Kiểm tra:

```bash
curl http://localhost:8000/api/health
```

Kết quả mẫu:

```json
{"status":"ok","service":"hosa-api","version":"0.1.0"}
```

## Khởi chạy Moon Explorer 3D

Moon Explorer dùng React, Three.js, NASA LROC color map và LOLA terrain derivatives.

```bash
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite chuyển tiếp `/api` tới backend tại cổng 8000.

Các chức năng hiện có:

- Moon globe 3D với ánh sáng và timeline;
- camera Orbit, South Pole và Surface;
- chọn tọa độ bất kỳ trên Moon globe, truy vấn DEM tốt nhất đang phủ điểm đó;
- marker Site01/Site04 từ catalog hiện tại, giữ nguyên tọa độ đã kiểm định;
- visibility Sun/Earth và cửa sổ 72 giờ từ dữ liệu xử lý thật;
- địa hình cục bộ Site01 và Site04, mỗi vùng 16 × 16 km, tạo từ DEM 5 m.
- sinh mesh địa hình 16 × 16 km quanh điểm tùy chọn khi tọa độ nằm trong coverage DEM.
- không gian Compare dùng scenario `south_pole_demo_v1`: 1.344 mốc bắt đầu/site trên lưới 15 phút, nhiệm vụ 72 giờ; hai tỷ lệ có nắng/Earth LOS tối thiểu là yêu cầu cứng, giới hạn tối/mất LOS liên tục là mong muốn mềm tùy chọn;
- so sánh Site01/Site04 bằng cận metric, ba trạng thái `PASS/FAIL/INDETERMINATE`, timeline sự kiện và horizon profile;
- xuất JSON/CSV kèm cấu hình, nguồn, dataset version và method version.

Scenario `south_pole_demo_v1` giữ hai candidate site và ephemeris demo 14/11–01/12/2026 UTC. API phân tích tọa độ `/api/lunar/point/*` ở phần đầu README dùng pipeline riêng, có metrics chuẩn bị cho 23 điểm trong 2000–2100 và tính theo yêu cầu trong coverage nguồn thực tế. Global texture/bump map và mesh chỉ phục vụ hiển thị/khảo sát địa hình. Earth LOS không phải link budget; Sun visibility không phải mô hình điện hoặc nhiệt.

## API của MVP

- `GET /api/scenarios`: scenario, miền UTC, thời lượng, chiều cao và lưới bắt đầu cố định.
- `GET /api/sites/{site_id}/profile?target=sun|earth`: horizon 0,25° và vật cản quyết định.
- `POST /api/analyze`: đánh giá một `start_index` chính xác cho một hoặc hai site.
- `GET /api/results/{result_id}/export?format=json|csv`: xuất kết quả tái lập.

Ví dụ:

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H 'Content-Type: application/json' \
  --data '{
    "scenario_id":"south_pole_demo_v1",
    "site_ids":["Site01_P1","Site04_P1"],
    "start_index":0,
    "min_sunlit_fraction":0.8,
    "min_earth_los_fraction":0.8,
    "constraints":{
      "max_darkness_hours":12,
      "max_earth_blackout_hours":6
    }
  }'
```

`D_hours`, chiều cao thiết bị, bước mô hình và bước lưới là thuộc tính bất biến của scenario. API trả `UNSUPPORTED_CONFIG` thay vì tự làm tròn hoặc thay cấu hình.
Hai mức tối thiểu là đầu vào bắt buộc. `constraints.max_*` chỉ là mong muốn mềm; vượt chúng không loại phương án. Giá trị 80% trong ví dụ không phải yêu cầu NASA quy định.

Có thể nhập trực tiếp ngày, điểm và ngưỡng bằng `scripts/planning_cli.py compare`
hoặc `search`, không qua LLM. Xem [CLI headless và ví dụ gọi API](docs/demo/planning-cli.md).

## Kiểm tra trước demo

```bash
make verify
```

Lệnh này chạy toàn bộ pytest, TypeScript typecheck và production build. Báo cáo nghiệm thu ứng dụng nằm tại `docs/validation/lunarsight/v0.2.0/reports/application_acceptance.md`.

Trước khi khóa bản nộp, dùng `docs/release-checklist.md`; kịch bản ghi hình nằm tại `docs/demo/lunarsight-demo-script.md` và protocol thử 3–5 người nằm tại `docs/validation/lunarsight/v0.2.0/user_test_protocol.md`.

Với release candidate, chạy kiểm tra đầy đủ và sinh manifest bằng chứng:

```bash
make release-check
```

Kết quả được ghi vào `docs/validation/lunarsight/v0.2.0/reports/release_audit.json`.
Biên bản chốt G0 nằm tại `docs/approvals/g0-signoff.md`; bản mô tả tiếng Anh
chuẩn bị cho hồ sơ nộp nằm tại `docs/submission/project-description-en.md`.
Các yêu cầu chính thức 2026 đã xác minh và biên bản bàn giao lần lượt nằm tại
`docs/submission/2026-official-requirements.md` và
`docs/handover/release-handover.md`.

Sau khi đã commit release candidate và `make release-check` đạt trên worktree sạch,
tạo source archive cùng SHA-256 bằng:

```bash
make package-release
```

Script chủ động từ chối đóng gói worktree đang có thay đổi để tránh bàn giao nhầm
phiên bản. Shot list ảnh/video nằm tại `docs/submission/media-shot-list.md`.

## Quy tắc dữ liệu

- `data/raw/` không sửa sau khi tải; mọi nguồn phải có bản ghi trong `manifests/datasets.csv`.
- Không commit GeoTIFF lớn, credential hoặc response chứa thông tin nhạy cảm.
- Dữ liệu xử lý và cache JPL đã kiểm định nằm trong snapshot `v0.2.0`. Dữ liệu NASA gốc được tải riêng từ [bản phát hành dữ liệu](https://github.com/QuanNguyen28/HOSA/releases/tag/lunarsight-data-v0.2.0).
- Mọi thời gian dùng UTC ISO 8601; mọi góc dùng độ; đơn vị khoảng cách phải ghi trong schema.
- Cache key phải bao gồm site, khoảng thời gian, bước lấy mẫu, tham số Horizons, dataset version và method version.
- Không dùng kết quả placeholder làm kết quả khoa học.

## Quy tắc nhánh

- `main`: bản có thể trình diễn.
- `feature/<ten-ngan>`: thay đổi đang phát triển.
- Mỗi thay đổi dữ liệu hoặc thuật toán cần ghi provenance và cập nhật `docs/decisions/` nếu ảnh hưởng kết quả.

## Backend planning và trợ lý LLM

Backend có API dùng chung cho phân tích điểm, so sánh, tìm cửa sổ, xếp hạng bất định và xuất kết quả. Chat dùng NVIDIA NIM trực tiếp và Gemini dự phòng, truy xuất nguồn của dự án và gọi các engine hiện có; engine giữ quyền quyết định số liệu và trạng thái khoa học.

- `/api/planning/compare`, `/api/planning/windows/search`, `/api/planning/results/{result_id}`.
- `/api/assistant/sessions`, `/api/assistant/sessions/{id}/messages`.
- `/api/assistant/runs/{id}`, `/events`, `/cancel`; lịch sử và kết quả lưu SQLite.
- `/api/assistant/parse`, `/api/assistant/evaluate` giữ tương thích, báo rõ khi giải thích LLM thất bại.
- [Kiến trúc, module, nguồn tham khảo, ví dụ và kết quả kiểm thử](docs/decisions/backend-planning-services.md).

Snapshot giữ phạm vi hai điểm P1 và scenario 72 giờ. Coordinate engine phụ thuộc DEM, Horizons và validation cho đúng tọa độ/thời gian. Chat không suy rộng coverage hay đổi kết luận từ INDETERMINATE thành PASS. Diễn giải ưu tiên nguyên nhân và ý nghĩa, chỉ dùng số liệu chi tiết khi cần; không có giới hạn số từ của câu trả lời.

Xem [thiết lập BE/LLM, cấu hình provider và giới hạn kiểm thử](docs/assistant/BE_LLM_RELEASE.md) và [terminal UTF-8 dùng cùng HTTP backend](docs/demo/assistant-terminal.md). Nhánh này không cập nhật frontend.
