# Từ điển dữ liệu HOSA

| Nhóm | Trường nguồn | Trường chuẩn hóa hoặc tính thêm |
| --- | --- | --- |
| D01 · PGDA 78 | `surf.tif` lưu cao độ mặt đất theo mét. `ldec.tif` lưu lượt đo LOLA. `toterr.tif` lưu sai số RMS cao độ theo mét. Shapefile ROI có đa giác và thuộc tính X/Y. | Danh mục D05 ghi vị trí ô được chọn, giá trị cao độ, số lượt đo và RMS tại ô đó. |
| D02 · PGDA 90 | Hai DEM vùng rộng lưu cao độ theo mét trên lưới 80 m và 240 m. | Lượt quét theo phương vị ghép các DEM để lấy góc che địa hình. |
| D03 · JPL Horizons | UTC, phương vị, góc cao và các cờ gốc trong phản hồi observer. | `utc`, `az_deg`, `el_deg`, `row_present` trong `ephemeris/*.csv`. Một dòng mỗi mốc thời gian của truy vấn. |
| D05 · Điểm quan sát | Hệ chiếu, đa giác ROI và ba raster D01. | `site_id`, `region`, `geometry`, `lon_e_deg`, `lat_deg`, `x_m`, `y_m`, `pixel_row`, `pixel_col`, `dem_z_m`, `roi_id`, `roi_crs_wkt`, `dataset_id`, `dem_sha256`, `coverage_status`, `selection`, `lola_spots_at_site`, `elevation_rms_error_m_at_site`. |
| Đường chân trời | DEM 5/80/240 m, điểm D05 và độ cao thiết bị. | Mỗi hướng có `horizon_deg` và vị trí vật cản quyết định trong `blocker_*`. Các cột `samples_*`, `missing_samples`, `valid_samples`, `fallback_samples` và `coverage_complete` mô tả lượt quét. Tên tệp ghi site, độ cao, bước góc và bán kính. |
| Tầm nhìn 5 phút | Góc Sun/Earth và góc che địa hình theo cùng phương vị. | Mỗi cặp `start_utc`, `end_utc` có `sun_clearance_deg`, `earth_clearance_deg`, trạng thái từng thiên thể, `joint_state` và các cờ chất lượng. Clearance bằng góc cao trừ góc che. `V` là thấy, `B` là bị che, `?` là chưa xác định. |
| Cửa sổ 72 giờ | Các khoảng tầm nhìn giao với cửa sổ. | `total_sun_hours`, `longest_dark_hours`, `longest_blackout_hours`, `longest_joint_hours` đều có cận `_L` và `_U`. `darkness_constraint`, `earth_constraint` và `decision` ghi kết quả áp dụng ngưỡng. |
| Kiểm tra đường ghép | Giá trị cao độ lấy tại cùng vị trí từ hai DEM. | Các bảng `seam_*` ghi sai biệt cao độ và góc, thống kê p95, vị trí ghép và cờ `accepted_for_model`. Các tệp `seam_1` và `seam_2` trùng với bản `seam_fixed_1` và `seam_fixed_2` tương ứng, được giữ làm bằng chứng của các lần chạy. |

Ghép bảng theo `site_id` và thời gian UTC. Cửa sổ 72 giờ và khoảng 5 phút dùng quy ước `[start_utc, end_utc)`. Mỗi cửa sổ có thể giao với nhiều khoảng 5 phút. Hai cửa sổ bắt đầu liền nhau chia sẻ 71 giờ 45 phút.
