# Kiểm tra chuỗi sáng 10 ngày tại Site01_P1

Kết quả: **không phát hiện hồi quy khiến backend tự tính thành 240 giờ sáng**. Với mô hình tâm Mặt Trời, dữ liệu NASA LOLA và JPL thực đang dùng, chuỗi này đã xuất hiện trong dữ liệu cũ và được tính lại nhất quán. Đây là kiểm tra hồi quy và kiểm tra số học độc lập; chưa phải xác nhận thực địa hoặc chứng nhận an toàn nhiệm vụ.

## Trường hợp đã kiểm tra

- Tọa độ: latitude −89.43892646479243°, longitude east 222.90402192622227°.
- Bắt đầu: 2026-11-17 00:00 UTC; kết thúc: 2026-11-27 00:00 UTC, không tính thêm khoảng ở mốc cuối.
- Panel 1 m; antenna 2 m; cao độ pixel DEM là 1958.3211669921875 m so với bán kính tham chiếu 1737.4 km.
- Result ID: `a02704aa3656287226b793dbbd46c8bd11bf356b5d30e53b6d6503844bcb0d50`.

## Bằng chứng

| Phép kiểm tra | Kết quả thực |
|---|---|
| CSV Site01 trong revision `94b33c68032f3561b6cd636bcf39384501bf6e34` và file hiện tại | Giống từng byte; 2880/2880 khoảng 5 phút đã là V từ trước |
| Góc azimuth/elevation Sun của CSV cũ và API mới | Giống nhau hoàn toàn |
| Chạy code visibility nguyên bản và code hiện tại trên cùng dữ liệu | Toàn bộ output giống nhau ở cả lưới 5 phút và 1 phút, sau khi bỏ khác biệt kiểu lưu category |
| Đọc lại bảng raw JPL bằng bộ đọc CSV/calendar riêng | Trùng parser production; đủ mốc đầu/cuối và không thiếu góc ở cả hai lưới |
| Lưới 5 phút | 2880 khoảng + mốc biên cuối; tổng Sun 240 giờ |
| Lưới 1 phút từ truy vấn JPL riêng | 14400 khoảng + mốc biên cuối; tổng Sun 240 giờ |
| Góc cao Sun trên lưới 1 phút | 0.979928633° đến 1.348150445° |
| Độ hở Sun − horizon nhỏ nhất trên lưới 1 phút | 1.237770753°, tại 2026-11-20 08:46 UTC |
| Tính lại toàn bộ 17280 blocker của bốn profile bằng XYZ → ENU độc lập | Sai khác góc cao lớn nhất khoảng 1.05×10⁻⁹ độ |
| Quét lại DEM tại 12 hướng thực, gồm thời điểm có độ hở nhỏ nhất | Mỗi hướng 16133 mẫu bán kính đến 400 km; tất cả vẫn thấy Sun; độ hở nhỏ nhất khoảng 1.237770753° |
| Đối chứng tối tại (−86.61104682173548°, 336.25717784632303°E), 24–27/11/2026 | Cache có receipt/hash hợp lệ; 0/72 giờ Sun, FAIL; classifier nguyên bản cũng xác nhận toàn bộ 864 khoảng B |

Hash CSV cũ: `ae0416a458449f71f091f8a6ab7d292eeef6d76bb46ef448ba0e9e102373ffef`.

Các file raw JPL được kiểm SHA-256, kiểm observer Moon/MEAN_ME, east-positive longitude, altitude, airless, UTC, bán kính và target. Hai lưới là dữ liệu truy vấn thực khác nhau, không phải nội suy 5 phút thành 1 phút. Các DEM được kiểm receipt, nguồn NASA và SHA-256. Danh sách digest, raw query và số liệu chi tiết nằm trong `long-sunlight-audit.json`.

Quét lại dùng công thức tọa độ cầu theo bearing và phép chiếu vector XYZ khác với `ray_positions`/`ray_elevation` production. Khoảng cách mẫu là 2.5 m gần điểm, 20 m ở vùng trung gian và 60 m ở vùng xa. Nó dùng các DEM đã xác minh giống production; không phải nguồn đo địa hình độc lập. 12 tia này bổ sung kiểm tra, không thay thế kiểm tra toàn bộ đường đi bằng các profile.

## Vì sao có thể sáng 10 ngày?

Gần cực nam, có những điểm cao nhìn được Mặt Trời ở sát đường chân trời qua nhiều ngày. NASA mô tả một số ít vị trí vùng cực nhận nắng gần liên tục, đồng thời nhấn mạnh cần phân tích riêng thời gian, độ phân giải địa hình và chiều cao thiết bị: [NASA LOLA Polar Illumination](https://pgda.gsfc.nasa.gov/products/69).

Trong trường hợp cụ thể này, Sun di chuyển về azimuth từ khoảng 227.16° đến 105.76°, nhưng góc cao vẫn dương xấp xỉ 1°. Horizon địa hình ở các hướng này thấp hơn mặt phẳng ngang địa phương. Các con số này đến từ DEM/JPL của yêu cầu, không suy ra từ phát biểu tổng quát của NASA.

`240 giờ sáng` có nghĩa **tâm Mặt Trời không bị địa hình che tại tất cả các mẫu đang xét**. Nó không có nghĩa chiếu thẳng góc vào panel, công suất không đổi hoặc có đủ điện cho nhiệm vụ.

## Thuật toán nào thay đổi?

`point_analysis/geometry.py` và `services/lunarsight/horizon.py` giống nguyên bản. `visibility.py` chỉ đổi cột trạng thái/coverage sang kiểu lưu category để giảm RAM; công thức phân loại và nội suy horizon giữ nguyên. Parser JPL thêm hỗ trợ timestamp HH:MM khi phản hồi không in giây; góc và tọa độ observer giữ nguyên.

Refinement chọn profile góc mịn hơn cho result mới; vì vậy horizon dọc đường Sun có thể khác CSV cũ tối đa khoảng 0.08121°, dù **trạng thái Sun vẫn giống nhau và độ hở nhỏ nhất không đổi đáng kể**. Đợt sửa validation thay đổi điều kiện cho phép đưa ra PASS, không đổi các mẫu Sun bị che thành mẫu sáng.

## Giới hạn còn lại

`validation.passed` toàn cục vẫn là **false** do độ nhạy giữa các lưới phương vị ở những hướng khác. Không xóa diagnostic này. `validation.mission_path.passed` là **true** vì các hard requirements của yêu cầu vẫn đạt khi dùng envelope số học bảo thủ trên các đường Sun/Earth thực tế. Với Sun, padding là 0.659793502°; biên an toàn nhỏ nhất còn 0.577896271° khi xét các cấu hình của phép kiểm chứng.

Envelope này có tính thực nghiệm và trạng thái PROVISIONAL. Nó không bao trùm mọi sai số vật lý DEM, không chứng minh mọi thời điểm giữa các mẫu 1 phút, không mô hình hóa đĩa Mặt Trời, công suất, nhiệt hoặc link budget. Tài liệu NASA ở trên hỗ trợ tính hợp lý của hiện tượng, không xác nhận độc lập dự báo tại tọa độ/ngày này.

## Chạy lại

Từ repository root, với DEM/raw JPL/result đã lưu:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_long_sunlight.py \
  data/cache/point-analysis/results/a02704aa3656287226b793dbbd46c8bd11bf356b5d30e53b6d6503844bcb0d50/result.json \
  --output docs/validation/lunarsight/long-sunlight-audit.json
```

Script chạy offline, dừng nếu hash, dữ liệu, kết quả hồi quy hoặc kiểm tra độc lập không khớp. Không sửa threshold khoa học để làm bài kiểm tra qua.

Kiểm thử liên quan đã chạy: **60 passed** (`test_science`, `test_long_missions`, `test_compute_performance`, `test_indeterminate_resolution`). Một deprecation warning của Starlette/httpx không liên quan đến số liệu.
