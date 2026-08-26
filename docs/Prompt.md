
# Prompt: Kế hoạch cải thiện hệ thống Tìm kiếm Keyframe Video (AIC 2026)

## PHẦN I: BỐI CẢNH DỰ ÁN

### 1.1 Mục tiêu cuộc thi

- **Cuộc thi**: AIC 2026 — Video Retrieval Challenge (TP.HCM)
- **Dữ liệu**: 177K keyframes từ ~1000 video, được trích từ kho video của BTC
- **3 nhiệm vụ chính**:
  1. **KIS (Known Item Search)**: Cho query văn bản → trả `<video_id, frame_id>` (1 mốc duy nhất)
  2. **Q&A (Visual Question Answering)**: Cho query + câu hỏi → trả `<video_id, frame_id, answer>`
  3. **TRAKE (Temporal Retrieval & Alignment)**: Cho query + N mốc sự kiện → trả `<video_id, frame_id₁, ..., frame_idₙ>`
- **Công thức chấm điểm**: R-Score (Reciprocal Rank) trung bình ở ranks 1/5/20/50/100; Sai video = 0 điểm tuyệt đối.
- **Hạn chế cuộc thi**: Tối đa 3 lần nộp bài; Sai format bị tính 1 lượt nộp vĩnh viễn.

### 1.2 Kiến trúc hiện tại

```
Query (text) 
  ↓
[Shared Retriever]: CLIP ViT-B/32 (embedding 177K keyframes)
  ↓
[3 Pipelines riêng biệt]:
  • KIS: tuyến tính (không LLM), 1 lệnh retrieve
  • Q&A: orchestrator-workers (≤2 vòng reflection, bắt buộc cross-check vs Objects JSON)
  • TRAKE: 2 giai đoạn (chọn video → align N mốc theo thứ tự tăng dần)
  ↓
[Submission Builder]: Ghi CSV theo chuẩn BTC → ZIP
```

**Quyết định kiến trúc đã chốt:**

- ✓ KIS không cần LLM (query đơn giản → retrieve đúng nguyên tắc là xong)
- ✓ Q&A bắt buộc cross-check (CLIP + Objects JSON + LLM Vision) để chống ảo giác
- ✓ TRAKE cố định 2 giai đoạn (không để LLM tự quyết định bước kỳ tiếp theo)
- ✓ 1 nguồn cấu hình LLM duy nhất (`agent/config.py`)
- ✓ File-based, không database

### 1.3 Nhân tố hạn chế từ kiến trúc CLIP baseline

Từ tài liệu "Bộ Đề Kiểm Thử & Phân Tích Bẫy AIC2026", những bẫy **Critical** mà CLIP hiện tại không xử lý tốt:

| Bẫy ID      | Vấn đề                                   | Ảnh hưởng                                                                         | Hướng giải quyết khả dĩ                                 |
| ------------ | ------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| KIS-01       | Phủ định (CLIP mù phủ định)          | "không đội nón" ≈ vector gần hệt "đội nón"                                 | Dịch lại thành dương tính + object detector lọc        |
| KIS-06       | Query dài >77 token (cắt ngắn)           | Vector trung bình quá lỏng, cần rút gọn về 1 khoảnh khắc trọng tâm        | Bước "distill" query dài trước encode                    |
| KIS-09       | Tranh chấp thuộc tính (binding problem)  | "áo đỏ xe xanh" ≈ "áo xanh xe đỏ" về vector                                  | Object detector + bounding box xác nhận cặp gán           |
| QA-04, QA-05 | OCR / Đọc text nhỏ                       | CLIP mù chữ, VLM hay diễn giải lại thay vì trích chính xác                  | OCR chuyên dụng hoặc VLM có khả năng OCR kiểm chứng   |
| QA-07        | Tiền đề sai (presupposition trap)        | LLM "chiều" tiền đề sai thay vì kiểm tra trước                               | Chỉ dẫn tường minh + cross-check độc lập               |
| TRAKE-01     | Sai video (near-duplicate videos)           | Video gần hệt nhau về thị giác, embedding không phân biệt sự kiện cụ thể | Lưu ý: khi similarity video hàng đầu sát nhau = rủi ro |
| TRAKE-03     | Hành động lặp lại (repetitive actions) | Model trả về lần có similarity cao nhất, không biết "lần thứ 2"             | Clustering theo thời gian + chọn đúng cụm thứ N         |

---

## PHẦN II: 9 Ý TƯỞNG CẢI THIỆN (Tái cấu trúc)

### **Nhóm A: Tăng Chất Lượng Tìm Kiếm Keyframe Ban Đầu (Giai đoạn 1)**

#### Ý tưởng 1: Đa mô hình Embedding (Ensemble)

**Mô tả hiện tại:**

- Hệ thống dùng 1 model duy nhất: CLIP ViT-B/32 (embedding 512-d)
- Có sẵn 4 model trong `kaggle_jobs/` đã encode 177K keyframes: ViT-L/14, SigLIP SO400M, Jina CLIP v2, DFN-5B ViT-H/14
- Nhưng chỉ 1 model được load mặc định, các model khác bị bỏ

**Ý tưởng cải thiện:**

- Xây dựng framework **voting/fusion** để dùng 2-3 model cùng lúc
- Cơ chế tối ưu: **Reciprocal Rank Fusion (RRF)** hoặc trung bình ngược lại ranking score
  - Lợi ích: Tăng recall, giảm "blind spot" của 1 model (e.g., CLIP yếu ở tiếng Việt, nhưng SigLIP có thể mạnh hơn)
  - Rủi ro: Latency tăng, chi phí tính toán 3× (nhưng load chỉ 1 lần startup)

**Liên quan đến bẫy:**

- KIS-01 (phủ định): SigLIP / Jina có thể xử lý phủ định tốt hơn CLIP ViT-B
- KIS-09 (binding): DFN cực mạnh về attribute binding (visual cấu trúc chặt)
- KIS-08 (góc quay bất thường): ViT-L/14 train trên dữ liệu đa dạng hơn

**Yêu cầu cụ thể:**

- Chọn 2-3 model nào? (Tiêu chí: latency production, điểm baseline từ eval, tạm thời giả định Jina cho kế hoạch sau vì chưa chạy xong)
- Công thức fusion nào? (Weighted RRF hay averaging score?)
- Khi nào dùng single model (test fast), khi nào dùng ensemble (test final)?

---

#### Ý tưởng 2: Viết lại Query Thông minh (Query Rewrite)

**Mô tả hiện tại:**

- Pipeline Q&A/TRAKE có sẵn `rewrite.py` (VN→EN)
- Nhưng chỉ dịch ngôn ngữ, không tối ưu cấu trúc query cho CLIP

**Ý tưởng cải thiện:**

- Mở rộng rewrite thành 3 bước:
  1. **Lọc nhiễu**: Xóa phần mô tả không liên quan đến hình ảnh (vd. "theo mình là" → bỏ)
  2. **Chuẩn hóa ngữ pháp**: Đảo ngữ → S-V-O đơn giản (vd. "Dưới tán cây, người phát biểu..." → "Person wearing red speaking...")
  3. **Gán dấu thừa nhân cách**: Dùng LLM sinh thêm từ khóa ngắn bổ sung chi tiết (vd. thêm "standing"/"walking" nếu action không rõ)

**Prompt tối ưu cho việc rewrite:**

```
"Viết lại câu sau thành 1 mô tả hình ảnh ngắn gọn, chỉ giữ lại chi tiết thị giác.
Cấu trúc: [người/vật chủ yếu] [hành động] [chi tiết phân biệt: màu sắc, bối cảnh, góc quay].
Tránh từ trừu tượng, tránh phủ định."
```

**Liên quan đến bẫy:**

- KIS-02 (đảo ngữ): chuẩn hóa cấu trúc
- KIS-04 (tiếng lóng): LLM giải thích → mô tả thị giác
- KIS-06 (query dài): rút gọn về 1 khoảnh khắc trọng tâm
- QA-07 (tiền đề sai): phát hiện & highlight tiền đề trước tìm kiếm

**Yêu cầu cụ thể:**

- Prompt template nào tốt nhất cho LLM? (Gemini, Groq hay NVIDIA NIM?)
- Có cần feedback loop từ user không? (nếu rewrite lần 1 không match, hỏi người dùng "bạn muốn nói gì?")
- Cost: Gọi LLM cho mỗi query = có chấp nhận không?

---

### **Nhóm B: Tăng độ tin cậy sau khi Retrieve (Giai đoạn 2-3)**

#### Ý tưởng 3: Metadata từ Transcript Video

**Mô tả hiện tại:**

- Chỉ có keyframe (ảnh) + Objects JSON (object detector)
- Không có transcript (text content) từ audio video

**Ý tưởng cải thiện:**

- **Tạo transcript** cho từng video bằng **Speech-to-Text (STT)**
- Cung cấp ngữ cảnh lmn khi:
  - Query là câu hỏi về "người nói cái gì" (Q&A)
  - TRAKE cần xác định thứ tự N mốc dựa trên "ai nói gì đó khi nào"

**Các công cụ STT:**

- **OpenRouter**: Hỗ trợ Transcription (19 models) — qua API
- **Whisper (OpenAI)**: Model mở, chạy local (CPU/GPU)
- **Google Cloud Speech**: Chất lượng cao nhưng phí + quota

**Lợi ích:**

- Bổ sung ngữ cảnh rich cho Q&A ("Người phát biểu nói gì?" → tra transcript)
- Giúp phân biệt near-duplicate videos (TRAKE-01) qua nội dung lời nói

**Rủi ro:**

- **Chi phí**: Encode 1000 video × 5-30 phút mỗi video = hàng giờ compute
- **Quality**: STT tiếng Việt có thể lỗi, cần kiểm chứng bằng mắt
- **Storage**: Transcript text có thể lớn

**Yêu cầu cụ thể:**

- Dùng công cụ STT nào? (Giới hạn chi phí?)
- Chỉ extract **partial transcript** quanh keyframe cần (ví dụ: ±30s trước/sau frame?) để tiết kiệm?
- Tích hợp vào Q&A/TRAKE ra sao? (Append vào prompt LLM hay tìm kiếm transcript đầu tiên?)

---

#### Ý tưởng 4: OCR & Object Description từ Keyframe

**Mô tả hiện tại:**

- Objects JSON chỉ có tên class object ("person", "car", ...) + bounding box
- Không có OCR (đọc chữ) hoặc description từng object chi tiết

**Ý tưởng cải thiện:**

- **Tầng 1 — OCR**: Dùng Tesseract (local) hoặc VLM có khả năng OCR

  - Trích text từ biển hiệu, logo, số áo, slide, ...
  - Lưu dưới dạng: `{frame_id: {x, y, w, h, text}}`
- **Tầng 2 — Object Description**: Dùng VLM mini (tùy model) để miêu tả từng object

  - Thay vì chỉ "person", tạo "person wearing red shirt, standing"
  - Giúp binding problem (KIS-09) tìm đúng người/vật

**Các công cụ:**

- **Tesseract** (open-source, chạy local): Tốc độ nhanh, chất lượng 7/10 với tiếng Việt
- **EasyOCR** (Python, local): Chất lượng 8/10, hỗ trợ Việt + 80+ ngôn ngữ
- **VLM nhỏ** (Phi-3, LLaVA local): Có khả năng OCR + description

**Lợi ích:**

- KIS-04, KIS-06: Metadata phong phú → query match tốt hơn
- QA-04, QA-05, QA-06: Đọc text trên ảnh
- KIS-09: Xác nhận attribute-object pair (e.g., "red shirt" + "person ID 5")

**Rủi ro:**

- Chi phí compute tăng (encode 177K × 2 = 354K frames)
- OCR lỗi ở ảnh mờ/nhỏ (yêu cầu fallback LLM nếu OCR fail)

**Yêu cầu cụ thể:**

- Chọn Tesseract hay EasyOCR hay VLM để OCR?
- Chạy trực tiếp hay qua OpenRouter API?
- Lưu metadata ở đâu? (Extend Objects JSON? File `.npy` riêng?)

---

#### Ý tưởng 5: Feedback Loop & Query Refinement

**Mô tả hiện tại:**

- Nếu KIS/Q&A trả lỗi, hệ thống không có cơ chế "hỏi lại người dùng để tối ưu"

**Ý tưởng cải thiện:**

- Tạo vòng lặp feedback **có trần**:
  1. Retrieve 100 candidate đầu tiên
  2. Nếu top-1 có confidence < ngưỡng (e.g., 0.4):
     - Tự động yêu cầu user: "Bạn có thể mô tả rõ hơn không? (ví dụ: người mặc gì, ở đâu?)"
     - Hoặc đề xuất: "Có phải một trong 5 kết quả này không?"
  3. User xác nhận hoặc gõ mô tả thêm
  4. Rewrite query dùng feedback → retrieve lại 1 lần (không quá 2 vòng)

**Cơ chế chính:**

```python
def run_kis_with_feedback(query, max_iterations=2):
    for i in range(max_iterations):
        rewritten = rewrite_query(query)
        hits = retrieve(rewritten, top_k=100)
        if hits[0]['score'] > threshold:
            return hits[0]
        else:
            user_feedback = ask_user(f"Iteration {i}: {len(hits)} results found. Refine?")
            query = query + " " + user_feedback  # append feedback
    return hits[0]  # best effort
```

**Lợi ích:**

- Tăng precision KIS (đặc biệt khi query mơ hồ)
- Giúp xử lý KIS-05 (query siêu ngắn)

**Rủi ro:**

- Tỏ ra "hệ thống không biết", có thể làm user mất tin tưởng (nếu query rõ ràng mà còn hỏi lại)
- Bài thi không cho phép tương tác → **chỉ dùng cho test/prototype, KHÔNG cho contest mode**

**Yêu cầu cụ thể:**

- Ngưỡng confidence bao nhiêu mới kích hoạt hỏi lại? (Điểm từ similarity score hay ranking RRF?)
- Độ dài lịch sử feedback tối đa bao nhiêu? (Tránh prompt overlong khi đưa vào LLM)
- Chỉ dùng cho UI test hay cần hỗ trợ batch mode?

---

#### Ý tưởng 6: Cross-Check Đa Tầng (Anti-hallucination)

**Mô tả hiện tại:**

- Q&A đã có cross-check vs Objects JSON (1 tầng)
- Nhưng TRAKE chưa có cross-check (chỉ retrieve + align)

**Ý tưởng cải thiện:**

- **Tầng 1 (Hiện tại)**: Objects JSON vs LLM answer (Q&A)
- **Tầng 2 (Mới)**: Transcript vs LLM answer (nếu answer là quote)
- **Tầng 3 (Mới)**: Re-rank video TRAKE bằng semantic similarity với toàn bộ query (TRAKE-01)
  - Tính average similarity của N mốc so với description của từng video
  - Nếu top-2 videos rất sát nhau → đó là tín hiệu rủi ro, cần xác nhận thêm

**Lợi ích:**

- Giảm hallucination (QA-03, QA-07)
- Tăng confidence khi chốt video (TRAKE-01)

**Rủi ro:**

- Tăng latency (gọi thêm LLM, tính toán thêm)

**Yêu cầu cụ thể:**

- Transcript cross-check như thế nào? (Exact match? Semantic similarity? Substring?)
- Ngưỡng sát nhau bao nhiêu để trigger cảnh báo (TRAKE-01)?
- Có threshold score tối thiểu bắt buộc hay chỉ đưa ra cảnh báo?

---

### **Nhóm C: Tối Ưu Chiến Lược Nộp Bài (Giai đoạn Cuối)**

#### Ý tưởng 7: Dynamic Model Selection

**Mô tả hiện tại:**

- Toàn bộ cuộc thi dùng 1 bộ model cố định (giống nhau cho test lẫn contest)

**Ý tưởng cải thiện:**

- Tạo **2 plan khác nhau**:
  1. **Test Plan** (development): Dùng model "rẻ" để tối ưu hóa tốc độ
     - Các model suy luận miễn phí gọi qua OpenRouter
     - Dùng để iterate nhanh, test feature mới
  2. **Contest Plan** (production): Dùng model "xịn" để tối ưu điểm
     - Gemini 3.7 Flash (đắt tiền hơn)
     - Dùng chỉ khi nộp bài thật

**Điểu khiển:**

- Biến môi trường `AIC_MODE=test|contest`
- Hoặc config file `config.test.json` vs `config.contest.json`

**Lợi ích:**

- Tiết kiệm chi phí phát triển (test nhiều không bị burn ngân sách)
- Tận dụng tối đa OpenRouter free/low-cost models lúc test

**Rủi ro:**

- "Hệ thống tốt lúc test nhưng tệ lúc thi" nếu không test kỹ bằng contest plan
- Cần ít nhất 1-2 lần run full pipeline bằng contest plan trước ngày thi

**Yêu cầu cụ thể:**

- Config structure nào? (ENV vars hay YAML file?)
- Có unit test để validate chế độ contest hay chỉ manual test?
- Chi phí dự kiến mỗi chế độ?

---

#### Ý tưởng 8: Risk-Aware Ranking & Budget Allocation

**Mô tả hiện tại:**

- Hệ thống luôn trả 100 dòng mà không tính tới mức độ tin cậy

**Ý tưởng cải thiện:**

- **Chế độ 1**: Nếu top-1 confidence cao (>0.7):

  - Đặt cược top-10 dòng lên cùng video (mở rộng recall trong top-10)
  - Mục đích: Ăn trọn R@1 + tối ưu R@5
- **Chế độ 2**: Nếu top-1 confidence thấp (<0.5):

  - Trải đều 100 dòng trên 10-20 video khác nhau (1 frame mỗi video, hoặc vài frame trên top-5)
  - Mục đích: Tìm sàn an toàn ở R@50/R@100 (RANK-02, phân tán rủi ro)
- **Chế độ 3**: Confidence trung bình (0.5-0.7):

  - Hỗn hợp: Top-20 dòng cùng video, còn lại spread
  - Tối ưu hóa trung bình expected value

**Công thức RRF weight:**

- Nếu đa mô hình: Model yếu nhất đạt consensus → confidence cao
- Nếu 1 model: Similarity score bình thường hóa (0-1)

**Liên quan đến bẫy:**

- RANK-02: Phân tán rủi ro khi tin cậy thấp
- RANK-01: Đặt cược top-1 khi tin cậy cao

**Yêu cầu cụ thể:**

- Ngưỡng confidence 0.7 / 0.5 có phù hợp? (Cần calibrate từ validation set)
- Công thức tính confidence từ similarity score nào? (Simple mapping? Softmax?)
- Có ranking heuristic nào cho KIS vs Q&A vs TRAKE khác nhau?

---

#### Ý tưởng 9: Temporal Alignment Constraints

**Mô tả hiện tại:**

- TRAKE align N mốc bằng cách retrieve độc lập mỗi event, rồi lấy top-1 frame từng cái
- Không kiểm chứng thứ tự thời gian (frame_id phải tăng dần)

**Ý tưởng cải thiện:**

- Ràng buộc tường minh:
  1. **Đơn điệu tăng dần**: Mốc j phải có `frame_id_j > frame_id_(j-1)`
  2. **Cửa sổ thời gian**: Nếu query mô tả 10 giây, span 4 mốc phải ≤ 10×30fps = 300 frame
  3. **Clustering**: Nếu 1 event lặp lại trong video (TRAKE-03), cluster frame theo thời gian rồi chọn cụm thứ k

**Implementation:**

```python
def align_with_constraints(events, video_frames, k_events=4):
    # Retrieve candidates cho mỗi event
    candidates = [retrieve(e, top_k=20) for e in events]
  
    # Ràng buộc 1: frame_id tăng dần
    valid_paths = []
    def backtrack(event_idx, last_frame_id, current_path):
        if event_idx == len(events):
            valid_paths.append(current_path[:])
            return
        for cand in candidates[event_idx]:
            if cand['frame_id'] > last_frame_id:
                current_path.append(cand)
                backtrack(event_idx+1, cand['frame_id'], current_path)
                current_path.pop()
  
    backtrack(0, 0, [])
  
    # Ràng buộc 2: Chọn path có tổng score cao nhất
    best = max(valid_paths, key=lambda p: sum(f['score'] for f in p))
    return best
```

**Lợi ích:**

- TRAKE-04 (vi phạm thứ tự thời gian): Không thể xảy ra nữa
- TRAKE-03 (hành động lặp lại): Ưu tiên frame theo cụm thứ tự

**Rủi ro:**

- Latency tăng (backtracking search thay vì greedy top-1)
- Nếu constraints quá chặt, có thể không tìm được valid path

**Yêu cầu cụ thể:**

- Cửa sổ thời gian max bao nhiêu? (10s, 30s hay 60s?)
- Nếu không tìm được valid path thì fallback ra sao? (Relax constraints hay return empty?)
- Có cần optimize backtracking (branch-and-bound) hay brute-force được chấp nhận?

---

## PHẦN III: YÊU CẦU ĐÁNH GIÁ & KẾ HOẠCH

### 3.1 Yêu cầu từ bạn

Dựa trên 9 ý tưởng trên, vui lòng:

1. **Đánh giá từng ý tưởng** (1-9):

   - ✓ Khả thi kỹ thuật (hay có blocking issue?)
   - ⏱️ Thời gian cần để triển khai (tính theo "người.ngày")
   - 💰 Chi phí (OpenRouter API / compute resource)
   - ⚠️ Rủi ro (liệu có làm hệ thống chậm hay crash?)
   - 🎯 Kỳ vọng cải thiện điểm (ước lượng sơ bộ)
2. **Xác định ưu tiên** (Critical → High → Medium):

   - Ý tưởng nào **bắt buộc** trước ngày thi?
   - Ý tưởng nào **tùy chọn** (nice-to-have)?
   - Ý tưởng nào **rủi ro quá cao** (không đáng làm)?
3. **Kế hoạch triển khai chi tiết**:

   - Trình tự implement từng ý tưởng (dependency graph)
   - Milestone chính (vd. "Tuần 1: Ý tưởng 1+2", "Tuần 2: Ý tưởng 3")
   - Điểm kiểm chứng (benchmark, unit test)
4. **Xác định những bẫy cần xử lý**:

   - Ý tưởng 1-2 giải quyết bẫy nào? (KIS-01, KIS-06, etc.)
   - Ý tưởng nào **không giải quyết được bẫy gì** mà chỉ tối ưu?
   - Có bẫy **Critical** nào vẫn bỏ ngỏ** sau khi implement tất cả?
5. **Prototype test plan**:

   - Làm sao validate mỗi ý tưởng trước khi merge?
   - Có eval set nào để benchmark (vd. "Bo De Kiem Thu" cases)?

### 3.2 Context bổ sung

- **Giới hạn thời gian**: Sắp tới thi từ 7h30 - 10h30, rồi đợt 2 ngày 28/7, đợt 4 ngày 4/9 (đã setup backup chuẩn bị rồi cứ thoải mái lên kế hoạch để nâng cấp)
- **Ngân sách chi phí**: 10 đô hoặc hơn
- **Team size**: 4 thành viên
- **Model baseline**: Hiện tại đang 5 điểm muốn vượt top đạt điểm gần tối đa

---

## PHẦN IV: Lưu Ý Kỹ Thuật

- **KHÔNG đặt cược quá sâu vào 1 ý tưởng nếu chưa kiểm chứng**: Thử prototype nhanh trước khi commit resource
- **Luôn giữ single-model baseline hoạt động** (Đổi qua Siglip và đưa model clip 32 vào lưu trữ): Dùng làm fallback nếu ensemble fail
- **Mọi thay đổi phải validate qua validation set** (không chỉ eyeball results): Có thể một ý tưởng làm tốt 1 trường hợp nhưng tệ hơn average
- **QA-03, QA-07 (hallucination) là ưu tiên cao nhất cho Q&A**: Vì sai answer = R-Score = 0 tuyệt đối

---

## PHẦN V: Tệp Đính Kèm Tham Khảo

- `ARCHITECTURE.md`: Kiến trúc hiện tại + quyết định đã chốt
- `Bo De Kiem Thu va Phan Tich Bay AIC2026.md`: Catalog 30+ bẫy, chi tiết cơ chế + hướng fix
- `Thong tin vong So tuyen AIC2026.md`: Luật thi chính thức

---

**End of Prompt**
