# Protocol thử tác vụ LunarSight

Mục tiêu là kiểm tra người học có thể so sánh hai site, đổi mốc bắt đầu và giải thích nguyên nhân bị loại mà không cần người hướng dẫn diễn giải kết quả thay họ.

## Mẫu thử

- Tuyển 3–5 người có kiến thức kỹ thuật phổ thông nhưng không tham gia phát triển trực tiếp.
- Mỗi người thực hiện độc lập trên cùng máy demo và cùng phiên bản commit.
- Không cung cấp đáp án; chỉ đọc nguyên văn nhiệm vụ.
- Không ghi tên thật nếu không cần thiết. Dùng mã P01–P05.

## Nhiệm vụ

1. Mở Compare và xác định site nào đạt với start index 0, tối tối đa 12 h, mất Earth LOS tối đa 6 h.
2. Cho biết ràng buộc nào làm mỗi site bị loại.
3. Mở bằng chứng của Site04 và giải thích mối quan hệ giữa Earth elevation, terrain horizon và clearance.
4. Tìm một cấu hình ngưỡng làm cả hai site đạt mà không thay đổi thời lượng hoặc chiều cao.
5. Xuất kết quả CSV và chỉ ra các trường cần thiết để một người khác chạy lại.

## Dữ liệu cần ghi cho từng người

- Mã người thử và nền tảng kiến thức.
- Thời gian bắt đầu/kết thúc từng nhiệm vụ.
- Hoàn thành đúng ngay lần đầu: có/không.
- Số lần nhờ gợi ý và nội dung gợi ý.
- Sai lệch chính: nhầm Sun/Earth, nhầm LOS với liên lạc, nhầm marker horizon hoặc hiểu dải lưới là liên tục.
- Câu giải thích nguyên văn cho nhiệm vụ 3.
- Điểm dễ hiểu nhất, điểm gây chậm nhất và đề xuất thay đổi.

## Tiêu chí nghiệm thu đề xuất

- Ít nhất 4/5 hoặc 3/3 người xác định đúng ràng buộc gây loại.
- Ít nhất 80% nhiệm vụ hoàn thành không cần người hướng dẫn thao tác hộ.
- Trung vị thời gian cho nhiệm vụ 1–3 không quá 3 phút.
- Không người nào diễn giải Earth LOS là bảo đảm chất lượng liên lạc sau khi đọc nhãn giới hạn.
- Mọi lỗi thao tác lặp lại ở hai người trở lên được ghi thành issue trước khi khóa bản demo.

## Biên bản tổng hợp

Ghi phiên bản commit, trình duyệt, độ phân giải, ngày giờ, số người thử và kết luận PASS/FAIL. Đính kèm dữ liệu thô đã ẩn danh, danh sách issue và quyết định sửa hoặc chấp nhận rủi ro. Không ghi PASS trước khi có dữ liệu người dùng thật.

