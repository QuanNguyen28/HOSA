# Biên bản bàn giao HOSA

Trạng thái: **DRAFT — chưa phải biên bản khóa bản**  
Dataset version: `v0.2.0`  
Method version: `lunar-sphere-enu-v2`  
Scenario: `south_pole_demo_v1` (`PROVISIONAL`)

## 1. Phạm vi bàn giao

Release candidate cung cấp nguyên mẫu web giáo dục để:

- khám phá Mặt Trăng 3D và hai candidate site `Site01_P1`, `Site04_P1`;
- so sánh 1.344 mốc bắt đầu/site trên lưới 15 phút cho hoạt động cố định 72 giờ;
- đánh giá giới hạn khoảng tối và mất Earth LOS hình học bằng mô hình ba trạng thái;
- truy sự kiện quyết định tới timeline, azimuth, elevation, terrain horizon và clearance;
- xuất JSON/CSV kèm request, nguồn và phiên bản phương pháp.

Ngoài phạm vi: chứng nhận an toàn hạ cánh, mô hình điện/nhiệt, link budget, xác suất
thành công, phân tích Sun/Earth cho điểm tùy ý và thay đổi ngầm cấu hình scenario.

## 2. Danh mục bàn giao

| Mã | Artifact | Trạng thái | Bằng chứng |
|---|---|---|---|
| BD01 | Ứng dụng HOSA | READY FOR RC | `frontend/`, `backend/`, application acceptance |
| BD02 | Mã nguồn và môi trường | READY FOR RC | README, lockfile, pyproject, scripts |
| BD03 | Dữ liệu và cấu hình | READY FOR RC | `data/processed/lunarsight/v0.2.0`, `manifests/lunarsight` |
| BD04 | Hồ sơ chất lượng | READY FOR RC | scientific validation, sensitivity, pytest, release audit |
| BD05 | Hồ sơ trình diễn | PARTIAL | script và English copy có; video/ảnh/public links còn thiếu |
| BD06 | Biên bản bàn giao | DRAFT | tài liệu này; thiếu người nhận và release commit |

## 3. Cách xác minh và vận hành

```bash
make release-check
make backend-run
make frontend-run
```

Mở `http://127.0.0.1:5173`. Backend health:
`http://127.0.0.1:8000/api/health`.

Kết quả audit được ghi tại
`docs/validation/lunarsight/v0.2.0/reports/release_audit.json`. Không nhận bàn giao
nếu `technical_status` khác `PASS`, worktree chưa khóa hoặc commit trong biên bản
không trùng release candidate.

## 4. Cổng còn mở

- G0: ký `docs/approvals/g0-signoff.md`; trước đó phải giữ `PROVISIONAL`.
- Quyền công bố: chủ sở hữu chọn giấy phép OSI và xác nhận không có nội dung bí mật.
- AC11/T19: thử tác vụ với 3–5 người thật và lập biên bản kết quả.
- AC12/T20: video, ảnh, repository/demo URL public, kiểm tra link chưa đăng nhập và
  bản dự phòng.
- G6: xác nhận biểu mẫu nộp 2026 thực tế và khóa release commit.

## 5. Rủi ro đã chấp nhận hoặc cần quyết định

- Sai biệt chân trời cực đại cục bộ vượt tolerance góc 0,1° ở kiểm tra độ phân giải;
  quyết định 72 giờ không đổi trong các ca đã ghi, nhưng UI phải giữ nhãn độ nhạy.
- Scenario và hai ngưỡng là cấu hình minh họa, không phải yêu cầu nhiệm vụ thật.
- Global sphere/mesh tùy ý phục vụ trực quan địa hình; kết luận khoa học giới hạn ở
  hai site đã xử lý.

## 6. Xác nhận bàn giao

| Trường | Giá trị |
|---|---|
| Release commit/tag | REQUIRED |
| Source archive SHA-256 | REQUIRED |
| Data manifest/release URL | REQUIRED |
| Người bàn giao | REQUIRED |
| Người nhận | REQUIRED |
| QA xác nhận | REQUIRED |
| Ngày giờ và múi giờ | REQUIRED |
| Kết luận | REQUIRED: ACCEPTED / ACCEPTED WITH CONDITIONS / REJECTED |

Điều kiện hoặc ghi chú: `REQUIRED`

