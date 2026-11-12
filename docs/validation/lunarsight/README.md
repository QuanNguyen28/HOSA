# Dữ liệu và kiểm định HOSA v0.2.0

Snapshot này ghi lại lần chạy từng cell trong Kaggle Draft với Site01 và Site04. Mốc bắt đầu kịch bản và ngưỡng khoa học vẫn mang nhãn `PROVISIONAL`. 17 bài kiểm thử đã đạt. Mỗi site có 4.896 khoảng 5 phút và 1.344 mốc bắt đầu cho cửa sổ 72 giờ. [Báo cáo thực thi](v0.2.0/reports/execution_status.json) · [Báo cáo EDA](v0.2.0/reports/eda_summary.md) · [Từ điển dữ liệu](data-dictionary.md)

| Thư mục | Nội dung |
| --- | --- |
| [backend/app/services/lunarsight](../../../backend/app/services/lunarsight) | Tải và kiểm tra nguồn, DEM adapter, Horizons adapter, đường chân trời, tầm nhìn và cửa sổ hoạt động. |
| [scripts](../../../scripts) | Runner Python và năm notebook đã bàn giao. |
| [data/processed/lunarsight/v0.2.0](../../../data/processed/lunarsight/v0.2.0) | Danh mục hai điểm, chuỗi JPL chuẩn hóa, đường chân trời và bảng kết quả. |
| [data/cache/lunarsight/v0.2.0](../../../data/cache/lunarsight/v0.2.0) | Sáu phản hồi JPL gốc, header và receipt của các truy vấn đã chạy. |
| [manifests](../../../manifests) | Danh mục nguồn và điểm, cấu hình, checksum và metadata. |
| [docs/validation/lunarsight/v0.2.0](v0.2.0) | Biểu đồ, báo cáo, log kiểm thử, độ nhạy và bằng chứng ghép DEM. |
| [tests](../../../tests) | Kiểm thử khoa học và fixture tổng hợp. |

## Chạy lại từ repo

Chạy từ gốc repo bằng Python 3.11 trở lên. Runner có thể tải dữ liệu còn thiếu từ NASA/JPL và dùng cache đúng tham số nếu đã có. Kết quả chạy mới nằm trong `data/cache/lunarsight/runs/`.

```sh
python -m pip install -r scripts/requirements-lunarsight.txt
python scripts/run_lunarsight.py
```

Để chạy offline, tải `lunarsight-raw-nasa-v0.2.0.zip` từ [GitHub Releases](https://github.com/QuanNguyen28/HOSA/releases/tag/lunarsight-data-v0.2.0) và giải nén từ gốc repo. ZIP tạo `data/raw/nasa/` với tám GeoTIFF, hai tệp ROI, tài liệu NASA, receipt và danh sách SHA-256. Cache JPL cho kịch bản này đi cùng repo.

```sh
python -m zipfile -e lunarsight-raw-nasa-v0.2.0.zip .
python scripts/run_lunarsight.py --offline
```

`lunarsight-data-deliverables.zip` trong cùng release là gói Kaggle đã kiểm tra CRC, chứa notebook độc lập và các kết quả đã xuất. SHA-256 của gói là `b6dc410e3c38d262ccddc3b7051244e835a7c4a42d5ec9cefbd4c5866503c212`. SHA-256 của gói NASA gốc là `2dc45da7dfcb92bf8e5a1cbb3c2465fab05354caba444c05060856d29631f577`.

## Nguồn và giới hạn

- Địa hình 5 m, count, sai số RMS và ROI đến từ [NASA PGDA 78](https://pgda.gsfc.nasa.gov/products/78). Khi sử dụng, trích dẫn [Barker et al. 2021](https://doi.org/10.1016/j.pss.2020.105119).
- Hai DEM vùng rộng 80 m và 240 m đến từ [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90). Khi sử dụng, trích dẫn [Barker et al. 2023](https://doi.org/10.3847/PSJ/acf3e1).
- Vị trí tâm Sun/Earth đến từ [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html). Tầm nhìn dùng hình học, giới hạn theo hai điểm, khoảng thời gian và lưới mẫu của kịch bản.
- Độ nhạy bước 1 phút đã kiểm tra ở Site01 trong 72 giờ đầu. [Báo cáo độ nhạy](v0.2.0/reports/sensitivity.json)
