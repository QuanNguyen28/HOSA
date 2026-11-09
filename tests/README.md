# Tests

Thư mục dành cho unit, integration và acceptance tests theo các giai đoạn R&D. Chỉ thêm test gắn với yêu cầu hoặc lỗi cụ thể; không tạo test hình thức.

Sau khi cài môi trường backend, chạy từ gốc repo:

```bash
PYTHONPATH=. backend/.venv/bin/pytest -q
```

`test_science.py` kiểm tra hệ tọa độ, ENU, độ cong, parser, cửa sổ thời gian, cận thời lượng và trạng thái thiếu dữ liệu. `test_catalog_api.py` kiểm tra catalog, DEM tùy ý, scenario, profile chân trời, phân tích hai site, sự kiện quyết định, export và từ chối cấu hình ngoài miền.
