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

## Nguyên tắc thiết kế

1. Baseline geometric phải chạy độc lập với terrain mode.
2. Không gọi API ngoài hoặc đọc DEM trong route health.
3. Mọi kết quả phân tích phải trả `provenance`, `warnings` và `method_version`.
4. Cache chỉ được dùng khi request key khớp toàn bộ tham số.
5. Chưa bật terrain mode cho site nếu CRS, coverage hoặc horizon profile chưa qua kiểm tra.
