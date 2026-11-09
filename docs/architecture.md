# Kiến trúc nền tảng

## Luồng dữ liệu

`raw source → manifest → adapter → normalized data → domain engine → API response → UI`

## Ranh giới module

- `Data Registry`: provenance, checksum, version và trạng thái coverage.
- `Horizons Adapter`: request, raw response, parser và cache ephemeris.
- `DEM Adapter`: CRS, pixel-to-coordinate, no-data và elevation.
- `Horizon Engine`: profile horizon theo azimuth và chiều cao thiết bị.
- `Visibility Engine`: geometric/terrain visibility, clearance và intervals.
- `Window Analyzer`: metrics, constraints, feasible windows và fail reasons.
- `API`: validation, orchestration, typed response và warnings.
- `UI`: Explore, Compare, Plan; không tự tính lại thuật toán khoa học.

## Moon Explorer và Compare

```text
NASA SVS LROC/LOLA display assets ──→ Three.js global globe
NASA PGDA Site01 DEM ──→ versioned web terrain derivatives ──→ local surface view
processed v0.2.0 GeoJSON/CSV ──→ read-only catalog API ──→ site panel/timeline
processed windows + intervals ──→ Planning API ──→ Compare workspace + export
```

- `frontend/src/components/MoonScene.tsx`: global Moon, camera presets, coordinate grid và local Site01 terrain.
- `backend/app/services/lunarsight/catalog.py`: adapter chỉ đọc, không tái tính metric trong API.
- `/api/lunar/sites`: catalog và provenance.
- `/api/lunar/sites/{site_id}/analysis`: native interval và cửa sổ 72 giờ gần nhất.
- `/api/lunar/coverage`: tách coverage hiển thị khỏi coverage phân tích.
- `/api/lunar/point/terrain`: chọn DEM có độ phân giải tốt nhất đang phủ tọa độ; trả `UNKNOWN` nếu không có raster hợp lệ.
- `/api/lunar/point/terrain-window`: cửa sổ mesh có giới hạn 65/129/257 mẫu để dựng local terrain; chỉ dùng hiển thị, không tái tính khoa học.
- `/api/scenarios`: hợp đồng scenario bất biến và 1.344 mốc bắt đầu/site.
- `/api/sites/{site_id}/profile`: horizon khoa học 1 m hoặc 2 m dùng cho giải thích sự kiện.
- `/api/analyze`: đọc đúng hàng `start_index`, đánh giá lại hai ngưỡng trên cận metric và truy sự kiện trong 72 giờ.
- `/api/results/{result_id}/export`: JSON/CSV tái lập từ result ID xác định theo request chuẩn hóa.

`backend/app/services/lunarsight/planning.py` không chạy lại hình học trong request. Nó chỉ đọc sản phẩm versioned đã kiểm định, từ chối trường scenario thay đổi và lưu bản export tại `data/cache/lunarsight/results/`. UI không được tự tính quyết định.

UI được phép xấp xỉ ánh sáng để minh họa toàn cầu. Mọi kết luận Sun/Earth trong panel phải lấy từ kết quả versioned của pipeline và luôn hiển thị trạng thái `PROVISIONAL` khi kịch bản chưa được phê duyệt.

## Nguyên tắc thiết kế

1. Baseline geometric phải chạy độc lập với terrain mode.
2. Không gọi API ngoài hoặc đọc DEM trong route health.
3. Mọi kết quả phân tích phải trả `provenance`, `warnings` và `method_version`.
4. Cache chỉ được dùng khi request key khớp toàn bộ tham số.
5. Chưa bật terrain mode cho site nếu CRS, coverage hoặc horizon profile chưa qua kiểm tra.
6. Route phân tích không chọn cửa sổ gần nhất; chỉ nhận số nguyên `start_index` trong `[0,1344)`.
7. Kết quả điểm tùy ý không được nâng thành đánh giá landing suitability nếu chưa có horizon/ephemeris và tiêu chí nhiệm vụ tương ứng.
