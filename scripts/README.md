# Data scripts

Đặt các script tải và kiểm tra dữ liệu ở đây. Script phải hỗ trợ `--help`, ghi thời gian UTC, nguồn, checksum và không ghi đè `data/raw/` một cách im lặng.

Chạy từ thư mục gốc bằng `python scripts/run_lunarsight.py --help`. Xem [hướng dẫn tải nguồn và chạy lại](../docs/validation/lunarsight/README.md) để chuẩn bị môi trường.

`notebooks/lunarsight-data-pipeline.ipynb` là notebook Kaggle độc lập đã xuất từ bộ bàn giao. Bốn notebook đánh số dùng cây thư mục của ZIP độc lập. Giải nén ZIP rồi đặt `LUNARSIGHT_ROOT` trỏ vào thư mục `lunarsight-data` trước khi chạy chúng.
# Web terrain derivatives

Generate reproducible browser assets from a validated raw DEM:

```bash
backend/.venv/bin/python scripts/build_web_terrain.py \
  data/raw/Site01/Site01_final_adj_5mpp_surf.tif \
  frontend/public/assets/terrain site01
```

The script writes an explicit receipt containing the source checksum, CRS metadata,
rendering parameters and output checksums. Generated height/hillshade files are for
display only; never use them in scientific calculations.
