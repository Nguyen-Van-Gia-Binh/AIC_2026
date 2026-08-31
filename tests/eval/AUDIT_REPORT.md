# Báo Cáo Kiểm Toán Bộ Dữ Liệu Ground Truth (AIC 2026)

> **Ngày thực hiện:** 2026-08-31  
> **Phạm vi:** Toàn bộ 91 câu trong 3 file ground truth con: [`eval_ground_truth_kis.json`](eval_ground_truth_kis.json) (59 câu), [`eval_ground_truth_qa.json`](eval_ground_truth_qa.json) (17 câu), [`eval_ground_truth_trake.json`](eval_ground_truth_trake.json) (15 câu).  
> **Mục tiêu:** Rà soát tính chính xác của nhãn (type), chất lượng bản dịch `text_vi` vs `text_en`, tính nhất quán của câu hỏi/đáp án QA, chuỗi sự kiện TRAKE, và phát hiện các lỗi cấu trúc/dữ liệu.  
> **Nguyên tắc:** **KHÔNG tự ý sửa nội dung file dữ liệu** trong quá trình phân tách; toàn bộ bất thường được ghi nhận tại đây để lập kế hoạch sửa lỗi sau khi người dùng phê duyệt.

---

## 1. Tổng quan phân bố dữ liệu

| Dạng bài (Type) | Số lượng câu | Số câu có lỗi cấu trúc | Số câu nghi vấn nhãn | Số câu thiếu tags |
|---|---|---|---|---|
| **KIS** | 59 | 0 | 11 | 20 |
| **QA** | 17 | 9 (thiếu `question` / `gt_answers`) | 3 | 10 |
| **TRAKE** | 15 | 3 (trống video_id / ngược frame) | 0 | 5 |
| **Tổng cộng** | **91** | **12** | **14** | **35** |

---

## 2. Bảng lỗi nghiêm trọng (Critical / High Severity)

Các lỗi này ảnh hưởng trực tiếp đến tính đúng đắn khi chạy evaluation/benchmark hoặc gây crash harness:

| STT | Query ID | Type | Vấn đề phát hiện | Chi tiết lỗi | Đề xuất hướng sửa (Phase sau) |
|---|---|---|---|---|---|
| 1 | `e-trake-thunghiem-001` | TRAKE | **Trống `gt_video_id`** & **Ngược khoảng frame** | `gt_video_id: ""` rỗng.<br>Event #1: `gt_frame_start: 5140 > gt_frame_end: 5050`. | Bổ sung video ID tương ứng từ bộ đề thử nghiệm (ví dụ `L21_V...`) và đảo lại khoảng `[5050, 5140]`. |
| 2 | `e-trake-thunghiem-003` | TRAKE | **Trống `gt_video_id`** | `gt_video_id: ""` rỗng. | Bổ sung `gt_video_id` tương ứng từ video thử nghiệm. |
| 3 | `query-p2-8-trake` | TRAKE | **Ngược khoảng frame** | Event #1: `gt_frame_start: 3909 > gt_frame_end: 3819`. | Đảo lại khoảng frame thành `[3819, 3909]`. |
| 4 | `query-p2-7-qa` | QA | **Thiếu `gt_answers`** | `gt_answer: "1204"` nhưng `gt_answers: []` (danh sách rỗng). | Điền `gt_answers: ["1204", "1.204"]`. |
| 5 | `query-p2-9-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "Dĩa cơm sườn"`. | Trích xuất câu hỏi từ `text_en`: `question: "What is the main dish on the plate?"`, `gt_answers: ["Dĩa cơm sườn", "cơm sườn", "com suon"]`. |
| 6 | `query-p2-12-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "4"`. | `question: "How many people are in the frame?"`, `gt_answers: ["4", "bốn", "four", "4 người"]`. |
| 7 | `query-p2-19-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "7"`. | `question: "What is the number shown on the screen?"`, `gt_answers: ["7", "bảy", "seven"]`. |
| 8 | `query-p2-23-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "Màu đỏ"`. | `question: "What color is the object?"`, `gt_answers: ["Màu đỏ", "đỏ", "red"]`. |
| 9 | `query-p2-27-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "2, 5"`. | `question: "Which numbers are not visible from the camera viewpoint?"`, `gt_answers: ["2, 5", "2 và 5", "2,5"]`. |
| 10 | `query-p2-28-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "Cá hồi"`. | `question: "What animal's meat is the topping?"`, `gt_answers: ["Cá hồi", "ca hoi", "salmon"]`. |
| 11 | `query-p2-29-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "300g"`. | `question: "What is the weight of the meat portion?"`, `gt_answers: ["300g", "300 gam", "300 gram"]`. |
| 12 | `query-p2-30-qa` | QA | **Thiếu `question` & `gt_answers`** | `question: ""` (chuỗi rỗng), `gt_answers: []`, `gt_answer: "Nghêu"`. | `question: "What creature is X?"`, `gt_answers: ["Nghêu", "ngheu", "clam", "nghêu trắng"]`. |

---

## 3. Nghi vấn phân loại nhãn (Label Semantic Ambiguity)

### 3.1. Các câu KIS mang ngữ nghĩa chuỗi thời gian (Nên xem xét chuyển sang TRAKE)
Một số câu KIS mô tả hai mốc thời gian rõ rệt ("bắt đầu bằng... kết thúc bằng...", "sau đó...") nhưng hiện tại chỉ được gán nhãn KIS và trỏ tới đúng 1 keyframe duy nhất:

- **`e-kis-ai-020`**: *"Một đàn sư tử đang nghỉ ngơi... Sau đó có cảnh hai nhân viên mặc áo xanh lá..."* (gt_frame: 10875).
- **`e-kis-ai-021`**: *"Đoạn clip bắt đầu bằng việc đậu hà lan... Đoạn clip kết thúc với khung quay chậm cảnh lắc chảo..."* (gt_frame: 5084).
- **`e-kis-ai-022`**: *"Mẩu tin bắt đầu với hình ảnh một người đàn ông mặc vest... Tiếp theo có hình ảnh toàn cảnh từ trên cao..."* (gt_frame: 18181).
- **`e-kis-ai-023`**: *"Đoạn clip bắt đầu bằng cảnh cà rốt... Đoạn clip kết thúc bằng hình ảnh đĩa rau củ luộc..."* (gt_frame: 3646).
- **`query-p2-2-kis`**: *"Đoạn clip bắt đầu bằng... Đoạn clip kết thúc với..."*.
- **`query-p2-11-kis`**, **`query-p2-13-kis`**, **`query-p2-22-kis`**, **`e-kis-thunghiem-011`**, **`e-kis-thunghiem-012`**, **`e-kis-thunghiem-018`**: Tương tự chứa cấu trúc diễn tiến thời gian nối tiếp.

> **Đánh giá & Khuyến nghị:**
> - Nếu BTC ra đề KIS yêu cầu tìm "đoạn video" chứa chuỗi hành động và chỉ nộp 1 frame đại diện, thì nhãn KIS vẫn chấp nhận được nhưng cần ghi chú rõ frame đại diện là mốc đầu hay mốc cuối.
> - Nếu là bài toán TRAKE (yêu cầu nộp chuỗi mốc), các câu này nên được tách thành các `events` với mốc `gt_frame` riêng biệt cho từng hành động.

### 3.2. Cấu trúc câu hỏi trong nhóm QA
- Các câu `e-qa-thunghiem-001`, `e-qa-thunghiem-002`, `e-qa-thunghiem-003` trong phần `text_vi` là câu tường thuật ("Cảnh một người...", "Hình ảnh..."), trong khi câu hỏi thực tế được đặt trong trường `question` tiếng Anh. Khuyến nghị chuẩn hoá lại `text_vi` để có câu hỏi tiếng Việt tương ứng.

---

## 4. Đánh giá chất lượng dịch thuật (`text_vi` vs `text_en`)

1. **Lỗi chính tả trong `text_vi` gốc:**
   - `e-kis-ai-022`: *"Mẩu tin bắt đầu với hình ảnh **nột** người đàn ông..."* -> gõ nhầm `"nột"` thay vì `"một"`. Bản dịch tiếng Anh `text_en` đã dịch đúng thành *"a man"*.
2. **Độ tương thích với SigLIP Text Encoder:**
   - Hầu hết các câu `text_en` do người dịch tay (`e-kis-ai-*`, `e-qa-ai-*`) có chất lượng ngữ nghĩa và độ chi tiết thị giác rất tốt (màu sắc, góc quay, vị trí).
   - Một số câu dịch tự động trong nhóm `query-p2-*` dịch từ ngữ địa phương hoặc tên món ăn còn thô (ví dụ: *"dĩa cơm sườn"*, *"hoa riềng tía"*), cần rà soát lại để tránh làm giảm độ chính xác khi đối sánh embedding.

---

## 5. Danh sách Difficulty Tags

- Hiện có **35/91 câu** có trường `difficulty_tags: []` (danh sách rỗng).
- Khuyến nghị trong phase sửa lỗi: Bổ sung các tag chuẩn từ `TAG_CHUAN` (`tests/eval/normalize_gt.py`) như `counting`, `text_in_frame`, `short_action`, `multi_similar_object`, `temporal_order` cho 35 câu này để hỗ trợ breakdown đánh giá độ khó.

---

## 6. Kế hoạch đề xuất cho Phase sửa lỗi tiếp theo (Action Plan)

1. **Bước 1:** Trình duyệt bảng sửa lỗi chi tiết (điền `gt_video_id` cho 2 câu TRAKE thử nghiệm, đảo ngược 2 khoảng frame, điền `question` & `gt_answers` cho 9 câu QA).
2. **Bước 2:** Bổ sung `difficulty_tags` cho 35 câu chưa có tag.
3. **Bước 3:** Chạy `normalize_gt.py` và cập nhật lại cả 3 file con `eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`.
