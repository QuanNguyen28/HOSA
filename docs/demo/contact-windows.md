# Earth visibility windows từ output backend

`scripts/contact_windows.py` là bước xử lý sau độc lập, chỉ dùng thư viện chuẩn
Python. Công cụ dùng module standard-library chung `app.services.lunarsight.contact_windows`,
không đọc DEM, không gọi JPL, không chạy lại horizon và không thay đổi cache
của pipeline. CLI chạy từ repo, không cần cài thư viện khoa học.
Chi phí tính toán tuyến tính theo số interval đầu vào.

## Dùng kết quả API tọa độ

Sau khi job đã hoàn tất, đọc trực tiếp URL kết quả hiện có:

```bash
python3 scripts/contact_windows.py \
  --url http://localhost:8000/api/lunar/point/analyses/JOB_ID/result \
  --min-contact-minutes 30 \
  --setup-minutes 5 \
  --required-windows 1 \
  --first-contact-deadline-minutes 120 \
  --max-gap-minutes 360 \
  --output /tmp/contact-windows.json
```

Dùng `result_url` thực tế của job nếu route khác ví dụ trên. Công cụ chỉ GET
kết quả, không tạo job và không chờ một job đang chạy. File JSON lưu bằng
`scripts/analyze_point.py --output /tmp/point-result.json` cũng dùng được:

```bash
python3 scripts/contact_windows.py \
  --input /tmp/point-result.json --min-contact-minutes 30
```

`--input -` nhận JSON qua stdin. JSON phải chứa `timeline` đầy đủ với
`start_utc`, `end_utc`, `earth_state` cho từng interval. Không dùng phần tóm tắt
mà `analyze_point.py` in ra stdout; cần file kết quả đầy đủ qua `--output`.
Các response compare/search chỉ có metric tổng hợp hoặc blocking events cũng
không đủ cho adapter này và sẽ bị từ chối. Không suy diễn phần không được liệt
kê trong một response bất kỳ thành nhìn thấy.

## Dùng interval CSV gốc đã xuất

```bash
python3 scripts/contact_windows.py \
  --input data/processed/lunarsight/v0.3.0/visibility/Site01_intervals.csv \
  --start-utc 2026-11-14T00:00:00Z \
  --end-utc 2026-11-17T00:00:00Z \
  --min-contact-minutes 30 \
  --output /tmp/site01-contact-windows.json
```

Nếu bỏ `--start-utc`/`--end-utc`, dùng toàn bộ miền thời gian của nguồn. Với
JSON tọa độ, miền được lấy từ request và `end_utc`; với CSV là biên đầu/cuối
file. Subwindow phải nằm trong miền đó. Timestamp phải có múi giờ, output
được chuẩn hóa UTC. Timeline rút gọn phục vụ vẽ đồ thị (`points`,
`sample_stride`) bị từ chối, kể cả khi có vẻ liên tục.

## Metric và yêu cầu

- `visible_windows`: từng chuỗi interval `V` liên tục, thời điểm bắt đầu/kết
  thúc, thời lượng, thời lượng sau khi trừ setup, đạt yêu cầu phiên hay không.
- `longest_contact_minutes_bounds`: cửa sổ dài nhất; cận dưới chỉ nối `V`, cận
  trên nối `V/?`.
- `max_gap_minutes_bounds`: thời gian không có LOS dài nhất; cận dưới nối `B`,
  cận trên nối `B/?`. Bao gồm khoảng chờ ở đầu và cuối nhiệm vụ.
- `total_los_minutes_bounds`: tổng LOS, giữ lại để tham khảo.
- `first_contact_wait_minutes`: chờ tới cửa sổ đầu tiên có thể xảy ra và tới
  cửa sổ đầu tiên xác nhận được. `null` nghĩa là không tìm được cửa sổ tương
  ứng trong miền phân tích; không có nghĩa là chờ 0 phút. Đây là thời điểm
  bắt đầu LOS, chưa đòi hỏi cửa sổ đủ dài cho phiên đã yêu cầu.
- `qualified_windows_count`: số chuỗi `V` đạt `setup + min_contact_minutes`.
  Nếu có `?`, số này chỉ mô tả các chuỗi đã quan sát, không phải cận dưới cho
  số cửa sổ thực tế: `V/?/V` có thể gộp thành một cửa sổ. Khi đó
  `qualified_windows_count_complete=false` và yêu cầu số cửa sổ trả
  `INDETERMINATE`.
- `qualified_visible_minutes`: tổng thời gian sau setup của các chuỗi `V`
  đạt yêu cầu; không chia một cửa sổ dài thành nhiều phiên độc lập.

`--min-contact-minutes` yêu cầu có ít nhất một phiên liên tục đủ dài.
`--required-windows` yêu cầu số cửa sổ riêng biệt. Mỗi cửa sổ trừ một lần setup.
`--first-contact-deadline-minutes` tính từ đầu miền phân tích và yêu cầu **toàn
bộ setup + phiên liên tục hoàn thành trước hoặc đúng deadline**, không chỉ
bắt đầu trước deadline. `--max-gap-minutes` giới hạn thời gian mất LOS dài
nhất. Các yêu cầu đều do người dùng chỉ định, không có ngưỡng nhiệm vụ mặc định.
Không truyền yêu cầu thì chỉ xuất metric, quyết định là `null`.

Khoảng nửa mở `[start,end)` được tính đúng trọng số thời gian; mốc terminal
không cộng thêm một interval. Khoảng thiếu giữa các dòng hoặc ở biên request
được ghi `?`, không tự gán `V` hay `B`. Dòng chồng lấn, đảo thứ tự, thời lượng
không dương hoặc trạng thái lạ bị từ chối. Cửa sổ chạm biên có cờ riêng; thời
lượng ngoài miền phân tích chưa được biết.

## Giữ nguyên kiểm định từ backend

`source` giữ result ID, method/dataset version, request, tọa độ, quyết định,
coverage, validation, warnings của nguồn; CLI bổ sung SHA-256 của dữ liệu đã
đọc. Công cụ không sửa quyết định gốc.

`requirements.sampled_checks` và `nominal_sampled_decision` là kiểm tra trên
mô hình interval đã lấy mẫu. `requirements.decision` chỉ sử dụng kết luận này
khi `validation.passed=true` từ nguồn. Nếu backend chưa đạt kiểm định hoặc
nguồn CSV không kèm kiểm định, quyết định cuối là `INDETERMINATE`.

Cận thời lượng chỉ mô tả thiếu bằng chứng trong mô hình lấy mẫu, không bao
hàm sai số DEM, dịch biên liên tục hay sự kiện ngắn hơn bước thời gian. Đây là
Earth-centre visibility, chưa phải xác nhận đường truyền tới một trạm mặt đất.
Không giả định đồng thời có ánh sáng Mặt Trời; nguồn điện và liên lạc là hai
yêu cầu riêng.

Import trực tiếp để dùng trong một client khác:

```python
from scripts.contact_windows import analyze_contacts

contacts = analyze_contacts(backend_result, min_contact_minutes=30,
                            first_contact_deadline_minutes=120)
```

CLI trả exit code 0 khi tính xong (kể cả FAIL/INDETERMINATE), 2 nếu đầu vào,
HTTP hoặc ghi output bị lỗi. Các nhãn này chỉ thuộc yêu cầu cửa sổ của bước
xử lý sau, không thay nhãn hoặc thứ tự xếp hạng hiện tại của backend.

Kiểm thử:

```bash
PYTHONPATH=. backend/.venv/bin/python -m pytest tests/test_contact_windows.py -q
```


## Tích hợp một request API

API tọa độ đã nhận `contact_requirements` trong cùng `POST /api/lunar/point/analyze`.
Khi được cung cấp, các yêu cầu contact cùng yêu cầu nắng được gộp vào quyết định
chung, sau gate khoa học. Độ nhạy cũng kiểm tra lại deadline/số cửa sổ trên từng
lưới. CLI độc lập vẫn giữ cách tính và interface cũ; chỉ phần thuật toán được
đặt trong module dùng chung để tránh hai phiên bản lệch nhau.

Xem [request mẫu và hướng dẫn API](../decisions/coordinate-analysis-pipeline.md).
Trên API, giới hạn mất LOS phụ nằm ở `constraints.max_earth_blackout_hours`;
`contact_requirements` chỉ gồm thời lượng, setup, số cửa sổ và deadline.
Tùy chọn `--max-gap-minutes` của CLI độc lập vẫn là kiểm tra riêng do người dùng
chủ động yêu cầu; không tự biến giới hạn phụ của API thành yêu cầu cứng.
