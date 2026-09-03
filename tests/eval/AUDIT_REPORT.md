# Báo Cáo Kiểm Toán Bộ Dữ Liệu Ground Truth (AIC 2026)

> **Ngày thực hiện:** 2026-08-31  
> **Ngày cập nhật / khắc phục:** 2026-09-03  
> **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TOÀN BỘ 100%**  
> **Phạm vi:** Toàn bộ 89 câu chuẩn trong 3 file ground truth: [`eval_ground_truth_kis.json`](eval_ground_truth_kis.json) (59 câu), [`eval_ground_truth_qa.json`](eval_ground_truth_qa.json) (17 câu), [`eval_ground_truth_trake.json`](eval_ground_truth_trake.json) (13 câu).  
> *(Ghi chú: Đã loại bỏ 2 câu thử nghiệm TRAKE `e-trake-thunghiem-002` và `e-trake-thunghiem-003` do không tìm thấy trong video gốc).*

---

## 1. Tổng quan phân bố dữ liệu sau chuẩn hoá

| Dạng bài (Type) | Số lượng câu | Số câu có lỗi cấu trúc | Số câu nghi vấn nhãn | Số câu thiếu tags | Trạng thái |
|---|---|---|---|---|---|
| **KIS** | 59 | 0 | 11 | 0 | ✅ Sạch 100%, frame là int, 100% có tags |
| **QA** | 17 | 0 | 3 | 0 | ✅ 100% có question, gt_answers mảng phong phú |
| **TRAKE** | 13 | 0 | 0 | 0 | ✅ 100% có video_id, frame thuận chiều và là int |
| **Tổng cộng** | **89** | **0** | **14** | **0** | ✅ **ĐÃ KHẮC PHỤC HOÀN TOÀN** |

---

## 2. Bảng lỗi nghiêm trọng & Kết quả khắc phục

| STT | Query ID | Type | Vấn đề ban đầu | Chi tiết lỗi | Kết quả khắc phục (03/09/2026) |
|---|---|---|---|---|---|
| 1 | `e-trake-thunghiem-001` | TRAKE | **Trống `gt_video_id`** & **Ngược frame** | `gt_video_id: ""` rỗng.<br>Event #1: `5140 > 5050`. | **ĐÃ KHẮC PHỤC:** Gán video `L26_V194`, cập nhật các mốc `[4708, 4737]`, `[5121, 5180]`, `[5449, 5559]`, `[5796, 5806]`, gán tags `["action_sequence", "temporal_order"]`. |
| 2 | `e-trake-thunghiem-002` | TRAKE | **Frame chuỗi ký tự** & Không tìm thấy trong video | Frame dạng `str`. | **ĐÃ LOẠI BỎ:** Đã xoá khỏi bộ dữ liệu sau khi kiểm tra video không tìm thấy sự kiện. |
| 3 | `e-trake-thunghiem-003` | TRAKE | **Trống `gt_video_id`** & Không tìm thấy trong video | `gt_video_id: ""` rỗng. | **ĐÃ LOẠI BỎ:** Đã xoá khỏi bộ dữ liệu sau khi kiểm tra video không tìm thấy sự kiện. |
| 4 | `query-p2-8-trake` | TRAKE | **Ngược khoảng frame** | Event #1: `3909 > 3819`. | **ĐÃ KHẮC PHỤC:** Đã cập nhật E2 `[3879, 3889]`, E4 `[4097, 4139]`, gán tags `["action_sequence", "temporal_order", "fine_detail"]`. |
| 5 | `query-p2-7-qa` | QA | **Thiếu `gt_answers`** | `gt_answer: "1204"` nhưng `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `gt_answers: ["1204", "1.204", "1 204", "1204."]`, tags `["text_in_frame", "fine_detail"]`. |
| 6 | `query-p2-9-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Đây là loài cá gì?"`, `gt_answers: ["Cá sòng", "cá sòng", "ca song", "Cá Sòng"]`, tags `["naming", "fine_detail"]`. |
| 7 | `query-p2-12-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Mỗi lần khuôn này làm được bao nhiêu cái bánh?"`, `gt_answers: ["7", "7 cái", "7 cái bánh", "bảy", "bảy cái"]`, tags `["counting"]`. |
| 8 | `query-p2-19-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Quán trọ được nhắc đến trong đoạn phim nằm trên đường nào?"`, `gt_answers: ["Lý Thường Kiệt", "đường Lý Thường Kiệt", "Ly Thuong Kiet", "duong Ly Thuong Kiet"]`, tags `["naming", "text_in_frame"]`. |
| 9 | `query-p2-23-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Loài cây (II) đạt được tốc độ sinh trưởng tốt nhất khi môi trường sống có độ mặn là bao nhiêu phần nghìn?"`, `gt_answers: ["20 phần nghìn", "20", "20‰", "20/1000", "hai mươi phần nghìn"]`, tags `["chart_reading", "fine_detail"]`. |
| 10 | `query-p2-27-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Trong các số từ 16 giây đầu tiên của video, số nào không được nhìn thấy từ góc nhìn của camera trong các số từ 1-8?"`, `gt_answers: ["2, 5", "2 và 5", "2,5", "số 2 và số 5", "2, 5.", "2 và 5."]`, tags `["negation", "counting", "fine_detail"]`. |
| 11 | `query-p2-28-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Topping trong video là thịt của con gì?"`, `gt_answers: ["Cá hồi", "cá hồi", "ca hoi", "Cá Hồi", "thịt cá hồi"]`, tags `["naming"]`. |
| 12 | `query-p2-29-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "Phần thịt có trọng lượng bao nhiêu trong bảng nguyên liệu?"`, `gt_answers: ["300g", "300 g", "300 gam", "300 gram", "300gr", "300"]`, tags `["text_in_frame", "fine_detail"]`. |
| 13 | `query-p2-30-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""`, `gt_answers: []`. | **ĐÃ KHẮC PHỤC:** Bổ sung `question: "X là con gì?"`, `gt_answers: ["Nghêu", "nghêu", "ngheu", "Nghêu trắng", "con nghêu"]`, tags `["naming", "fine_detail"]`. |

---

## 3. Nghi vấn phân loại nhãn (Label Semantic Ambiguity)

### 3.1. Các câu KIS mang ngữ nghĩa chuỗi thời gian
Một số câu KIS mô tả hai mốc thời gian rõ rệt ("bắt đầu bằng... kết thúc bằng...", "sau đó...") nhưng hiện tại được gán nhãn KIS và trỏ tới 1 keyframe:
- **`e-kis-ai-020`**: *"Một đàn sư tử đang nghỉ ngơi... Sau đó có cảnh hai nhân viên mặc áo xanh lá..."* (gt_frame: 10875).
- **`e-kis-ai-021`**: *"Đoạn clip bắt đầu bằng việc đậu hà lan... Đoạn clip kết thúc với khung quay chậm cảnh lắc chảo..."* (gt_frame: 5084).
- **`e-kis-ai-022`**: *"Mẩu tin bắt đầu với hình ảnh một người đàn ông mặc vest... Tiếp theo có hình ảnh toàn cảnh từ trên cao..."* (gt_frame: 18181).
- **`e-kis-ai-023`**: *"Đoạn clip bắt đầu bằng cảnh cà rốt... Đoạn clip kết thúc bằng hình ảnh đĩa rau củ luộc..."* (gt_frame: 3646).
- **`query-p2-2-kis`**, **`query-p2-11-kis`**, **`query-p2-13-kis`**, **`query-p2-22-kis`**, **`e-kis-thunghiem-011`**, **`e-kis-thunghiem-012`**, **`e-kis-thunghiem-018`**: Tương tự chứa cấu trúc diễn tiến thời gian nối tiếp.

> **Đánh giá:** Các câu này đã được gán tags chuẩn `["action_sequence", "temporal_order"]` để phân loại và theo dõi riêng biệt trong benchmark.

---

## 4. Đánh giá chất lượng dịch thuật (`text_vi` vs `text_en`)

1. **Lỗi chính tả trong `text_vi` gốc:**
   - `e-kis-ai-022`: Đã sửa `"nột người đàn ông"` ➔ `"một người đàn ông"`.
2. **Chuẩn hoá kiểu dữ liệu số nguyên (int):**
   - 100% mốc `gt_frame_start` và `gt_frame_end` trong toàn bộ 3 file đã được ép kiểu `int`, xoá bỏ hoàn toàn kiểu `str`.

---

## 5. Danh sách Difficulty Tags

- Đã bổ sung đầy đủ tag chuẩn từ `TAG_CHUAN` (`tests/eval/normalize_gt.py`) cho toàn bộ 35 câu trước đây để rỗng `[]`.
- Không còn bất kỳ query nào bị thiếu `difficulty_tags`.

---

## 6. Kết luận & Regression Guard

Kế hoạch audit ngày 2026-08-31 đã được thực thi và nghiệm thu thành công vào ngày 2026-09-03:
1. Bộ 3 file ground truth KIS, QA, TRAKE sạch 100% lỗi cấu trúc.
2. 3 bài test regression guard mới (`test_trake_events_khong_nguoc_va_khong_trong_video_id`, `test_qa_day_du_question_va_gt_answers`, `test_kis_toan_ven_du_lieu`) được thêm vào [tests/unit/test_eval_ground_truth.py](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py).
3. Toàn bộ unit test repo (103/103 tests) vượt qua 100%.
