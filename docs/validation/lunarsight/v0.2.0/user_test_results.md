# Biên bản kết quả thử tác vụ LunarSight

Trạng thái: **NOT RUN — không được đổi thành PASS nếu chưa có người thử thật**.

## Thông tin phiên thử

| Trường | Giá trị |
|---|---|
| Commit/release candidate | REQUIRED |
| Ngày, giờ, múi giờ | REQUIRED |
| Người điều phối | REQUIRED |
| Trình duyệt và phiên bản | REQUIRED |
| Hệ điều hành | REQUIRED |
| Độ phân giải/zoom | REQUIRED |
| Số người thử độc lập | REQUIRED (3–5) |

Protocol nguồn:
`docs/validation/lunarsight/v0.2.0/user_test_protocol.md`.

## Dữ liệu theo người thử

Chỉ dùng mã P01–P05. Không ghi thông tin nhận dạng không cần thiết.

| Participant | Nền tảng | T1 đúng lần đầu / giây / gợi ý | T2 đúng lần đầu / giây / gợi ý | T3 đúng lần đầu / giây / gợi ý | T4 đúng lần đầu / giây / gợi ý | T5 đúng lần đầu / giây / gợi ý | Hiểu đúng giới hạn LOS? |
|---|---|---|---|---|---|---|---|
| P01 | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| P02 | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| P03 | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| P04 | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL |
| P05 | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL | OPTIONAL |

## Câu giải thích nguyên văn cho nhiệm vụ 3

- P01: `REQUIRED`
- P02: `REQUIRED`
- P03: `REQUIRED`
- P04: `OPTIONAL`
- P05: `OPTIONAL`

## Tổng hợp định lượng

| Chỉ số nghiệm thu | Kết quả | Ngưỡng | PASS/FAIL |
|---|---:|---:|---|
| Người xác định đúng ràng buộc gây loại | REQUIRED | 3/3 hoặc ít nhất 4/5 | REQUIRED |
| Tỷ lệ nhiệm vụ hoàn thành không cần thao tác hộ | REQUIRED | ≥ 80% | REQUIRED |
| Trung vị thời gian nhiệm vụ 1–3 | REQUIRED | ≤ 180 giây | REQUIRED |
| Người hiểu nhầm Earth LOS sau khi đọc cảnh báo | REQUIRED | 0 | REQUIRED |

## Quan sát và issue

| ID | Quan sát/lỗi lặp lại | Số người gặp | Mức độ | Quyết định | Issue/commit bằng chứng |
|---|---|---:|---|---|---|
| UT-01 | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED |

Điểm dễ hiểu nhất: `REQUIRED`  
Điểm gây chậm nhất: `REQUIRED`  
Đề xuất nổi bật: `REQUIRED`

## Kết luận

- [ ] PASS — đạt toàn bộ tiêu chí và các lỗi lặp lại đã được xử lý hoặc chấp nhận
  rủi ro bằng quyết định có người chịu trách nhiệm.
- [ ] FAIL — chưa đạt ít nhất một tiêu chí.
- [x] NOT RUN — chưa có dữ liệu người dùng thật.

Người lập biên bản: `REQUIRED`  
Người QA xác nhận: `REQUIRED`  
Ngày giờ và múi giờ: `REQUIRED`

