# Kiểm tra INDETERMINATE và hiệu năng thực tế

Ngày kiểm tra: 12/11/2026. Nhánh `feat/merge-fe-be`; resolution policy `indeterminate-resolution-2.1`.

## Kết quả trên dữ liệu thật

Dùng NASA LOLA đã kiểm receipt/hash và raw JPL đã kiểm observer/frame/grid/hash. Các lần tính đầu trong benchmark có cache kết quả riêng, rỗng; không dùng kết quả hoàn tất sẵn để giả lập tính nhanh. Không có dữ liệu khoa học synthetic trong báo cáo này.

Bốn ca 72 giờ được chọn để kiểm tra các đường xử lý, không phải khảo sát ngẫu nhiên toàn vùng cực:

| Ca | Tắt xử lý bổ sung | Bật xử lý bổ sung | Tính lại với DEM/JPL đã lưu, chưa có result |
|---|---|---|---:|
| Site01_P1, 17–20/11, Sun/Earth ≥80% | INDETERMINATE | PASS | 1.78 s |
| Site04_P1, 17–20/11, Sun/Earth ≥80% | INDETERMINATE | PASS | 1.60 s |
| (−86.61104682°, 336.25717785°E), 24–27/11, Sun ≥80% và contact requirements | FAIL | FAIL, Sun 0/72 h | 0.95 s |
| Site04_P1, 17–20/11, Sun ≥80%, Earth LOS 100% | INDETERMINATE | INDETERMINATE | 2.98 s |

Trong nhóm này, số INDETERMINATE giảm **3 → 1**. Không suy rộng thành tỷ lệ giảm trên mọi tọa độ. Ca yêu cầu Earth LOS 100% chưa được chứng minh bởi cận bảo thủ; các phút chưa chắc chắn vẫn là `?`, không được biến thành V. Site04 với yêu cầu Earth 80% có cận Earth LOS 69.4167–72 h, vượt 57.6 h yêu cầu. `validation.passed` toàn cục ở các ca PASS này vẫn false; mission-path bounds mới đủ kết luận yêu cầu. Ngưỡng không đổi, vẫn PROVISIONAL.

Điểm người dùng thử thêm trên UI (−80.08468884°, 319.30117015°E), 24–27/11, vẫn INDETERMINATE với `DEM_SEAM_FAILED`. Chỉ 3190/7920 và 3180/7920 mẫu tương ứng ở hai phase có đủ cặp DEM80/DEM240 tại vùng seam, thấp hơn yêu cầu 90%. Các cặp có dữ liệu có sai lệch nhỏ (p95 góc khoảng 0.0089°), nên không được diễn giải mã lỗi này thành đã chứng minh hai DEM lệch datum. Đây là thiếu bằng chứng kiểm chứng seam, không phải nhóm chỉ độ nhạy số được phép fallback. Không ép ca này thành PASS dù nominal Sun/Earth đều 72 giờ.

## Tái hiện trường hợp 72 giờ chậm khoảng 30 giây

So sánh đúng cùng yêu cầu Site01 72 giờ, cùng DEM/JPL đã lưu, cùng profile ban đầu 0.125°/0.25°. Cả hai cache thử nghiệm đều chưa có result cuối hoặc profile refinement. Một bản pipeline trước thay đổi được lưu tạm và chạy đối chứng.

| Thành phần | Trước: refinement rồi mới kiểm chứng | Sau: kiểm chứng bằng dữ liệu hiện có trước |
|---|---:|---:|
| Tổng thời gian | 26.94 s | 0.92 s |
| Quét/đọc geometry | 25.26 s | 0.008 s |
| Đọc/kiểm raw JPL | 0.53 s | 0.46 s |
| Số lượt refinement | 1 | 0 |
| Quyết định | PASS | PASS |
| Full validation | false | false |
| Mission bounds | passed | passed |

Lượt quét mới chiếm phần lớn chi phí trước đây, dù các profile ban đầu đã đủ chứng minh mọi hard requirement. Bản mới kiểm chứng trước; vẫn refinement tối đa hai lần nếu cận chưa kết luận được. Không hạ ngưỡng, sửa góc Sun, hoặc giả định nắng khi thiếu dữ liệu. Cache identity tăng policy lên 2.1 để phân biệt bằng chứng từ các cấu hình khác nhau.

Đây là **một phép đo chẩn đoán trên máy đang dùng**, không phải tốc độ tối thiểu hay cam kết tăng tốc toàn pipeline 29 lần. Các thời gian gồm chi phí đọc file và xác minh input; cache hệ điều hành/DEM hash và tải CPU có thể khác giữa các lượt.

## Điểm mới vẫn có chi phí riêng

Đã kiểm tra chính request trên UI: Connecting ridge (−89.4398°, 222.83°E), 24–27/11/2026, panel/antenna 20 m, Sun 80% và contact requirements.

| Trạng thái dữ liệu | Thời gian đo |
|---|---:|
| Chưa có horizon điểm này; raw JPL đã có | 19.98 s, trong đó geometry 18.87 s |
| Có horizon/raw JPL; tính lại, chưa có result | 1.53 s |
| Gọi lại đúng result đã hoàn tất qua API thật | 0.56 s |

Điểm Connecting ridge này PASS và **full numerical validation cũng passed**. Chi phí lần đầu quét địa hình quanh tọa độ không tỉ lệ với thời lượng nhiệm vụ: 72 giờ vẫn phải lấy horizon đủ 360° và các kiểm tra sensitivity. Đổi tọa độ hoặc độ cao thiết bị có thể cần geometry mới. Nếu raw JPL chưa có, thời gian mạng được cộng thêm; vì vậy điểm hoàn toàn mới vẫn có thể mất hàng chục giây. Không tuyên bố mọi request hiện đều dưới một giây.

API thật của bốn ca trong bảng đầu trả 0.28–0.68 s khi dùng result cache, trong lúc có request dài và request ngắn khác đang xử lý. Số liệu API bao gồm HTTP và response schema/serialization; khác với thời gian đọc cache Python thuần.

## Vì sao bản FE gốc có thể chạy hai năm rất nhanh?

Đã đọc source revision `23ab18862a4298b5adacc57298b144c788a75ee5` của `feature/lunarsight-frontend`. Trong `frontend/src/figma/model.ts`, `maskFor()` tạo horizon từ `hash(site.id)` và các hàm sin; `bodiesAt()` xấp xỉ góc Sun/Earth bằng các chu kỳ sin; `buildSeries()` chạy các công thức đó trên trình duyệt với bước 10 phút. `App.tsx` dùng series này cho metrics.

Nếu lần chạy hai năm trước thuộc UI này, đó là mô hình minh họa, không phải phép quét DEM/JPL có kiểm định hiện tại. Không có log của chính lần chạy người dùng nhắc tới để xác định chắc chắn nó thuộc UI này hay một bản API/cache khác. Việc kéo timeline/đổi range nhanh cũng không chứng minh mọi dữ liệu backend đã được tính xong.

## Hàng đợi và khóa dữ liệu

Phát hiện job 191856 giờ đến năm 2048 đang chiếm worker duy nhất; phía sau có job 408 giờ và request UI 72 giờ. Cache-hit vốn đã đi thẳng, nhưng cache-miss bị chặn bởi cả hàng đợi và global compute lock.

Bản mới có một worker cho request ≤168 giờ và một worker riêng cho request dài hơn. Đây chỉ là cách xếp hàng, **không phải giới hạn thời lượng**. Các request trùng nhau vẫn gộp job; khóa theo request, theo geometry identity và theo raw JPL query bảo vệ việc ghi đồng thời. Không bỏ kiểm hash. Các job cũ được giữ ID/input, tiếp tục từ cache; job 408 giờ và Connecting ridge 72 giờ đã hoàn tất trong khi job dài vẫn tiếp tục.

## Kiểm thử và chạy lại

- **314 test backend passed**; có test request ngắn hoàn tất trong khi job hai năm còn chạy, hai request dùng chung geometry chỉ build một lần, hai query JPL trùng nhau chỉ tải một lần và giữ hash/receipt hợp lệ, và dữ liệu thiếu/seam lỗi/near-horizon vẫn không bị ép PASS.
- **32 test frontend passed**; typecheck/build qua; `git diff --check` sạch.
- Audit khoa học 240 giờ sáng từ lần trước cũng chạy lại qua với artifact policy 2.0 đã version hóa; không đổi thuật toán hình học.
- Trước push đã chạy lại API thật cho hai ca PASS/FAIL, đối chiếu point/compare/search/CSV bằng `verify_indeterminate_resolution.py --offline`; tất cả khớp.

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_compute_and_resolution.py \
  --output /tmp/compute-and-resolution-repeat.json
```

Lệnh trên dùng input NASA/JPL đã cài, chạy offline và dựng cache kết quả độc lập; không làm nóng cache production. Báo cáo đối chứng trước/sau đã lưu `before_pipeline_sha256` và từng stage/timing. Muốn chạy lại đối chứng cũ, truyền `--before-pipeline` đến bản pipeline đã lưu trước khi sửa. Không cần bản cũ để chạy lại bốn ca hiện tại.

Bằng chứng máy đọc được: `compute-and-resolution-audit.json`, `compute-ui72-audit.json`, `compute-and-resolution-api.json`. Các file cache và benchmark tạm không được đưa vào Git.
