# Data scripts

Đặt các script tải và kiểm tra dữ liệu ở đây. Script phải hỗ trợ `--help`, ghi thời gian UTC, nguồn, checksum và không ghi đè `data/raw/` một cách im lặng.

Chạy từ thư mục gốc bằng `python scripts/run_lunarsight.py --help`. Xem [hướng dẫn tải nguồn và chạy lại](../docs/validation/lunarsight/README.md) để chuẩn bị môi trường.

`planning_cli.py` nhận tham số hoặc JSON trực tiếp để compare/search/export,
không qua LLM. Có chế độ gọi service cục bộ và gọi HTTP bằng `--base-url`.
Xem [ví dụ CLI](../docs/demo/planning-cli.md).

`contact_windows.py` tính cửa sổ nhìn thấy Trái Đất, phiên đủ dài, thời gian chờ
và khoảng mất LOS từ JSON kết quả backend hoặc CSV interval gốc. Công cụ độc
lập với phần tính DEM/JPL. Xem [hướng dẫn và giới hạn](../docs/demo/contact-windows.md).

`notebooks/lunarsight-data-pipeline.ipynb` là notebook Kaggle độc lập đã xuất từ bộ bàn giao. Bốn notebook đánh số dùng cây thư mục của ZIP độc lập. Giải nén ZIP rồi đặt `LUNARSIGHT_ROOT` trỏ vào thư mục `lunarsight-data` trước khi chạy chúng.

## Full-product official data

The complete website data registry is
`manifests/lunarsight/full_product_sources.json`. It separates full downloads,
windowed cloud-optimized GeoTIFF access and on-demand validation data. Scientific
inputs are restricted to official NASA/JPL/PDS hosts and every downloaded file
gets an immutable SHA-256 receipt.

Preview the core transfer:

```bash
backend/.venv/bin/python scripts/acquire_full_product_data.py --dry-run
```

Download or verify it:

```bash
backend/.venv/bin/python scripts/acquire_full_product_data.py
backend/.venv/bin/python scripts/acquire_full_product_data.py --verify
```

The 10 m and 20 m DEMs are intentionally not downloaded whole. They are remote
COGs and must be extracted into local windows around approved or user-selected
sites. This avoids a multi-gigabyte full-raster transfer while preserving the
fine terrain needed for local analysis.

After acquiring the NASA Moon Trek region layer, build the navigation catalog:

```bash
backend/.venv/bin/python scripts/build_official_site_catalog.py
```

The generated centroids are explicitly `UNASSESSED_REGION_CENTROID`. They are
map/navigation anchors, not recommendations or certified landing coordinates.

Preview or materialize the high-resolution COG windows for that catalog:

```bash
make data-windows-plan
backend/.venv/bin/python scripts/materialize_dem_windows.py
```

For an arbitrary user-selected coordinate, fetch only its local windows:

```bash
backend/.venv/bin/python scripts/materialize_dem_windows.py \
  --point 'custom-point,-89.44,222.83'
```
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
