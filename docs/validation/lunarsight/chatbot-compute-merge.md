# Ghép chatbot-fix với computing backend

Nhánh đích: `feat/merge-fe-be`. Hai đầu vào được kiểm tra là `ed83e82ee138124c381681987c70291be80df90e` (computing) và `6a7d50c3969ff98737a9da22553cd1b6badb5f57` (`feature/chatbot-fix`). Không dùng nội dung file đính kèm cho lần merge này.

## Quy tắc ghép đã thống nhất

Giữ computing của nhánh đích: hình học ENU/horizon, JPL native 1/5 phút, cận thời lượng, hard/soft/contact requirements, decision gate và resolution 2.1, dữ liệu/cache có kiểm hash, tái dùng JPL theo observer, worker ngắn/dài và khóa theo tài nguyên. Giữ mission >72 giờ và chọn ngày kết thúc trong API/UI/chat.

Lấy các tính năng còn lại từ chatbot-fix: HOSA branding, General chat/Mission planning, provider NIM/Gemini/OpenRouter, citation và chat session/run có lưu trạng thái, catalog/alias dùng chung với Compare, bản đồ/texture NASA và terrain LOD, thông tin địa hình điểm và công cụ nhập dữ liệu mới.

## Các điểm phải nối thủ công

- Chat planning giữ `mission_end_utc`, `duration_hours`, `resolve_indeterminate` và bộ chọn source khi dùng tên mới trong catalog. Lượt sau kế thừa đúng thời lượng và điểm, không tự quay về 72 giờ hoặc Site01.
- Draft được ràng buộc với nguồn computing và catalog tọa độ có tên; thay đổi catalog làm draft cũ báo stale.
- Hủy point computation của chat dùng request lock mới, không đưa trở lại global compute lock. Vẫn đợi checkpoint an toàn khi worker đã bắt đầu.
- Engine evidence đưa `resolution`, phạm vi mission-path, cận bảo thủ và trạng thái full validation riêng sang giải thích chat. Không gọi PASS theo mission bounds là full validation passed.
- Giữ retry atomic-replace dành cho Windows và các stage progress mới của nhánh chatbot.
- Viewer 30 m vẫn dùng được cho xem 3D; không đẩy chiều cao 30 m vào API computing đang nhận tối đa 20 m. UI ghi rõ chiều cao tính toán vẫn nằm trong Mission requirements.
- Test terrain cho phép quality raster không được cài, nhưng kiểm dữ liệu thật khi có và kiểm cảnh báo khi thiếu; không tạo số quality thay thế. Một ca Site06 vẫn skip do DEM tùy chọn không có trên máy này.

## Kiểm thử

- Backend: **384 passed, 1 skipped** (DEM Site06 tùy chọn chưa cài); một deprecation warning Starlette/httpx.
- Frontend: **37 passed**; TypeScript và production build thành công.
- API thật với dữ liệu NASA/JPL đã lưu: point, compare, search, CSV khớp; ca full-sun từ INDETERMINATE thành PASS, ca 0 nắng vẫn FAIL.
- Request end-date 240 giờ qua API trả PASS theo mission-path bounds, giữ full validation=false. Lần tính chưa có result mất khoảng 1.52 s với DEM/JPL đã lưu; lặp lại khoảng 0.13 s trong phép đo ban đầu. Report chạy lại ghi rõ cache-hit để không nhầm là cold compute.
- Trình duyệt: đã chọn Target end date, panel 1 m/antenna 2 m, chạy Site01_P1 17–27/11/2026 với contact requirements và thấy PASS/240 h; hiển thị scope PROVISIONAL và full-model warning đúng. Hai chế độ General chat và Mission planning có mặt; Mission planning có tùy chọn validation.
- Site04 với Sun/Earth 80% không có contact deadline: PASS như ca kiểm tra cũ. Khi thêm deadline contact 120 phút trên UI, cận Earth còn bất định nên ca này vẫn INDETERMINATE; không gộp hai request khác yêu cầu thành cùng một kết quả kỳ vọng.

Đường chạy lại:

```bash
PYTHONPATH=.:backend backend/.venv/bin/pytest -q
cd frontend
npm test
npm run build
```

Với backend chạy cổng 8001 và NASA/JPL đã cài, từ repository root:

```bash
backend/.venv/bin/python scripts/verify_merged_mvp.py \
  --base-url http://127.0.0.1:8001 \
  --output /tmp/chatbot-compute-merge-api.json
```

Báo cáo API kèm theo: `chatbot-compute-merge-api.json`. Script chạy offline mặc định; `--online` mới cho lấy JPL còn thiếu. Các test transport LLM là deterministic tests, không được tính thành live provider success.

## Giới hạn kiểm thử LLM thật

Cấu hình local đang bật assistant và chọn NVIDIA, nhưng chưa có NVIDIA API key (Gemini cũng chưa có key). Có cấu hình OpenRouter riêng nhưng không tự đổi provider hoặc sửa `.env` khi merge. Vì vậy **không chạy inference NVIDIA/Gemini thật**, không khẳng định model đã trả lời thành công. Cần cấu hình key cho provider được chọn để nghiệm thu inference/live chat; không có credential nào được ghi trong report hoặc commit.
