# HOSA — LunarSight

LunarSight là nguyên mẫu hỗ trợ so sánh điều kiện chiếu sáng Mặt Trời và đường nhìn hình học tới Trái Đất tại các vị trí ứng viên ở cực nam Mặt Trăng.

## Mục tiêu của bộ khung

Bộ khung này tách rõ các lớp dữ liệu, tính toán và giao diện để nhóm có thể phát triển theo trình tự:

1. kiểm tra dữ liệu và provenance;
2. tích hợp JPL Horizons;
3. tạo geometric baseline;
4. tính terrain horizon từ DEM;
5. tính visibility, metric và mission windows;
6. kết nối giao diện Explore, Compare và Plan.

Trong giai đoạn đầu, repository chỉ cam kết API health và cấu trúc module. Chưa đưa tọa độ thật, kết quả tính hoặc token dịch vụ vào mã nguồn.

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
│   ├── processed/            # dữ liệu chuẩn hóa, có version
│   └── cache/                # cache Horizons và kết quả tính
├── manifests/                # catalog, checksum, request config
├── scripts/                  # script tải, kiểm tra và tạo cache
├── docs/                     # quyết định kỹ thuật, validation, giới hạn
├── tests/                    # dành cho test về sau; chưa có test giả
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

## Quy tắc dữ liệu

- `data/raw/` không sửa sau khi tải; mọi nguồn phải có bản ghi trong `manifests/datasets.csv`.
- Không commit GeoTIFF lớn, credential hoặc response chứa thông tin nhạy cảm.
- Mọi thời gian dùng UTC ISO 8601; mọi góc dùng độ; đơn vị khoảng cách phải ghi trong schema.
- Cache key phải bao gồm site, khoảng thời gian, bước lấy mẫu, tham số Horizons, dataset version và method version.
- Không dùng kết quả placeholder làm kết quả khoa học.

## Quy tắc nhánh

- `main`: bản có thể trình diễn.
- `feature/<ten-ngan>`: thay đổi đang phát triển.
- Mỗi thay đổi dữ liệu hoặc thuật toán cần ghi provenance và cập nhật `docs/decisions/` nếu ảnh hưởng kết quả.
