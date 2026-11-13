# Hướng dẫn Mission planning (Trợ lý HOSA)

Cập nhật: 13/11/2026 · áp dụng cho nhánh `feat/merge-fe-be`

## 1. Mission planning làm được gì

Mission planning là chế độ của Trợ lý giúp bạn đặt câu hỏi nhiệm vụ bằng lời thường, tiếng Việt hoặc tiếng Anh, rồi nhận kết luận kèm giải thích. Nó làm được ba việc:

| Việc | Bạn hỏi kiểu | Tương đương tab |
|---|---|---|
| **Khám phá một điểm** | "Phân tích Connecting Ridge bắt đầu 24/11/2026 09:00 UTC trong 72 giờ" | Khám phá |
| **So sánh hai điểm** | "So sánh Haworth với Malapert Massif từ 1/12/2026 đến 15/12/2026 UTC" | So sánh |
| **Tìm thời điểm tốt nhất** | "Tìm giờ bắt đầu tốt nhất cho Shackleton Rim trong tháng 12/2026" | Thời điểm tốt nhất |

Mỗi câu trả lời đều dựa trên kết quả tính của backend cho đúng điểm, ngày và ngưỡng bạn hỏi. Chatbot không tự ước lượng.

### Dùng chung thiết lập với các tab

Chat lấy **thiết lập nhiệm vụ hiện tại** của tab Khám phá, So sánh và Thời điểm tốt nhất. Mặc định gồm:
- tấm pin và ăng-ten cao **20 m**;
- chiếu sáng tối thiểu **80%**;
- liên lạc liên tục **≥ 30 phút**, thiết lập 5 phút, 1 cửa sổ, liên lạc đầu tiên trong 120 phút;
- khoảng tối và mất Earth LOS liên tục tối đa 12 giờ và 6 giờ (mong muốn mềm, không làm trượt kết quả);
- **không** đặt ngưỡng Earth LOS (%).

Vì vậy cùng điểm, cùng ngày, cùng thiết lập thì chat và các tab cho cùng kết quả. Đổi thiết lập ở tab trước khi bắt đầu hội thoại thì chat dùng thiết lập mới. Trong hội thoại có thể đổi ngay bằng lời: `nếu tấm pin chỉ cao 1 m và ăng-ten 2 m thì sao?`, `thêm yêu cầu Earth LOS 80%`. Bản Review luôn ghi chiều cao thiết bị đang dùng.

**Vì sao chiều cao quan trọng:** ở cực Nam, Mặt Trời và Trái Đất nằm rất thấp trên đường chân trời. Ví dụ Connecting Ridge ngày 26/11/2026: thiết bị cao 20 m nhận nắng 100%, còn cao 1 m thì 0% vì bị địa hình che. Cả hai kết quả đều đúng với chiều cao tương ứng.

### Danh sách điểm (27 điểm, đồng bộ với các tab)

Chat chỉ phân tích đúng **27 điểm** có trong danh sách tab Khám phá, So sánh và Thời điểm tốt nhất. Đây là tâm vùng NASA công bố, lấy từ `manifests/compare-sites.json`:

Connecting Ridge (Site01), Shackleton Rim (Site04), Nobile Rim 1 (Site06), Peak Near Shackleton (Site07), de Gerlache Rim 1 (Site11), Leibnitz Beta Plateau (Site20), Leibnitz Beta Plateau (extended boundaries) (Site20v2), Malapert Massif (Site23), de Gerlache-Kocher Massif (Site42), Haworth, Shoemaker, Amundsen Rim (DM1), Nobile Rim 2 (DM2), de Gerlache Rim 2 (SL2), Connecting Ridge Extension (SL3), Cabeus Exterior Wall 1 (NPA), Amundsen 1 (NPB), Idel'son L Crater 1 (NPC), Malapert Crater 1 (NPD), Shackleton Rim B (LM1), Shoemaker Rim A–E (LM2–LM6), Faustini Rim A (LM7), Shoemaker Rim F (LM8).

- Các điểm khác như IM-1, IM-2, VIPER, Mons Mouton hay điểm quan sát cũ Site01_P1 / Site04_P1 **không** dùng trong chat. Nếu bạn nêu, chatbot sẽ nói rõ điểm đó không thuộc 27 điểm và hỏi bạn chọn điểm khác.
- Tên dễ nhầm vẫn được phân biệt: Connecting Ridge với Connecting Ridge Extension, Shackleton Rim với Shackleton Rim B, Malapert Massif với Malapert Crater 1.
- Leibnitz Beta Plateau và bản "(extended boundaries)" có **cùng tâm vùng**, nên kết quả giống hệt nhau; câu trả lời sẽ nói rõ điều này.
- Bản Review và thẻ kết quả hiện tên kèm tọa độ, ví dụ "Connecting Ridge (89.4632°S 137.4900°W)".

## 2. Số liệu đến từ đâu

Luồng của mỗi câu hỏi:

1. **LLM hiểu yêu cầu.** Nó xác định điểm, ngày giờ, thời lượng, ngưỡng và khoảng tìm. Backend kiểm tra lại tên điểm theo danh mục, kiểm tra ngày giờ hợp lệ, và hỏi lại nếu còn thiếu.
2. **Bạn xác nhận bản Review.** Đây là những gì sẽ được tính: điểm, ngày, thời lượng, ngưỡng.
3. **Engine tính.** Engine dùng chung với các tab:
   - So sánh và Khám phá qua chat gọi `PlanningService.compare`, giống tab So sánh (`/planning/compare`).
   - Tìm thời điểm tốt nhất gọi `PlanningService.search`, giống tab Thời điểm tốt nhất (`/planning/windows/search`).
   - Khi tính theo tọa độ, cả hai dùng pipeline `point_analysis` của tab Khám phá: DEM NASA LOLA, SPICE/JPL, đường chân trời địa hình.
4. **LLM giải thích.** LLM chỉ nhận kết quả của engine (quyết định, chỉ số, nguyên nhân, kiểm chứng) và viết thành lời. Backend kiểm tra rằng quyết định PASS/FAIL/INDETERMINATE của từng phương án được chép đúng từ engine. Một lượt rà soát thứ hai bỏ các khẳng định không có căn cứ.

**LLM không tự tính, không đổi kết luận, không nới ngưỡng.** Ví dụ ngày 20/11/2026, Connecting Ridge đạt 72% và Shackleton Rim 28% chiếu sáng so với yêu cầu 80%. Đây đúng là số engine trả về khi chạy trực tiếp.

### Kiểm chứng tự động (13/11/2026)

Script `scripts/mission_chat_live_check.py` chạy thật 29 kịch bản (35 lượt hội thoại, tiếng Việt và tiếng Anh) qua LiteLLM. Với mỗi lượt có kết quả, script kiểm ba việc:

1. **Đối chiếu với tab:** gọi lại đúng tham số đó trên API của tab So sánh (`/planning/compare`) hoặc Thời điểm tốt nhất (`/planning/windows/search`), rồi so từng phương án: trạng thái, quyết định, mọi chỉ số, khuyến nghị, số mốc đã thử.
2. **Đối chiếu với tab Khám phá:** với khám phá một điểm, chạy `/lunar/point/analyses` và so số giờ chiếu sáng và số giờ thấy Trái Đất.
3. **Soát từng con số trong câu trả lời:** mỗi số %, giờ, phút, số mốc phải suy ra được từ kết quả engine. Mọi tên điểm được nhắc tới phải là điểm đã được tính. Câu trả lời không được nói "khả thi" khi engine không kết luận như vậy.

Kết quả lần chạy mới nhất (dùng thiết lập mặc định của các tab): 36 kịch bản, 44 lượt hội thoại, **0 lượt bị đánh dấu**.
- 43 lượt có kết quả (17 so sánh, 16 khám phá, 10 tìm thời điểm) khớp hoàn toàn với API các tab.
- 16/16 lần đối chiếu với tab Khám phá khớp cả quyết định lẫn số giờ chiếu sáng và thấy Trái Đất.
- Mọi con số trong câu trả lời đều đúng với engine.
- Lượt còn lại là câu hỏi 3 điểm: chatbot hỏi lại như mong đợi.

Bộ kịch bản có cả yêu cầu liên lạc, phần chưa hỗ trợ và câu hỏi tiếp.

Chạy lại (cần backend đang chạy và `.env` có key LiteLLM):

```bash
python scripts/mission_chat_live_check.py              # toàn bộ kịch bản
python scripts/mission_chat_live_check.py --case-id VI-BEST-WEEK
```

Danh sách kịch bản: `tests/fixtures/assistant/mission_chat_live_cases.json`. Script trả mã lỗi khác 0 nếu có lượt bị đánh dấu.

## 3. Cách dùng trên giao diện

1. Mở tab **Trợ lý** (hoặc nút **Hỏi** ở góc dưới), chọn **Mission planning**.
2. Bấm **New conversation** khi bắt đầu một chủ đề mới.
3. Gõ câu hỏi rồi nhấn **Enter** để gửi. **Shift+Enter** để xuống dòng.
4. Nếu chatbot hỏi lại (thường là ngày giờ bắt đầu), trả lời ngắn, ví dụ `24/11/2026 lúc 9 giờ UTC`.
5. Kiểm tra bản **Review** (điểm, ngày, thời lượng, ngưỡng, khoảng tìm và bước tìm, yêu cầu liên lạc) rồi bấm **Confirm evaluation**.
6. Đọc câu trả lời. Số liệu chi tiết nằm trong thẻ kết quả bên dưới.

Lượt đầu tiên của một hội thoại bắt buộc phải có ngày bắt đầu hoặc khoảng tìm. Các lượt sau tự giữ điểm, ngày và ngưỡng của lượt trước.

## 4. Khám phá một điểm

Cần có: tên điểm, ngày giờ bắt đầu kèm múi giờ, và thời lượng (mặc định 72 giờ) hoặc ngày kết thúc.

Ví dụ:
- `Phân tích Connecting Ridge bắt đầu 24/11/2026 lúc 09:00 UTC trong 72 giờ`
- `Is Haworth OK for a 5-day mission from Dec 3 2026 00:00 UTC if I need 70% sunlight and 50% Earth line of sight?`
- `explore Haworth`. Chatbot sẽ hỏi ngày, rồi hỏi giờ và múi giờ nếu bạn chỉ nêu ngày.

Kết quả: đạt hay không đạt, yêu cầu nào quyết định, và đạt bao nhiêu % so với ngưỡng.

## 5. So sánh hai điểm

- Tối đa **2 điểm mỗi lượt**. Nếu nêu 3 điểm trở lên, chatbot sẽ hỏi bạn chọn 2.
- So sánh tại một mốc: `So sánh Haworth với Malapert Massif ngày 17/11/2026 00:00 UTC` (mặc định 72 giờ).
- So sánh cả khoảng ngày: `So sánh Shackleton Rim với Malapert Massif từ 1/12/2026 00:00 UTC đến 15/12/2026 00:00 UTC`. Hệ thống tính một nhiệm vụ kéo dài trọn khoảng đó (ở đây 336 giờ), không chỉ ngày đầu.
- Tên điểm được tra theo danh mục 27 điểm (xem mục "Danh sách điểm"): `site01`, `site 01`, `điểm 01`, `R01` → Connecting Ridge; `site04` → Shackleton Rim…

Kết quả: điểm nào tốt hơn hoặc cả hai đều không đạt, vì sao, và mức chênh so với ngưỡng.

## 6. Tìm thời điểm tốt nhất

Cần có: điểm (1 hoặc 2), khoảng cho phép đổi ngày bắt đầu, và thời lượng nhiệm vụ.

Ví dụ:
- `Tìm ngày bắt đầu tốt nhất cho Connecting Ridge từ 14/11/2026 00:00 UTC đến 15/11/2026 00:00 UTC, nhiệm vụ 72 giờ`
- `Trong tháng 12/2026 (từ 1/12 đến 31/12/2026 UTC), ngày nào bắt đầu tốt nhất cho Shackleton Rim với nhiệm vụ 72 giờ?`
- `Tìm thời điểm bắt đầu có nhiều nắng nhất cho Malapert Massif từ 20/11/2026 đến 21/11/2026 UTC, nhiệm vụ 48 giờ` (xếp hạng theo nắng)

- `hãy tìm thời điểm tốt nhất cho điểm connecting ridge tại 26/11/2026 00:00 UTC trong 72 giờ` (chỉ nêu một mốc: hệ thống tìm tiếp từ mốc đó trong giới hạn 128 lượt, ở đây là đến trước 27/11 08:00 với bước 15 phút)

Cách tìm:
- Engine thử tối đa **128 mốc bắt đầu mỗi lượt** (64 mốc mỗi điểm khi tìm cho 2 điểm).
- **Bước tìm được tự chọn** cho vừa giới hạn: 1 ngày → 15 phút, 1 tuần → 80 phút, 1 tháng → 6 giờ. Bạn có thể tự nêu, ví dụ "bước một giờ".
- Khoảng quá dài (ví dụ cả năm) thì chatbot đề nghị bạn thu hẹp lại.
- Xếp hạng mặc định theo tổng thời gian nhìn thấy Trái Đất. Có thể đổi: "ưu tiên nắng nhiều nhất", "khoảng tối dài nhất ngắn nhất"…
- Chat trả về **3 khung tốt nhất không trùng nhau**. Tab Thời điểm tốt nhất trả về tối đa 10.

Câu trả lời nêu số mốc đã thử, bước tìm, số mốc đạt. Nếu không mốc nào đạt, phương án đứng đầu chỉ là **gần đạt nhất**, không phải khuyến nghị.

### Yêu cầu liên lạc với Trái Đất

Có thể thêm yêu cầu liên lạc vào bất kỳ câu hỏi khám phá, so sánh hay tìm thời điểm nào. Đây là yêu cầu cứng, engine kiểm tra từ các cửa sổ nhìn thấy Trái Đất liên tục:

| Bạn nói | Nghĩa |
|---|---|
| `thời lượng liên lạc 70 phút`, `liên lạc liên tục ít nhất 70 phút` | Cần một cửa sổ liên lạc liên tục ≥ 70 phút |
| `thời gian thiết lập 10 phút` | Mỗi lần liên lạc cần 10 phút chuẩn bị trước |
| `cần 2 cửa sổ liên lạc riêng` | Cần 2 cửa sổ tách biệt, mỗi cửa sổ đủ dài |
| `liên lạc đầu tiên trong vòng 6 giờ` | Lần liên lạc đầu phải xong trong 6 giờ sau khi bắt đầu |

Yêu cầu liên lạc được giữ cho các lượt hỏi tiếp, ví dụ `nếu cần liên lạc liên tục 600 phút thì sao?`. Engine dừng ở yêu cầu cứng đầu tiên bị trượt: nếu chiếu sáng hoặc Earth LOS đã không đạt thì yêu cầu liên lạc **chưa được đánh giá**, và câu trả lời sẽ nói rõ điều này. Nếu chỉ muốn xét liên lạc, hãy đặt ngưỡng nắng và Earth LOS về 0%.

Khi bạn không nêu ngưỡng nắng hay Earth LOS, hệ thống dùng **ngưỡng mặc định 80%**, và câu trả lời sẽ ghi rõ đó là ngưỡng mặc định.

### Khi có phần chưa hỗ trợ

Nếu câu hỏi có phần chat chưa tính được (ví dụ nhiệt độ bề mặt), chatbot nêu đúng phần đó và liệt kê những gì đang hỗ trợ. Trả lời `bỏ phần đó, tính tiếp` để tiếp tục với phần còn lại mà không phải gõ lại câu hỏi.

## 7. Hỏi tiếp trong cùng hội thoại

Các lượt sau giữ nguyên điểm, ngày và ngưỡng, chỉ đổi phần bạn nêu:
- Đổi ngưỡng: `giờ hạ ngưỡng Earth LOS xuống 60% xem sao`
- Dời ngày: `lùi ngày bắt đầu thêm 3 ngày, giữ nguyên mọi thứ khác`
- Hỏi lý do: `vậy điểm nào tốt hơn và vì sao?`
- Hỏi số cụ thể: `Shackleton Rim thiếu bao nhiêu so với yêu cầu chiếu sáng?` Khi bạn hỏi "bao nhiêu" hoặc "số liệu", câu trả lời nêu số giờ cụ thể.
- Đổi ngôn ngữ: hỏi bằng tiếng Anh thì được trả lời bằng tiếng Anh.

Mỗi câu hỏi tiếp vẫn đi qua bản Review và cần bấm Confirm, vì hệ thống luôn tính lại từ engine.

## 8. Đọc câu trả lời

| Trạng thái | Ý nghĩa |
|---|---|
| **PASS / khả thi** | Đạt mọi yêu cầu cứng, đã qua kiểm chứng |
| **FAIL / không đạt** | Vi phạm ít nhất một yêu cầu cứng (chiếu sáng hoặc Earth LOS) |
| **INDETERMINATE / chưa xác định** | Chưa đủ căn cứ. Thường do kiểm chứng địa hình hoặc độ ổn định chưa đạt. Không phải đạt, cũng không phải trượt |

- "Đạt 72% so với yêu cầu 80%" là tỷ lệ thực tế engine tính so với ngưỡng bạn đặt.
- **Chiếu sáng** là tỷ lệ trung bình phần đĩa Mặt Trời nhìn thấy được, không phải công suất pin.
- **Earth LOS** là đường nhìn hình học tới tâm Trái Đất, không phải chất lượng liên lạc vô tuyến.
- Kết quả 0% có thể là thật: điểm nằm trong bóng tối, hoặc Trái Đất ở dưới đường chân trời suốt nhiệm vụ.

## 9. Giới hạn và lưu ý

- Mỗi lượt mất khoảng 5 giây để hiểu câu hỏi và 10–15 giây để giải thích. Tìm khoảng dài cần thêm thời gian engine tính, có thể tới khoảng 2 phút.
- Chỉ dùng 27 điểm của danh sách Khám phá. Tọa độ chỉ được nhận khi trùng một trong 27 điểm (sai số 1 m); tọa độ tùy ý hãy dùng mục "Tọa độ tùy chọn" ở các tab.
- Chiều cao tấm pin và ăng-ten tối đa 30 m. Các thay đổi thiết bị khác (hiệu suất pin, công suất phát…) chưa hỗ trợ.
- Ngày kiểu Việt `3/12/2026` được hiểu là ngày 3 tháng 12. Hiểu được "noon", "midnight", "1 giờ chiều", "8h tối".
- Kết quả là đánh giá hình học nguyên mẫu (PROVISIONAL). Không chứng nhận an toàn hạ cánh, nhiệt độ, pin hay liên lạc vô tuyến.
- Cấu hình nhanh (`.env`): `LLM_PROXY_REASONING_EFFORT=low` và `ASSISTANT_MAX_CONCURRENT_PER_PROVIDER=4`. Thiếu hai dòng này thì chatbot vẫn chạy nhưng chậm hơn nhiều.

## 10. Kịch bản kiểm thử mẫu

Mỗi kịch bản bắt đầu bằng **New conversation**. Dấu → là câu trả lời khi chatbot hỏi lại.

| # | Câu hỏi | Mong đợi |
|---|---|---|
| 1 | `Phân tích Connecting Ridge bắt đầu 24/11/2026 lúc 09:00 UTC trong 72 giờ` | Chạy luôn, nêu % chiếu sáng so với 80% |
| 2 | `explore Haworth` → `11/24/2026` → `9 AM UTC` | Hỏi ngày, rồi giờ và múi giờ; trả lời tiếng Anh |
| 3 | `Phân tích Malapert Massif` → `ngày 3/12/2026 lúc 1 giờ chiều UTC` | Hiểu ngày 3 tháng 12, 13:00 |
| 4 | `so sánh site01 và site04` → `bắt đầu 14/11/2026 00:00 UTC` | Chỉ hỏi ngày; so sánh Connecting Ridge với Shackleton Rim |
| 5 | `So sánh Shackleton Rim với Malapert Massif từ 1/12/2026 00:00 UTC đến 15/12/2026 00:00 UTC` | Tính trọn 336 giờ |
| 6 | `Compare Shackleton Rim, Malapert Massif and Haworth starting Dec 3 2026 00:00 UTC for 72 hours` | Hỏi chọn 2 điểm, không báo lỗi |
| 7 | `Tìm ngày bắt đầu tốt nhất cho Connecting Ridge từ 14/11/2026 00:00 UTC đến 15/11/2026 00:00 UTC, nhiệm vụ 72 giờ` | 96 mốc, bước 15 phút |
| 8 | `Tìm thời điểm bắt đầu tốt nhất cho Connecting Ridge trong khoảng 17/11/2026 đến 24/11/2026 UTC, nhiệm vụ 72 giờ` | 126 mốc, bước 80 phút |
| 9 | `Find the best start for Malapert Massif anywhere in 2027 (Jan 1 2027 to Jan 1 2028 UTC), 72-hour mission` → `search only January 2027` | Đề nghị thu hẹp, sau đó tìm với bước 6 giờ |
| 10 | `So sánh Connecting Ridge và Shackleton Rim nhiệm vụ 72 giờ bắt đầu 20/11/2026 00:00 UTC` → `giờ hạ ngưỡng Earth LOS xuống 60% xem sao` → `lùi ngày bắt đầu thêm 3 ngày` → `vậy điểm nào tốt hơn và vì sao?` | Giữ ngữ cảnh; giải thích hạ Earth LOS không đổi kết quả vì cái chặn là chiếu sáng |

Bộ kiểm thử tự động liên quan: `tests/assistant/test_mission_chat_fixes.py`.
