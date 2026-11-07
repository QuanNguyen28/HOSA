# Tests

Thư mục dành cho unit, integration và acceptance tests theo các giai đoạn R&D. Chỉ thêm test gắn với yêu cầu hoặc lỗi cụ thể; không tạo test hình thức.

Sau khi cài `scripts/requirements-lunarsight.txt`, chạy `python -m pytest -q tests/test_science.py` từ gốc repo. Các fixture tổng hợp kiểm tra hệ tọa độ, ENU, độ cong, cửa sổ thời gian, cận thời lượng và trạng thái thiếu dữ liệu. Runner cũng thực thi bộ kiểm thử này trước khi tính kết quả.
