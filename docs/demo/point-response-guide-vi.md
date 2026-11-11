# Đọc kết quả API tọa độ

HTTP 200 nghĩa là tính toán thành công; một phương án không đáp ứng nhiệm vụ vẫn có thể trả HTTP 200 với `decision=FAIL`. Không dùng HTTP status để thay cho quyết định nhiệm vụ.

## Thứ tự đọc

1. `decision`: kết luận chung sau kiểm định. PASS = đạt yêu cầu đã nhập trong mô hình; FAIL = không đạt; INDETERMINATE = thiếu bằng chứng hoặc kiểm định chưa đạt. `null` = chưa nhập yêu cầu cứng để kết luận.
2. `constraint_checks`: từng yêu cầu cứng. Đây là kiểm tra nominal trên mô hình lấy mẫu; nếu gate khoa học không đạt, tất cả các check có thể PASS mà `decision` vẫn INDETERMINATE.
3. `validation.passed`: các kiểm tra hiện được thực thi có đạt không. Không phải chứng nhận tuyệt đối hoặc chứng nhận hạ cánh. Các tolerance vẫn PROVISIONAL.
4. `soft_constraint_checks`: tiêu chí phụ. FAIL ở đây không tự loại phương án đạt yêu cầu cứng.
5. `metrics_hours`, `availability_fraction`, `contact_analysis`: số liệu để hiểu nguyên nhân.

`nominal_sampled_decision` là kết luận trước gate kiểm định; không thay cho `decision` cuối cùng.

`INDETERMINATE` không phải thuộc tính cố định của tọa độ, cũng không có nghĩa API bị lỗi hoặc số liệu bằng 0. Kết luận phụ thuộc tọa độ, thời gian, chiều cao thiết bị, yêu cầu và bằng chứng kiểm định. Có thể thiếu dữ liệu địa hình/ephemeris, có interval `?`, hoặc có đủ dữ liệu nhưng kết quả chưa ổn định theo các phép thử sensitivity.

Ví dụ đã thử điểm (-88.66481191717628, 291.6227220723251), bắt đầu 2026-11-24 UTC, nhiệm vụ 6 giờ, panel/antenna cao 20 m: mô hình danh định cho 6 giờ Sun và Earth LOS, nhưng sai lệch góc khi đổi bước quét là 0,12834°, vượt ngưỡng 0,1°. Vì vậy kết luận cuối là INDETERMINATE dù nominal PASS. Một nominal FAIL cũng bị giữ INDETERMINATE nếu kiểm định chưa đạt; không thể dùng nó làm bằng chứng FAIL đã xác nhận.

## Window khác session như thế nào?

Một **visibility window** là chuỗi interval `V` liên tục: tâm Trái Đất được xác định là nhìn thấy về hình học trong mô hình. Đây là cơ hội thực hiện liên lạc, không phải phiên truyền dữ liệu đã đặt lịch hay đã thực hiện. Chặn `B` làm kết thúc window. Khoảng `?` không được tự nối thành một window chắc chắn.

`min_contact_minutes=30`, `setup_minutes=5` yêu cầu ít nhất một window có độ dài >=35 phút: dành 5 phút setup và còn >=30 phút sử dụng.

`required_windows=N` yêu cầu **N cửa sổ riêng biệt**, mỗi cửa sổ đủ `setup + min_contact`. Nó không đếm N phiên có thể xếp trong một cửa sổ. Ví dụ một window liên tục 4 giờ vẫn chỉ được đếm là 1, dù có thể đủ thời gian để bố trí nhiều phiên 30 phút.

Số window không phải điểm chất lượng:

- Một window liên tục phủ toàn nhiệm vụ cho phép liên lạc lúc nào cũng được; ít window ở đây là tốt.
- Một window dài xuất hiện quá muộn vẫn không đáp ứng deadline liên lạc sau hạ cánh.
- Nhiều window rải đều có thể hữu ích hơn một window sớm duy nhất nếu phần còn lại của nhiệm vụ mất LOS quá lâu.
- Nếu mục tiêu là liên tục/khả dụng, bỏ `required_windows` hoặc để 1. Không đặt 2 chỉ vì muốn "nhiều cơ hội": điều đó có thể loại một điểm luôn nhìn thấy Trái Đất.
- Yêu cầu "mỗi 6 giờ có một phiên 30 phút" không được biểu diễn chỉ bằng `required_windows`; API hiện chưa lập lịch các phiên trong từng khoảng lặp/rolling window.

`first_contact_deadline_minutes=120` yêu cầu setup và một phiên đủ dài **hoàn thành** trước hoặc đúng phút 120. Không chỉ yêu cầu bắt đầu window trước phút 120. Tất cả thời gian chờ/deadline tính từ đầu nhiệm vụ.

## Các metric contact

| Trường trong `contact_analysis.metrics` | Ý nghĩa | Đơn vị |
|---|---|---|
| `total_los_minutes_bounds` | Tổng thời gian Earth LOS trong nhiệm vụ | phút [L,U] |
| `longest_contact_minutes_bounds` | Window liên tục dài nhất trong miền phân tích | phút [L,U] |
| `max_gap_minutes_bounds` | Khoảng không có LOS dài nhất, gồm cả đầu/cuối nhiệm vụ | phút [L,U] |
| `visible_windows_count` | Số chuỗi V, kể cả ngắn chưa đủ phiên | số lượng |
| `qualified_windows_count` | Số chuỗi V đủ setup + thời lượng yêu cầu | số lượng |
| `qualified_windows_count_complete` | Có đủ bằng chứng để biết số cửa sổ thật trong mô hình không | boolean |
| `qualified_visible_minutes` | Tổng thời gian còn dùng được sau một lần setup/window đủ dài | phút; không phải thời gian đã truyền |
| `first_contact_wait_minutes.first_confirmed` | Chờ đến window V đầu tiên, chưa bảo đảm đủ dài cho phiên | phút hoặc null |
| `first_contact_wait_minutes.earliest_possible` | Thời điểm sớm nhất có thể thấy Earth nếu unknown thuận lợi | phút hoặc null |

Nếu có `?`, số chuỗi V quan sát được không phải cận dưới an toàn cho số window thật: `V / ? / V` có thể là một window nếu phần giữa thực ra V. Khi đó yêu cầu về số window trả INDETERMINATE. `null` ở thời gian chờ nghĩa là không có window tương ứng trong miền đã phân tích, không phải chờ 0 phút.

Trong `visible_windows`, `duration_minutes` là độ dài window; `usable_duration_minutes` đã trừ setup; `qualifies` chỉ nói window này đủ dài không. `touches_window_start/end` cho biết window chạm biên nhiệm vụ; độ dài ở ngoài miền chưa được biết (`outside_window_duration_known=false`).

## Cặp [L,U] và đơn vị

- `metrics_hours`: giờ. `contact_analysis.metrics`: phút. `availability_fraction`: tỷ lệ 0–1, nhân 100 để ra phần trăm.
- [L,U] là cận dưới/trên khi thay đổi các đoạn chưa xác định trong mô hình lấy mẫu. [6,6] không có độ rộng do unknown; không có nghĩa đúng tuyệt đối trong thực tế.
- Chưa bao gồm đầy đủ sai số DEM, thời điểm chuyển giữa hai mốc, vật cản giữa các ray, hoặc sự kiện ngắn hơn bước thời gian.
- `V` = nhìn thấy, `B` = bị chặn, `?` = chưa xác định; không đổi `?` thành nhìn thấy hoặc bị chặn để làm đẹp kết quả.

## warnings, scope, limitations

Các trường này là mô tả phạm vi và giới hạn; có thể xuất hiện cả khi PASS. Không phải mọi dòng trong `warnings` đều là lỗi chạy chương trình.

| Trường/nội dung | Cách hiểu |
|---|---|
| `warnings` | Ghi chú của toàn pipeline: trạng thái PROVISIONAL, phạm vi mô hình, giới hạn của cận số liệu; có thêm thông báo nếu validation không đạt |
| `PROVISIONAL` | Các ngưỡng kiểm định do dự án đặt tạm thời, chưa được chủ nhiệm nhiệm vụ phê duyệt làm chuẩn vận hành |
| Sun/Earth centre only | Chỉ hình học tâm Sun/Earth. Chưa tính phần đĩa Mặt Trời đang ló, công suất điện/nhiệt hay đường truyền RF |
| Missing-sample duration bounds | [L,U] chỉ bao unknown trong mô hình, không phải toàn bộ sai số thực tế |
| Sampled rays to 400 km | Địa hình được quét theo các tia và bán kính hữu hạn; coverage đầy đủ là đầy đủ các mẫu đã yêu cầu, không phải mọi vật cản thật |
| Validation gate did not pass | Kiểm định cụ thể chưa đạt, cần xem `validation` để biết phần nào; kết luận yêu cầu cứng giữ INDETERMINATE |
| `scope=sampled_earth_centre_visibility_within_analysis_window` | "Khả năng nhìn thấy tâm Trái Đất theo lưới mẫu, chỉ trong khoảng thời gian phân tích". Đây không phải mã lỗi |
| `limitations` | Các quy tắc/giới hạn của phần contact: chưa có trạm mặt đất/RF; khoảng nửa mở; blackout đầu/cuối được tính; deadline đòi hoàn thành phiên; phải giữ gate của nguồn |

`[start,end)` là khoảng gồm thời điểm bắt đầu, loại thời điểm kết thúc, tránh đếm đôi hai interval liền nhau. Timestamp cuối của ephemeris chỉ là biên; không cộng thêm một interval.

`contact_analysis.source` giữ lại metadata nguồn để phần contact có thể được kiểm tra độc lập. Vì vậy một số warnings/validation/request được lặp lại từ cấp ngoài; đó không phải nhiều lỗi độc lập.

## Các metadata khác

- `result_id`: định danh để đối chiếu/cache; không phải điểm chất lượng.
- `method_version`, `schema_version`: phiên bản thuật toán/định dạng.
- `execution.result_cache_hit`: dùng lại kết quả cùng đầu vào/nguồn/version đã kiểm tra; không có nghĩa là số liệu giả lập.
- `coordinate.observer_dataset_id`, `observer_resolution_m`: DEM thực sự dùng và khoảng cách lưới của nó; độ phân giải 80 m không phải tuyên bố sai số vị trí/cao độ đúng bằng 80 m.
- `timeline`: interval và trạng thái gốc, dùng để kiểm tra khi nào nhìn thấy/bị chặn.
- `horizons`: góc đường chân trời theo phương vị và chiều cao thiết bị.
- `provenance`: nguồn, tham số, checksum, phiên bản để tái lập phép tính.

Một request nhiều metric vẫn chỉ cho một tọa độ. Các tiêu chí phụ giúp đánh giá/so sánh; endpoint này chưa tự lập một lịch liên lạc tối ưu hoặc xếp hạng một tập tọa độ.


## Đọc phần sensitivity sau khi sửa ghép biên

- `events_first/second`: số lần chuyển trạng thái, không phải số window. Một timeline V từ đầu đến cuối có 1 window nhưng 0 lần chuyển trạng thái.
- `matched_first_within_15min`, `matched_second_within_15min`: số biên ghép được trong dải tìm kiếm 15 phút; nay mỗi biên chỉ dùng một lần và giữ thứ tự thời gian.
- `unmatched_first/second`: số biên chưa ghép được; thiếu biên phải được báo rõ.
- `max_matched_event_shift_minutes`: độ dịch lớn nhất của các cặp đã ghép. Ngưỡng chấp nhận hiện tại là 5 phút; 15 phút chỉ là dải tìm cặp, không phải ngưỡng PASS.
- `minutes_state_diff`: tổng số phút hai mô hình cho trạng thái khác nhau; tổng số giờ visible giống nhau không có nghĩa là timeline giống nhau.

`provenance.identity.sensitivity_version=ordered-events-1.0` đánh dấu kết quả đã dùng sửa lỗi ghép biên. Khóa cache mới không tự tái sử dụng quyết định đã tính theo logic cũ; cache horizon/DEM/JPL vẫn được giữ vì không thay phép tính hình học/ephemeris.
