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
