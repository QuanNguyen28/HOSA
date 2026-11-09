# Checklist khóa bản LunarSight

## Kỹ thuật

- [ ] `make release-check` đạt trên commit dự kiến nộp; lưu `release_audit.json`.
- [ ] Backend và frontend khởi động từ README trên máy sạch hoặc môi trường dự phòng.
- [ ] Explore tải Moon globe và hai site khi ngắt Internet sau khi cache.
- [ ] Compare chạy start index 0 và một mốc khác; JSON/CSV mở được.
- [ ] Không có request ngoài ý muốn tới JPL/NASA trong luồng demo offline.
- [ ] Provenance, attribution và cảnh báo mô hình hiển thị đúng.

## Khoa học và sản phẩm

- [ ] G0 tại `docs/approvals/g0-signoff.md` ghi người phê duyệt epoch, hai ngưỡng minh họa và tolerance; nếu chưa có, giữ nhãn PROVISIONAL.
- [ ] Site01 và Site04 dùng cùng scenario và method version.
- [ ] Sự kiện quyết định truy đúng site, body, timestamp, horizon và clearance.
- [ ] Kiểm tra người dùng 3–5 người được ghi tại `user_test_results.md` và issue quan trọng đã xử lý.
- [ ] Không gọi kết quả là landing certification, link budget, power model hoặc xác suất thành công.

## Hồ sơ nộp

- [ ] Tên đội, Local/Universal Event và danh sách thành viên đã xác nhận.
- [ ] Chủ sở hữu đã chọn giấy phép OSI, tạo `LICENSE` và xác nhận quyền công bố mã nguồn/dữ liệu/media.
- [ ] Yêu cầu đang áp dụng được đối chiếu với `docs/submission/2026-official-requirements.md` và Project Tab thực tế.
- [ ] Mô tả tiếng Anh trong `docs/submission/project-description-en.md` đã thay hết trường `REQUIRED` và khớp chức năng thực tế.
- [ ] Repository/link demo có quyền truy cập phù hợp.
- [ ] Video theo kịch bản `docs/demo/lunarsight-demo-script.md`, đúng thời lượng và định dạng hiện hành.
- [ ] Ảnh đại diện, ảnh giao diện và credit nguồn NASA/JPL đầy đủ.
- [ ] Media được chụp theo `docs/submission/media-shot-list.md` từ đúng release commit.
- [ ] Kiểm tra liên kết trên một trình duyệt chưa đăng nhập.
- [ ] Lưu một bản video, source archive và data manifest dự phòng ngoại tuyến.
- [ ] Trên worktree sạch, chạy `make package-release`; đối chiếu SHA-256 trong manifest.
- [ ] Điền và ký `docs/handover/release-handover.md` bằng đúng release commit/tag.
