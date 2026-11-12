# MVP frontend–backend

Nhánh tích hợp: `feat/merge-fe-be`. Nguồn frontend: `feature/lunarsight-frontend` (`23ab188`); nguồn backend: `feat/fix-compute-backend` (`1e5d598`) cộng bản sửa rà soát (`06920a2`). Merge nguồn được giữ trong lịch sử; không sửa hoặc push hai nhánh nguồn.

## Phát hiện khi ghép

- Nhánh FE đã kế thừa backend đến `1e5d598`, nhưng chưa có sửa lỗi review trong workspace.
- Entry point FE chuyển sang bản Figma Make. `figma/model.ts` tạo horizon/ephemeris giả lập; Compare/Best dates tính từ các hàm này và Chat trả lời bằng heuristic trong browser.
- Các tọa độ template Connecting Ridge/Shackleton không phải tọa độ P1 trong catalog backend; mapping tên template sang Site01/Site04 không thể được dùng làm bằng chứng khoa học.
- Frontend cho phép 7–30 ngày và chiều cao 30 m, vượt giới hạn backend 1–72 giờ, chiều cao >0 đến 20 m.
- Công cụ catalog mới cần Shapely 2.1+, chưa được khai báo trong dependency backend. `.env.example` bị xóa trên nhánh FE.

## Tích hợp MVP

Giữ entry point gốc `frontend/src/figma/App.tsx` của nhánh frontend: header/tab, panel Site/All sites, viewer Moon/Pole/Ground, thanh thời gian, compare cards, lưới Best dates và Ask dock. Các luồng dữ liệu trong shell này đã thay bằng API thật. Module `frontend/src/mvp/` chỉ chứa hợp đồng request, API/job client và ngữ cảnh assistant; không có workspace giao diện thay thế. Các hàm sinh horizon/ephemeris/metric giả lập và chat heuristic đã được gỡ khỏi module Figma; số liệu đến từ backend.

| Màn | API | Hành vi |
|---|---|---|
| Explore | `/lunar/sites`, `/lunar/point/analyses`, status/result | Chọn tọa độ chính xác, tạo job, theo dõi tiến độ, hiện metric/check/validation/contact/timeline từ backend |
| Terrain | `/lunar/point/terrain-window` | Mesh DEM thật; không dùng nhầm mesh cũ khi đổi điểm; ánh sáng 3D ghi rõ chỉ là preview |
| Compare | `/planning/compare` với `data_source=coordinate` | Cùng đầu vào nhiệm vụ với point; đề xuất chỉ khi PASS sau gate |
| Best dates | `/planning/windows/search` | Khoảng bắt đầu nửa mở, chặn vượt 128 phép đánh giá; hiển thị cả số lượng unknown |
| Export | `/planning/results/{id}` | JSON/CSV của kết quả đã lưu; point tải nguyên JSON API |
| Assistant | `/assistant/capabilities`, `/parse`, `/evaluate` | LLM thật phía server, review/confirm, clarification, giữ ngữ cảnh và lựa chọn site giữa các lượt/tab |

Mọi endpoint trong bảng có prefix `/api`. Frontend không nhận khóa OpenRouter. Khi backend tắt assistant, UI hiện trạng thái disabled, không giả lập câu trả lời.

Assistant nhận tên hoặc mã của các điểm trên Compare, tối đa hai điểm mỗi lượt, với cấu hình demo 72 giờ và panel/antenna 1/2 m. Kịch bản 72 giờ với Site01_P1/Site04_P1 dùng snapshot. Khi có điểm ngoài snapshot, mốc kết thúc hoặc thời lượng khác, cả lượt dùng pipeline theo tọa độ, phụ thuộc DEM và JPL Horizons tại vị trí và thời gian yêu cầu. Có thể bật kiểm định bổ sung cho kết quả chưa đủ căn cứ. Chat giữ bước xác nhận trước khi tính.

## Chạy từ repo root

Yêu cầu Python 3.11+, Node 22.12+, npm 10.5.1+. `frontend/.nvmrc` khai báo Node 22.

```bash
make backend-install
make frontend-install
backend/.venv/bin/python scripts/prepare_point_data.py
```

Dữ liệu NASA cần khoảng 0,5 GB; không tự tải bộ full-product lớn để chạy MVP. Dữ liệu thô/cache cá nhân và khóa API không được commit.

Hai terminal:

```bash
make backend-run
```

```bash
make frontend-run
```

Mở `http://127.0.0.1:5173`. Có thể trỏ Vite dev hoặc preview tới backend khác qua `LUNARSIGHT_BACKEND_URL`.

Mẫu mặc định: bắt đầu 24/11/2026 UTC, 72 giờ, panel/antenna 20 m, nắng tối thiểu 80%, contact 30 phút + setup 5 phút, 1 window và deadline hoàn thành phút 120. Các giá trị này là cấu hình kiểm chứng, không phải khuyến nghị phần cứng hay tiêu chuẩn nhiệm vụ.

- Example A: (-88.80771296769387, 123.81313283430084).
- Example B: (-87, 180).

Mở All sites để chọn Example A/B, hoặc mở Choose / enter coordinates để nhập tọa độ. Điểm ban đầu vẫn là Connecting ridge của UI gốc. Bấm Analyze để tính; không hiển thị số liệu tính sẵn trong JS. Chọn ngày/điểm mới có thể cần JPL và mất vài phút. Cache-only mode thiếu cache đúng đầu vào sẽ báo thiếu bằng chứng.

## Kiểm chứng trước push

```bash
make verify
backend/.venv/bin/python scripts/verify_mvp_api.py --base-url http://127.0.0.1:8000
```

Thêm `--offline` khi đã có cache JPL cho hai request mẫu. Script chỉ gọi API thật, không dùng LLM và không tạo metric tổng hợp. Nó đối chiếu direct/compare/search, ID phương án, validation và export.

Kiểm thử trình duyệt dùng Chrome thật qua Playwright CLI, thao tác biểu mẫu/nút tải và đối chiếu file tải với response API. Bằng chứng cục bộ được giữ dưới `output/playwright/` (gitignored). Xem báo cáo tại `docs/validation/lunarsight/fe-be-mvp-acceptance.md`.

## Giới hạn còn giữ

- Metric là hình học tâm Sun/Earth, lấy mẫu, ngưỡng PROVISIONAL; chưa có RF/điện/nhiệt hay chứng nhận hạ cánh.
- Coverage phụ thuộc DEM và ephemeris thực có; `INDETERMINATE` không được đổi thành FAIL hoặc PASS.
- API snapshot legacy vẫn được giữ để tương thích; MVP coordinate không gọi `/api/analyze` legacy để quyết định.
- Search đồng bộ có thể lâu khi cần nhiều truy vấn JPL mới. MVP giới hạn 128 phép đánh giá và không tự quét cả năm.
