# HOSA — LunarSight

LunarSight là nguyên mẫu hỗ trợ so sánh điều kiện chiếu sáng Mặt Trời và đường nhìn hình học tới Trái Đất tại các vị trí ứng viên ở cực nam Mặt Trăng.

## Mục tiêu của bộ khung

Bộ khung này tách rõ các lớp dữ liệu, tính toán và giao diện để nhóm có thể phát triển theo trình tự:

1. kiểm tra dữ liệu và provenance;
2. tích hợp JPL Horizons;
3. tạo geometric baseline;
4. tính terrain horizon từ DEM;
5. tính visibility, metric và mission windows;
6. kết nối giao diện Explore và Compare; Plan là backlog sau MVP.

Pipeline dữ liệu đã chạy cho Site01 và Site04 trên Kaggle. Kết quả mẫu dùng kịch bản `PROVISIONAL` bắt đầu ngày 14/11/2026 UTC. Xem [dữ liệu, cách chạy lại và bằng chứng kiểm định](docs/validation/lunarsight/README.md).

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
│   ├── processed/            # dữ liệu chuẩn hóa và kết quả phiên bản v0.2.0
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
{"status":"ok","service":"lunarsight-api","version":"0.1.0"}
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
- marker Site01/Site04 từ catalog v0.2.0;
- visibility Sun/Earth và cửa sổ 72 giờ từ dữ liệu xử lý thật;
- địa hình cục bộ Site01 và Site04, mỗi vùng 16 × 16 km, tạo từ DEM 5 m.
- sinh mesh địa hình 16 × 16 km quanh điểm tùy chọn khi tọa độ nằm trong coverage DEM.
- không gian Compare dùng đúng scenario `south_pole_demo_v1`: 1.344 mốc bắt đầu/site trên lưới 15 phút, nhiệm vụ 72 giờ, ngưỡng tối và mất Earth LOS có thể chỉnh;
- so sánh Site01/Site04 bằng cận metric, ba trạng thái `PASS/FAIL/INDETERMINATE`, timeline sự kiện và horizon profile;
- xuất JSON/CSV kèm cấu hình, nguồn, dataset version và method version.

Ranh giới hiện tại: global texture/bump map và mesh điểm tùy ý chỉ phục vụ hiển thị/khảo sát địa hình. Phân tích Sun/Earth khoa học chỉ hỗ trợ hai candidate site đã xử lý. Ứng dụng không ngoại suy kết quả ra ngoài ephemeris 14/11–01/12/2026 UTC. Earth LOS không phải link budget; Sun visibility không phải mô hình điện hoặc nhiệt.

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
    "constraints":{
      "max_darkness_hours":12,
      "max_earth_blackout_hours":6
    }
  }'
```

`D_hours`, chiều cao thiết bị, bước mô hình và bước lưới là thuộc tính bất biến của scenario. API trả `UNSUPPORTED_CONFIG` thay vì tự làm tròn hoặc thay cấu hình.

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

Backend mới có API dùng chung cho so sánh, tìm cửa sổ, xếp hạng bất định và xuất kết quả. Trợ lý gọi cùng service qua một LLM hai lượt.

- `/api/planning/compare`, `/api/planning/windows/search`, `/api/planning/results/{result_id}`.
- `/api/assistant/parse`, `/api/assistant/evaluate`.
- [Kiến trúc, module, nguồn tham khảo, ví dụ và kết quả kiểm thử](docs/decisions/backend-planning-services.md).

Phạm vi vẫn là hai điểm P1, phần cứng hiện có và nhiệm vụ 72 giờ; các API planning hoạt động độc lập với LLM. Kết quả kiểm thử LLM thật được ghi riêng với kiểm thử offline.

Interactive terminal demo: [live model and scripted rehearsal](docs/demo/assistant-terminal.md).
