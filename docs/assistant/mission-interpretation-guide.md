# HOSA: giải thích kết quả cho người dùng

Current reference. Metric meanings and evidence mapping are implemented in backend/app/assistant/interpretation.py. Numerical decisions continue to come from app.mission.evaluation and planning services.

## Mục tiêu cuộc thi và dự án

Theo đề bài Lunar Landing Site Navigator do người dùng cung cấp, công cụ cần giúp mission planners, educators và công chúng so sánh nhanh vị trí và ngày hoạt động ở cực Nam Mặt Trăng, quan sát Sun và Earth so với chân trời, hiểu tiềm năng chiếu sáng và cửa sổ đường nhìn trực tiếp về Trái Đất. Tương tác dễ hiểu và giải thích trade-off là mục tiêu; chatbot hỗ trợ hiểu và sử dụng công cụ hiện có.

HOSA dùng NASA LOLA/PGDA, JPL Horizons và terrain horizon. Engine xác định số liệu, ngưỡng, xếp hạng và quyết định. Chatbot trả lời câu hỏi bằng các nguồn và kết quả đã tính, giải thích ý nghĩa đối với yêu cầu cụ thể. Các phép tính được giới hạn bởi capabilities, nguồn dữ liệu và validation hiện tại. Chỉ có dữ liệu trong catalog chưa chứng minh một nhiệm vụ khả thi.

## Ý nghĩa chỉ số

Total sun hours / tổng thời gian có nắng: tổng thời gian tâm Mặt Trời khả kiến trong cửa sổ nhiệm vụ. Các khoảng có thể rời nhau. Chỉ số mô tả cơ hội chiếu sáng; không cho biết điện năng hoặc an toàn nhiệt. Tổng nắng đủ không chứng minh có nắng liên tục.

Total Earth LOS / tổng thời gian nhìn thấy Trái Đất: tổng thời gian tâm Trái Đất khả kiến về mặt hình học. Các khoảng có thể rời nhau. Tổng thời gian cao không chứng minh có cửa sổ liên tục đủ dài, chất lượng sóng vô tuyến hay lịch trạm mặt đất.

Longest darkness / khoảng tối liên tục dài nhất và longest blackout / khoảng mất Earth LOS liên tục dài nhất: đánh giá tính liên tục trong đúng cửa sổ nhiệm vụ. Giới hạn tối đa do người dùng đặt là mong muốn mềm; vượt nó không tự tạo hard FAIL. Sự kiện chạm biên có thể kéo dài ra ngoài khoảng đã đánh giá. Không suy ra thời lượng pin từ thời gian tối.

Longest joint visibility: khoảng liên tục dài nhất có cả Sun và Earth khả kiến, không phải điểm chất lượng tổng hợp hay chứng nhận điện và liên lạc.

Contact window / cửa sổ liên lạc: khoảng Earth LOS liên tục còn dùng được sau setup. Yêu cầu có thể gồm thời lượng tối thiểu, số cửa sổ riêng biệt, hạn hoàn tất liên lạc đầu tiên. Số cửa sổ không phải số phiên nhét vào cùng cửa sổ. Engine contact đánh giá yêu cầu cứng này; chatbot dùng sampled_checks và quyết định đã qua validation.

Bounds / cận dưới và trên phản ánh trạng thái khả kiến đã biết và chưa biết. Chúng không phải xác suất thành công hay khoảng tin cậy thống kê.

## Giải thích quyết định

PASS đáp ứng các yêu cầu cứng đã đánh giá và validation cần thiết; FAIL vi phạm yêu cầu cứng; INDETERMINATE chưa đủ căn cứ kết luận. Kết quả nominal và quyết định cuối cùng có thể khác nhau khi validation không đạt. Luôn giữ quyết định cuối của engine.

Một sự kiện bị chắn có thời gian, hướng và góc so với terrain horizon giúp giải thích kết quả. Chỉ khẳng định địa hình cụ thể gây chắn khi có bằng chứng tương ứng; không tự đặt tên crater/ridge hoặc suy ra nguyên nhân từ một tổng số giờ.

Khi người dùng hỏi vì sao không đạt, nêu yêu cầu quyết định và ý nghĩa của nó. Khi hỏi phương án tốt hơn, dùng xếp hạng và phạm vi đã tính, giải thích trade-off. Khi thiếu mốc bắt đầu, chỉ hỏi mốc đó; các mong muốn mềm tùy chọn không phải điều kiện để bắt đầu. Không đưa field/schema/code vào câu trả lời.

Trả lời trực tiếp trước, giải thích bằng vài câu liên quan. Chỉ đưa số cần cho lập luận và nguồn tương ứng; dành bảng chi tiết cho yêu cầu so sánh hoặc khi người dùng muốn xem thêm. Không kể lại toàn bộ dự án cho một câu hỏi tiếp nối.
