# Data scripts

Đặt các script tải và kiểm tra dữ liệu ở đây. Script phải hỗ trợ `--help`, ghi thời gian UTC, nguồn, checksum và không ghi đè `data/raw/` một cách im lặng.

Chạy từ thư mục gốc bằng `python scripts/run_lunarsight.py --help`. Xem [hướng dẫn tải nguồn và chạy lại](../docs/validation/lunarsight/README.md) để chuẩn bị môi trường.

`planning_cli.py` nhận tham số hoặc JSON trực tiếp để compare/search/export,
không qua LLM. Có chế độ gọi service cục bộ và gọi HTTP bằng `--base-url`.
Xem [ví dụ CLI](../docs/demo/planning-cli.md).

`assistant_chat.py` dùng API session/run cho hội thoại thật; `/result` hiển thị số liệu theo yêu cầu và `/unicode` kiểm tra dấu tiếng Việt tại máy. `open_assistant_terminal.ps1` cấu hình UTF-8 và có thể khởi động API local chạy nền. `provider_preflight.py`, `assistant_eval.py --live` và `assistant_failover_eval.py` là các công cụ gọi API thật; xem [hướng dẫn BE/LLM](../docs/assistant/BE_LLM_RELEASE.md). Credential chỉ lấy từ môi trường hoặc `.env` bị ignore.

`contact_windows.py` tính cửa sổ nhìn thấy Trái Đất, phiên đủ dài, thời gian chờ
và khoảng mất LOS từ JSON kết quả backend hoặc CSV interval gốc. Công cụ độc
lập với phần tính DEM/JPL. Xem [hướng dẫn và giới hạn](../docs/demo/contact-windows.md).

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
