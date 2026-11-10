# Backend thử nghiệm LLM — kế hoạch và cách chạy

Ngày: 10/11/2026. Nhánh: `feature/llm-backend-openrouter`, tách từ `feature/lunarsight-data` tại `63d16b0`. Repo làm việc: `G:\My Drive\H1\HOSA`. Các nhánh `main` và `feature/lunarsight-data` giữ nguyên commit; repo G đang mở nhánh LLM.

## Cấu trúc và ranh giới thay đổi

| Folder/file | Vai trò |
| --- | --- |
| `backend/app/assistant/models.py` | Schema đầu vào, thay đổi, yêu cầu chuẩn hóa, bằng chứng và kết quả |
| `backend/app/assistant/config.py` | Đọc `.env` tại gốc worktree; model và key không nằm trong code |
| `backend/app/assistant/provider.py` | Adapter OpenRouter, timeout, schema, lỗi đã lọc; mỗi lượt một HTTP request |
| `backend/app/assistant/prompts.py` | Hai prompt có phiên bản; tách khỏi điều phối và khoa học |
| `backend/app/assistant/engine.py` | Adapter gọi bộ tính cũ, kiểm tra dữ liệu, xếp hạng và tạo bằng chứng |
| `backend/app/assistant/service.py` | Điều phối một LLM/hai lượt; kiểm tra giải thích, dùng mẫu khi lỗi |
| `backend/app/assistant/store.py` | Lưu draft có TTL, giới hạn số lượng, chống chạy trùng |
| `backend/app/assistant/router.py` | API riêng dưới `/api/assistant`, không thay hợp đồng `/api/analyze` |
| `tests/assistant/` | Kiểm thử contract, HTTP route, provider giả lập, lỗi và dữ liệu thật |
| `tests/fixtures/assistant/` | Prompt, đáp án chuẩn và mẫu dữ liệu nhỏ có checksum |
| `scripts/assistant_eval.py` | Chấm LLM thật qua chính route FastAPI; chỉ gọi khi có `--live` |
| `scripts/build_assistant_sample.py` | Tạo lại 6 cửa sổ mẫu từ CSV được quản lý phiên bản |

Chỉ cần sửa ba file dùng chung: `.env.example`, `backend/pyproject.toml` và `backend/app/main.py` (đăng ký router). Giữ nguyên frontend, bộ tính, API cũ và snapshot khoa học. Khi tích hợp tiếp, giao diện chỉ cần dùng schema API; có thể thay provider, kho draft hoặc bộ dữ liệu qua các ranh giới trên. Không cam kết không có conflict nếu các nhánh tiếp tục cùng sửa file dùng chung.

## Tham khảo từ nhóm 24 repo

Đã đọc lại mã nguồn ngày 10/11/2026; học cấu trúc, không nhập mã hoặc thêm dependency của các repo này:

- [PolarWindow compare_service](https://github.com/MdAhbab/PolarWindow/blob/main/backend/app/services/compare_service.py), blob `6ebbe884987e49f10e27ec61a5d02cf3202a91d9`: so sánh và chi tiết phải dùng chung bộ tính; công bố thiếu dữ liệu và bất định.
- [PolarWindow tools](https://github.com/MdAhbab/PolarWindow/blob/main/backend/app/agents/tools.py), blob `aac391bab1c24cce3404719bba1a4fda6fb4b2c6`: schema chặt, giới hạn dữ liệu đưa cho LLM, chỉ cho truy cập qua adapter đã kiểm tra. Không kế thừa kiến trúc nhiều agent.
- [EmanuelAbasto analysis](https://github.com/EmanuelAbasto/CLPS-Lunar-Mission-Browser/blob/main/backend/lunar-core/src/lunar_core/analysis.py), blob `2acd54f80bbb70aabcd1fdab2134ac4b1cd42fd7`: tách scenario, phân tích và xếp hạng. Bản thử này giữ trạng thái chưa đủ dữ liệu thay vì thay địa hình thiếu bằng chân trời phẳng.
- [BroBYW finder](https://github.com/BroBYW/CLPS-Lunar-Mission-Website/blob/main/web/src/lib/finder.ts), blob `5b882b7e529dbebf068c08d041842806fd5e9b28`: tham khảo việc lọc theo ràng buộc trước khi chọn phương án. Đây là thư viện tính trong web, không phải backend để sao chép.

## Dữ liệu được chọn

Nguồn Drive: [DATASET](https://drive.google.com/drive/folders/1MXt-hPU-H7Wj5eIaokKC6y0L5nxE-I7U). Đã đọc README, inventory và checksum; tải và kiểm tra gói `D03_JPL_HORIZONS_DECLARED_P1_RAW.zip`, 1.770.203 byte, SHA-256 `0b7637f9ee715d68932642aa0243750325a73b3836da3f7c5d872fdebda9f6a0`.

Bốn JSON gốc bước 5 phút của Site01_P1/Site04_P1, Sun/Earth khớp byte với cache của repo. Chọn 9 dòng mỗi chuỗi quanh 00:00, 00:05, 00:10 UTC vào 14, 17 và 20/11/2026: tổng 36 dòng, nằm trong `jpl_samples.json`. Chọn tiếp 6 cửa sổ 72 giờ (2 điểm × 3 ngày bắt đầu trên) từ sản phẩm đã xử lý của repo trong `window_sample.json`; kèm hash CSV nguồn.

Phân biệt nguồn: 36 dòng là mẫu JPL lấy trực tiếp từ Drive; 6 bộ chỉ số là sản phẩm tính đã có của repo, không phải chỉ số NASA cung cấp sẵn. Không dùng 36 dòng để tái tính độ dài tối 72 giờ. Route chạy trên toàn snapshot versioned của hai site; không tải DEM hoặc gọi JPL trong request. LLM nhận metadata ở lượt 1 và bằng chứng rút gọn ở lượt 2, không nhận raster hay toàn bộ ephemeris. Đây là tập đánh giá, không phải tập huấn luyện/fine-tune.

## Luồng API

1. `GET /api/assistant/capabilities`: phạm vi dữ liệu, cấu hình cố định và các ràng buộc hỗ trợ.
2. `POST /api/assistant/parse`: nhận prompt, baseline đầy đủ và danh sách điểm được chọn. LLM lượt 1 tạo RequestPatch; backend chuẩn hóa UTC, kiểm tra lưới, phạm vi, cấu hình. Trả draft và spec để người dùng kiểm tra; chưa chạy phân tích.
3. `POST /api/assistant/evaluate`: nhận `draft_id`, `spec_hash`, baseline hiện tại và `confirmed=true`. Kiểm tra baseline/source hash; chạy bộ đánh giá cũ; LLM lượt 2 chọn thứ tự giải thích và tham chiếu bằng chứng. Backend dựng câu và số từ dữ liệu đã kiểm tra. Lỗi giải thích/timeout thì dùng mẫu; không có lượt sửa thứ ba.

Payload mẫu cho bước 2 ở `tests/fixtures/assistant/request.json`. Ở bước 3, lấy draft_id/spec_hash từ phản hồi bước 2, truyền lại baseline. Gọi lại cùng draft đã xong trả kết quả cũ, không gọi thêm LLM. Draft hết hạn, thay baseline hay dữ liệu thì phải tạo yêu cầu mới.

Giới hạn: hai điểm P1, 72 giờ, panel 1 m, antenna 2 m; ngày bắt đầu từ 14/11 đến trước 28/11/2026 UTC trên lưới 15 phút, dữ liệu hoạt động tới 01/12. Hỗ trợ ngưỡng tối, mất Earth LOS và tỷ lệ có nắng (suy từ cận số giờ nắng/72). Không tự làm tròn ngày, mở rộng vùng hay thay phần cứng; không hỗ trợ mô hình năng lượng/pin. “Vùng này” trong pilot là danh sách site đang được chọn, chưa phải truy vấn điểm trong polygon tùy ý.

Lọc theo trạng thái từng site, không dùng overall_decision của API cũ làm kết luận tồn tại phương án. Chưa có điểm đạt thì chọn điểm FAIL ít vi phạm nhất, giữ `apply_allowed=false`. Điểm INDETERMINATE không được xếp hạng như đã biết. Không tự thay baseline; apply_allowed chỉ phản ánh ràng buộc đã xét trong scenario PROVISIONAL, không chứng nhận nhiệm vụ.

## Chạy trên Windows

Từ thư mục `G:\My Drive\H1\HOSA`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "./backend[test]"
Copy-Item .env.example .env
```

Chỉ sao chép khi chưa có `.env`; giữ khóa hiện có nếu đã cấu hình. Điền `OPENROUTER_API_KEY` và `OPENROUTER_MODEL` (model ID đầy đủ), giữ `ASSISTANT_ENABLED=true`. Model phải hỗ trợ JSON Schema với endpoint đang phục vụ. Nếu chủ động dùng model chỉ hỗ trợ JSON mode, đổi `OPENROUTER_RESPONSE_FORMAT=json_object`; backend vẫn validate cùng schema. Không tự đổi mode hoặc model khi lỗi. Không đưa key vào frontend hoặc commit `.env`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

Mở `http://127.0.0.1:8001/docs` để thử route. Dùng cổng 8001 để tách với backend cũ tại 8000. Khởi động lại server sau khi sửa `.env`. Model/key được đọc từ `.env` tại gốc repo `G:\My Drive\H1\HOSA`.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/assistant -q
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts/assistant_eval.py --live --limit 3
```

Offline dùng đầu ra LLM chuẩn bị trước và HTTP provider giả lập; kiểm tra được bộ tính thật, schema, nhánh lỗi và route nhưng không đo khả năng hiểu tiếng Việt. `prompts.json` có 14 câu/kịch bản gồm lùi ngày, múi giờ, 720 phút, thông tin thiếu, ngoài dữ liệu, đổi phần cứng, đổi thời lượng, lệch lưới và 75% nắng. Đây là tập nhỏ mới bám dữ liệu 2026; không tuyên bố đã chạy lại 31 fixture giả lập năm 2027 trước đây.

Live dùng OpenRouter thật qua route FastAPI trong tiến trình thử, không cần mở server riêng; cần extra test (TestClient). Có tối đa 2 request/ca đầy đủ, ít hơn khi bị chặn. Báo cáo lưu ở `data/cache/assistant/live-eval.json`, tách khỏi offline; fallback vẫn được đánh dấu là chưa đạt tiêu chí giải thích của LLM. Không tự chạy live khi chưa có key/model.

## Kết quả xác minh ngày 10/11/2026

| Kiểm tra | Kết quả |
| --- | --- |
| Bộ assistant mới | 50 passed, không có ca skip |
| Backend cũ | 32 passed, 1 failed do chưa cài DEM Site01, 3 skipped do thiếu raw DEM tùy chọn |
| Toàn bộ pytest backend | 82 passed, 1 failed, 3 skipped; không công bố toàn suite xanh |
| HTTP trên server localhost thật | Health và capabilities hoạt động; parse thiếu key/model trả 503 OPENROUTER_NOT_CONFIGURED |
| CLI live khi chưa có env | Dừng trước khi gọi API; không tạo kết quả LLM thật giả |
| Nguồn JPL | 4/4 JSON 5 phút khớp byte với gói Drive đã đối chiếu SHA-256 |
| Mã bộ tính và test cũ | Đối chiếu với feature/lunarsight-data: không đổi |
| LLM thật | Chưa chạy; chưa có key/model do người dùng cấu hình. Offline không đo chất lượng LLM |

Bằng chứng máy đọc: `data/cache/assistant/pytest.xml`, `validation-summary.json`, `http-smoke.json` (cache cục bộ, không commit). Trace API trả prompt_version, model, thời gian từng bước và token usage/cost nếu OpenRouter cung cấp; không chứa API key. Các deprecation warning của thư viện đã được ghi trong lần chạy, không được tính là lỗi mô hình.

Kho draft hiện lưu trong RAM với TTL/giới hạn và chống chạy trùng, phù hợp thử nghiệm một worker. Khởi động lại mất draft; triển khai nhiều worker cần thay bằng repository dùng chung. Chưa thay bằng cơ sở dữ liệu hoặc framework multiagent để tránh tăng phạm vi pilot.

Kiểm thử cũ `test_coverage_separates_visualization_from_science` yêu cầu DEM Site01 gốc chưa được git quản lý. Nếu chưa cài raw DEM, ca này báo thiếu dữ liệu; ba ca terrain có điều kiện skip. Không tạo raster giả hoặc sửa test để che tình trạng thiếu dữ liệu. Các kiểm thử assistant dùng sản phẩm đã xử lý và không cần tải toàn bộ raw dataset.

Tài liệu API đã đối chiếu: [OpenRouter overview](https://openrouter.ai/docs/api/reference/overview), [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs). Key ở Authorization header; endpoint cố định `https://openrouter.ai/api/v1/chat/completions`. Không tự retry, bật response-healing hay chuyển model.
