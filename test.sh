# Trường hợp PASS
curl --fail-with-body -sS http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-outside-pass-request.json \
  -o /home/levantuananh/H1/HOSA/point-pass-response.json

# Trường hợp FAIL
curl --fail-with-body -sS http://127.0.0.1:8000/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-analysis-outside-fail-request.json \
  -o /home/levantuananh/H1/HOSA/point-fail-response.json

# So sánh 2 điểm tọa độ (Compare)
curl --fail-with-body -sS http://127.0.0.1:8000/api/planning/compare \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/planning-compare-coordinate-request.json \
  -o /home/levantuananh/H1/HOSA/planning-compare-response.json

# Tìm kiếm cửa sổ nhiệm vụ trên 2 điểm tọa độ (Search)
curl --fail-with-body -sS http://127.0.0.1:8000/api/planning/windows/search \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/planning-search-coordinate-request.json \
  -o /home/levantuananh/H1/HOSA/planning-search-response.json

