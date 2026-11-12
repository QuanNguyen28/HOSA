# Shot list hồ sơ và video HOSA

Trạng thái: **READY TO CAPTURE — chưa có media khóa bản**.

Mọi ảnh/video phải được chụp từ đúng release commit đã ghi trong biên bản bàn giao.
Không dùng mockup hoặc dữ liệu placeholder để minh họa kết quả khoa học.

## Thiết lập chung

- Khung hình mục tiêu: 1920 × 1080; browser zoom được ghi lại và giữ nhất quán.
- Ẩn bookmark bar, thông báo, thông tin tài khoản và ứng dụng nền.
- Giữ nhãn `PROVISIONAL`, nguồn NASA/JPL và giới hạn mô hình nhìn thấy được.
- Dùng scenario `south_pole_demo_v1`, dataset `v0.2.0` và start index 0 trừ khi
  caption ghi rõ cấu hình khác.
- Lưu PNG gốc; không chỉnh sửa số liệu, trạng thái, timestamp hoặc biểu đồ.
- Tên file dùng ASCII, ngày và thứ tự, ví dụ `lunarsight-01-explore-20261114.png`.

## Ảnh bắt buộc đề xuất

| ID | Khung hình | Trạng thái UI | Điều phải chứng minh | Caption tiếng Anh |
|---|---|---|---|---|
| S01 | Explore toàn cảnh | Orbit, Moon globe, hai marker | Công cụ 3D và phạm vi cực nam | Explore the Moon and two supported south-pole candidate sites in a shared 3D view. |
| S02 | Địa hình cục bộ | Site01, Surface | DEM cục bộ và vị trí observer | Inspect the local NASA LOLA terrain used to derive the site horizon. |
| S03 | Compare đầy đủ | index 0, ngưỡng 12 h/6 h | Hai site, cùng scenario, timeline và quyết định | Compare both sites under the same 72-hour scenario and explicit constraints. |
| S04 | Bằng chứng sự kiện | Site04 Earth event được chọn | Azimuth, elevation, horizon, clearance cùng sự kiện | Trace a disqualifying Earth-visibility event to its terrain-horizon evidence. |
| S05 | Export/provenance | nút JSON/CSV và version nhìn thấy | Khả năng tái lập | Export the request, source versions and result metadata for reproducibility. |

## Thumbnail

Ưu tiên bố cục từ S03 hoặc tổ hợp Moon globe + Compare, nhưng không ghép khiến
người xem hiểu nhầm toàn bộ Mặt Trăng đã được phân tích. Tên dự án đọc được ở kích
thước nhỏ; không dùng logo NASA như logo dự án và không hàm ý NASA bảo trợ.

## Video hai phút nội bộ

Thực hiện theo `docs/demo/lunarsight-demo-script.md`. Bắt đầu và kết thúc bằng ứng
dụng thật; mỗi phát biểu khoa học phải tương ứng với trạng thái đang hiển thị. Nếu
Project Tab 2026 yêu cầu thời lượng khác, điều chỉnh nhịp nhưng giữ nguyên trình tự:

1. vấn đề và hai site;
2. Explore/Surface;
3. Compare cùng cấu hình;
4. sự kiện quyết định và terrain evidence;
5. đổi ngưỡng có chủ đích;
6. export, provenance và giới hạn.

## Kiểm tra trước công bố

- [ ] Release commit trong media trùng biên bản bàn giao.
- [ ] Không có credential, email, tab riêng tư hoặc PII.
- [ ] Người xuất hiện/đọc lời thoại đã đồng ý theo điều khoản.
- [ ] Credit NASA LOLA/PGDA và JPL Horizons có trong caption hoặc end card.
- [ ] Không gọi Earth LOS là bảo đảm liên lạc hoặc Sun visibility là công suất.
- [ ] Không gọi kết quả là landing certification.
- [ ] File mở được trên thiết bị khác và link hoạt động khi chưa đăng nhập.

