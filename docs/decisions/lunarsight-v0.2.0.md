# Phương pháp tính và phân phối dữ liệu HOSA v0.2.0

Các lượt quét dùng tọa độ ENU trên mặt cầu Mặt Trăng, phương vị Bắc địa lý, DEM 5/80/240 m và bán kính 400 km. Với Site04, đường ghép bán kính cố định giữa DEM 5 m và 80 m cho sai biệt góc p95 khoảng 0,189°. Chuyển sang ghép theo biên DEM 5 m giảm sai biệt còn 0,106–0,107° trên hai lưới phương vị. Báo cáo giữ cả số liệu trước và sau khi đổi. [Bảng kiểm tra Site04](../validation/lunarsight/v0.2.0/reports/Site04_seam_summary.csv)

Các artifact Kaggle được lưu theo phiên bản trong `data/processed/`, `data/cache/`, `manifests/` và `docs/validation/`. Các tệp NASA gốc được phân phối ở GitHub Releases để có thể giải nén đúng vào `data/raw/nasa/`. Runner kiểm tra SHA-256 của cache theo receipt trước khi dùng và ghi kết quả mới vào một thư mục chạy riêng.

Kịch bản, ngưỡng G0 và các kết luận tầm nhìn vẫn mang nhãn `PROVISIONAL`. [Cấu hình kịch bản](../../manifests/lunarsight/config/scenario.json) · [Cấu hình hình học](../../manifests/lunarsight/config/geometry_config.json)
