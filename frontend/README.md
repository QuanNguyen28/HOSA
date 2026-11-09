# LunarSight web

Moon Explorer là giao diện mô phỏng 3D realtime dùng React, Three.js và dữ liệu hiển thị NASA LRO/LOLA.

## Chạy local

```bash
cd frontend
npm install
npm run dev
```

Vite proxy `/api` tới backend tại `http://127.0.0.1:8000`.

## Ranh giới khoa học

- Texture LROC và bump map LOLA trong `public/assets/nasa/` chỉ phục vụ hiển thị.
- Kết quả khoa học phải lấy từ backend và mang theo `provenance`, `warnings` và `method_version`.
- Chuyển động Mặt Trời trong Moon Viewer v0.1 là phép xấp xỉ trực quan và được ghi rõ trong metadata; không dùng làm kết quả mission planning.
- Site01/Site04 lấy từ snapshot `data/processed/lunarsight/v0.2.0/site_catalog.geojson` khi API chưa chạy.
- Điểm tùy chọn gọi `/api/lunar/point/terrain`; Surface mode chỉ dựng mesh khi backend xác nhận coverage.

## Hai không gian thao tác

- **Explore**: Moon globe 3D, camera Orbit/South Pole/Surface, catalog site và khảo sát DEM tại tọa độ tùy ý.
- **Compare**: scenario cố định 72 giờ, mốc bắt đầu trên lưới 15 phút, hai ngưỡng chỉnh được, kết quả Site01/Site04, timeline và horizon giải thích.

Compare gọi `/api/scenarios`, `/api/analyze` và `/api/sites/{id}/profile`. Mọi quyết định và metric đến từ backend; SVG chỉ biểu diễn profile đã kiểm định. Nút JSON/CSV tải bản export chứa request và provenance.

## Nguồn asset

NASA Scientific Visualization Studio, CGI Moon Kit, ID 4720:

- `lroc_color_2k.jpg`: LROC WAC color mosaic, hiển thị thẩm mỹ.
- `ldem_3_8bit.jpg`: LOLA global elevation preview, dùng làm bump map.

Credit: NASA's Scientific Visualization Studio; Ernie Wright (USRA); Noah Petro (NASA/GSFC).
