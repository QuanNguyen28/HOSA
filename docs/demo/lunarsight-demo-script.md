# Kịch bản trình diễn HOSA

Thời lượng mục tiêu: 2 phút. Môi trường: backend cổng 8000, frontend cổng 5173, dữ liệu v0.2.0 đã cache cục bộ.

## Chuẩn bị trước khi ghi

- Chạy `make verify` và lưu log PASS.
- Mở `http://127.0.0.1:5173` ở độ phân giải tối thiểu 1920 × 1080.
- Kiểm tra Explore tải Moon globe, Site01, Site04 và Surface mode.
- Chuyển về Orbit, thời gian 2026-11-14 00:00 UTC.
- Kiểm tra Compare tự tải scenario `south_pole_demo_v1` với ngưỡng tối 12 h và Earth LOS 6 h.
- Tắt thông báo trình duyệt, bookmark bar không cần thiết và ứng dụng nền có thể xuất hiện trong video.

## Lời thoại và thao tác

### 0 đến 20 giây

**Lời thoại:** HOSA là nguyên mẫu giáo dục giúp so sánh hai điểm ứng viên ở cực nam Mặt Trăng cho một hoạt động cố định 72 giờ. Ứng dụng kết hợp địa hình NASA LOLA với vị trí Sun và Earth từ JPL Horizons.

**Thao tác:** Mở Explore, xoay Moon nhẹ, chọn South Pole rồi lần lượt chọn marker Site01 và Site04.

### 20 đến 40 giây

**Lời thoại:** Chế độ Explore cho phép quan sát Mặt Trăng 3D và dựng địa hình cục bộ. Mặt cầu toàn cục phục vụ trực quan; kết luận khoa học chỉ lấy từ dữ liệu đã kiểm định của hai site.

**Thao tác:** Chọn Site01, mở Surface trong vài giây, sau đó chuyển sang Compare.

### 40 đến 75 giây

**Lời thoại:** Hai điểm được đánh giá trên cùng mốc bắt đầu, thời lượng, chiều cao thiết bị và hai ngưỡng. Với mốc đầu tiên, cả hai điểm có Sun liên tục nhưng mất đường nhìn hình học tới tâm Trái Đất vượt giới hạn 6 giờ.

**Thao tác:** Giữ start index 0 và ngưỡng 12/6. Chỉ lần lượt vào kết quả Site01 và Site04, các lane 72 giờ và giá trị longest blackout.

### 75 đến 100 giây

**Lời thoại:** Kết quả không chỉ đưa ra đạt hay không đạt. Người dùng nhấp sự kiện quyết định để truy đúng profile chân trời, phương vị, thời gian và khoảng hở xấu nhất gây che khuất.

**Thao tác:** Nhấp “Sự kiện quyết định” của Site04. Chỉ vào Earth Horizon và marker sự kiện.

### 100 đến 115 giây

**Lời thoại:** Khi đổi giới hạn mất Earth LOS lên 72 giờ và phân tích lại, cả hai phương án chuyển sang đạt theo đúng quy tắc đã công bố. Ứng dụng không tự làm tròn mốc hoặc đổi cấu hình ngầm.

**Thao tác:** Đặt Earth LOS tối đa bằng 72, bấm “Phân tích hai điểm”, chờ hai nhãn chuyển sang ĐẠT.

### 115 đến 120 giây

**Lời thoại:** Mỗi kết quả có thể xuất JSON hoặc CSV cùng request, nguồn, phiên bản dữ liệu và phương pháp để tái lập. HOSA biến dữ liệu khoa học thành một luồng so sánh có thể kiểm tra và giải thích.

**Thao tác:** Chỉ vào hai nút JSON và CSV, kết thúc ở toàn cảnh Compare.

## Tuyên bố bắt buộc

- Earth LOS là hình học tới tâm Trái Đất, không phải link budget vô tuyến.
- Sun visibility không phải mô hình điện hoặc nhiệt.
- Scenario hiện mang nhãn PROVISIONAL và không phải chứng nhận an toàn hạ cánh.

