# Kế hoạch Pha 2 — Sửa 8 lỗi hành vi

> **Spec:** [2026-08-31-phase2-behavior-fixes-design.md](../specs/2026-08-31-phase2-behavior-fixes-design.md)
> **Nhánh:** `fix/phase2` (tách từ `main` sau khi merge Pha 1)

**Mục tiêu:** Sửa 8 lỗi hành vi P2.1–P2.8, mỗi mục có số đo trước–sau riêng, mỗi mục một commit.

## Ràng buộc toàn cục

Áp dụng cho **mọi** task bên dưới:

- `pytest tests/unit -q` phải xanh sau mỗi task. Hiện là **59 passed**.
- Mọi số đo so sánh chạy ở `AIC_MODE=test`. **Không bao giờ** lấy số từ `AIC_MODE=local`.
- Mỗi task đổi hành vi phải ghi một khối vào `docs/reports/phase2_measurement_log.md`
  (digest trước/sau, Final trước/sau) **trước khi** commit.
- Luật single-call-site giữ nguyên: LLM chỉ ở `scripts/agent/config.py:call_llm()`;
  CSV/ZIP chỉ ở `scripts/submit/build_submission.py`.
- Import nội bộ dùng tiền tố `scripts.`; **chỉ repo root** trên `sys.path`.
- Comment/UI tiếng Việt có dấu. Ngoại lệ: prompt LLM trong `qa_prompts.py` và
  `pipeline_trake.py` (tiếng Anh — đổi một ký tự là đổi hành vi hệ thống).
- `frame_id = frame_idx + 1` chỉ xảy ra ở `index_store.py:row_to_hit()`.
- Không commit `.env`; `.env.example` chỉ chứa placeholder.

## Lệnh hay dùng

```
.venv\Scripts\python.exe -m pytest tests\unit -q
.venv\Scripts\python.exe tests\e2e\golden_kis_snapshot.py --check
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types kis            # 0 đồng
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types qa             # cần API key
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types trake          # cần API key
```

---

## Task 0 — Hạ tầng đo (không đổi hành vi)

**Files:** tạo `docs/reports/phase2_measurement_log.md` · sửa `scripts/agent/config.py` ·
sửa `.env.example` · sửa `CLAUDE.md`

- [x] **0.1** Chốt lại golden snapshot trên `main` sau merge: `golden_kis_snapshot.py --check`.
  Ground truth đã đổi 33 → 38 câu, nhưng golden snapshot chạy trên 18 câu KIS của **file riêng**
  nên phải xác nhận digest vẫn là `81448536a4f1245f`. Nếu đổi → dừng, điều tra trước khi đi tiếp.
- [x] **0.2** Chốt baseline mới trên 38 câu: `score_pipelines.py --types kis --save-baseline`
  (KIS miễn phí, chạy trước). Ghi số vào nhật ký.
- [x] **0.3** Thêm `AIC_MODE=local` vào `config.py`: khi `AIC_MODE == "local"`, `PROVIDER_CHAIN`
  chỉ có một nhà cung cấp trỏ tới LM Studio qua tiền tố `lm_studio/` của LiteLLM,
  `api_base` đọc từ env `LM_STUDIO_BASE` (mặc định `http://localhost:1234/v1`),
  tên model đọc từ `LM_STUDIO_MODEL`. Nới `if AIC_MODE not in (...)` cho nhận `"local"`.
- [x] **0.4** Thêm `LM_STUDIO_BASE` / `LM_STUDIO_MODEL` vào `.env.example` (placeholder).
- [x] **0.5** Thêm mục vào `CLAUDE.md`: bảng 3 chế độ + cảnh báo **số đo từ `local` không dự báo
  được điểm thi thật**; và sửa lại chữ của luật cấm precompute OCR cho khớp ý thật
  (cấm chạy hàng loạt trên đường truy vấn / máy dev, không cấm shard trên Kaggle).
- [x] **0.6** `pytest tests/unit -q` xanh. Commit.

---

## Task 1 — P2.8: gỡ production khỏi phụ thuộc `tests/`

**Files:** `git mv tests/eval/multi_index.py scripts/agent/tools/multi_index.py` ·
sửa `scripts/agent/tools/index_store.py` · sửa `tests/eval/run_eval.py`

**Tiêu chí đặc biệt:** đây là task **duy nhất** mà golden digest **phải khớp**
`81448536a4f1245f`. Digest đổi = lỗi, không phải tính năng.

- [x] **1.1** `git mv` để giữ lịch sử file.
- [x] **1.2** `index_store.py:94` — đổi `from multi_index import get_index, get_encoder, MODEL_REGISTRY`
  thành `from scripts.agent.tools.multi_index import ...`. **Bỏ** khối chèn `tests/eval/` vào
  `sys.path` ngay trên đó (đó chính là cái đã gây bug nạp index 2 bản 4 lần).
- [x] **1.3** `run_eval.py:51` — đổi `from multi_index import ...` thành
  `from scripts.agent.tools.multi_index import ...`; bỏ khối `sys.path` trỏ tới thư mục hiện tại.
- [x] **1.4** Grep toàn repo `multi_index` — sửa mọi tham chiếu còn lại, kể cả trong docstring
  và comment (`fusion.py:16`, `hybrid.py:130`, `index_store.py:11/65/88`, `retrieve.py:19`,
  `golden_kis_snapshot.py:4`, `test_phase3_rerank.py:5`).
- [x] **1.5** `pytest tests/unit -q` xanh.
- [x] **1.6** `golden_kis_snapshot.py --check` → **phải khớp** `81448536a4f1245f`.
- [x] **1.7** Xác nhận `run_eval.py --models siglip --limit 3` vẫn chạy (import ngược không gãy).
- [x] **1.8** Commit: `fix(P2.8): chuyen multi_index vao scripts/agent/tools`.

---

## Task 2 — P2.1: Q&A dùng `siglip2` thay vì `siglip`

**Files:** `scripts/agent/tools/index_store.py:52` · docstring `pipeline_qa.py:18-20`

- [x] **2.1** Ghi digest + Final QA **trước khi sửa** vào nhật ký.
- [x] **2.2** `index_store.py:52` — đổi mặc định `"siglip"` → `"siglip2"`. Giữ nguyên khả năng
  ghi đè bằng env `AIC_QA_MODEL`. Cập nhật docstring dòng 10 cho khớp.
- [x] **2.3** `pipeline_qa.py` — xoá đoạn cảnh báo "Sai lệch giữa code và tài liệu này CHƯA được
  xử lý: xem PLAN.md P2.1" vì đã xử lý; thay bằng một câu nêu lý do chọn `siglip2` + số bake-off.
- [x] **2.4** `score_pipelines.py --types qa` với `AIC_MODE=test`. Ghi Final trước/sau.
- [x] **2.5** `golden_kis_snapshot.py --check` — **phải vẫn khớp** (KIS dùng `_MODEL_TAG` riêng,
  không đụng `_QA_MODEL_TAG`). Nếu đổi thì hai đường model đang lẫn nhau ⇒ dừng, điều tra.
- [x] **2.6** `pytest tests/unit -q` xanh. Commit.

---

## Task 3 — P2.2: TRAKE trả đủ 100 dòng

**Files:** `scripts/agent/pipeline_trake.py:120` (+ docstring dòng 10, 132)

- [x] **3.1** Ghi Final TRAKE trước khi sửa.
- [x] **3.2** Đổi `top_k_video: int = 20` → `100`. Kiểm tra `results` không bị cắt ở chỗ khác
  (grep `[:20]`, `top_k_video` trong file).
- [x] **3.3** Xác nhận cổng LLM **không** mở rộng theo: crosscheck vẫn chỉ chạy khi margin #1–#2
  ≤ `TRAKE_CROSSCHECK_MARGIN` và tối đa 3 video. Nếu số lượt gọi LLM tăng theo `top_k_video`
  thì dừng — mục này phải **miễn phí về LLM**.
- [x] **3.4** `score_pipelines.py --types trake`. Kỳ vọng R@50/R@100 tăng, R@1/R@5 không đổi.
- [x] **3.5** `pytest tests/unit -q` xanh. Commit.

---

## Task 4 — P2.3: `strict_monotonic` hạ tiêu chuẩn thay vì loại video

**Files:** `scripts/agent/pipeline_trake.py:200-203` · có thể chạm
`scripts/agent/tools/trake_align.py`

- [x] **4.1** Ghi Final TRAKE trước khi sửa.
- [x] **4.2** Viết test trước ở `tests/unit/test_trake_align.py`: dựng `event_hits` mà hai mốc
  buộc phải rơi vào **cùng một `frame_idx`**; khẳng định `find_best_increasing_chain(strict=True)`
  trả `None` còn `strict=False` trả một chuỗi. Chạy — phải PASS ngay (đây là hành vi đã có, test
  này khoá nó lại trước khi sửa chỗ gọi).
- [x] **4.3** `pipeline_trake.py`: khi `chain is None`, thử lại `strict=False` thay vì `continue`.
  Đánh dấu kết quả đó (ví dụ `chain_relaxed = True`) và **xếp sau** mọi chuỗi tăng nghiêm ngặt
  khi sắp thứ hạng video — hạ tiêu chuẩn để cứu video, không phải để nó vượt lên.
- [x] **4.4** Thêm test ở `tests/unit/test_pipeline_trake.py`: video chỉ có chuỗi nới lỏng vẫn
  xuất hiện trong kết quả, nhưng xếp sau video có chuỗi nghiêm ngặt cùng điểm.
- [x] **4.5** `score_pipelines.py --types trake`. `pytest tests/unit -q` xanh. Commit.

---

## Task 5 — P2.6: Q&A trích answer cho nhiều cụm hơn

**Files:** `scripts/agent/tools/answer_qa.py:146` · `scripts/agent/pipeline_qa.py:44,64-88`

- [x] **5.1** Ghi Final QA trước khi sửa (đã đo ở Task 2, dùng lại nếu chưa đổi gì khác).
- [x] **5.2** `answer_from_hits()` — thêm tham số `max_tier: int = 2`. Khi `max_tier == 1`:
  chạy Tầng 1 (Objects JSON) rồi **dừng**; không vào Tầng 2 Vision, không gọi OCR. Nếu Tầng 1
  không trả lời được thì trả `{"answer": "", ..., "method": "fallback"}` như hiện tại.
  Chữ ký cũ giữ nguyên mặc định ⇒ mọi lời gọi hiện có không đổi hành vi.
- [x] **5.3** Test ở `tests/unit/test_answer_qa.py`: monkeypatch `answer_qa.call_llm` đếm số lượt
  gọi; khẳng định `max_tier=1` gọi **tối đa 1 lượt văn bản** và **không** gọi Vision.
  ⚠️ Patch đúng module sở hữu hàm (`answer_qa`), không patch qua `qa_normalize` — lỗi này đã xảy
  ra 2 lần, xem `docs/decisions-log.md`.
- [x] **5.4** `pipeline_qa.py` — tách `MAX_ANSWER_CLUSTERS = 3` thành hai hằng:
  `FULL_ANSWER_CLUSTERS = 3` (chạy đủ tầng) và `CHEAP_ANSWER_CLUSTERS = 12` (chỉ Tầng 1).
  `answer_by_video_cluster()` chạy cụm 1–3 như cũ, cụm 4–15 với `max_tier=1`.
- [x] **5.5** Test ở `tests/unit/test_pipeline_qa.py`: với 15 video trong hits, số dòng mang
  answer **riêng của chính video mình** tăng rõ rệt so với 3.
- [x] **5.6** `score_pipelines.py --types qa`. Theo dõi cả Final **và** số lượt gọi LLM —
  nếu chi phí tăng quá 3× thì hạ `CHEAP_ANSWER_CLUSTERS`.
- [x] **5.7** `pytest tests/unit -q` xanh. Commit.

---

## Task 6 — P2.5: bật lại OCR + làm lỗi hiện rõ

**Files:** `scripts/agent/tools/ocr_read.py:88-100` · tạo `scripts/offline/ocr/fetch_vietocr_assets.py`
· `.gitignore`

Tài sản người dùng đã tải: `data/extracted/base.yml`, `data/extracted/vgg_transformer.pth` (151 MB).
Còn thiếu `vgg-transformer.yml`.

- [x] **6.1** Tạo `scripts/offline/ocr/fetch_vietocr_assets.py`: tải 2 YAML từ
  `https://vocr.vn/data/vietocr/config/{base.yml,vgg-transformer.yml}` với `verify=False`
  (host gốc chính thức, cert hết hạn), gộp vào **một** file `data/models/vietocr/config.yml`
  đã trỏ `weights` vào đường dẫn `.pth` cục bộ; di chuyển 2 file người dùng đã tải sang
  `data/models/vietocr/`. In rõ đường dẫn từng file. Chạy một lần, không nằm trên query path.
- [x] **6.2** `ocr_read.py` — thay `Cfg.load_config_from_name("vgg_transformer")` bằng
  `Cfg.load_config_from_file(_VIETOCR_CONFIG)` với `_VIETOCR_CONFIG = _ROOT/"data"/"models"/"vietocr"/"config.yml"`.
  Nếu file không tồn tại: **fail loud** với thông báo chỉ đúng lệnh `fetch_vietocr_assets.py`
  cần chạy — không nuốt vào `except` chung.
- [x] **6.3** Thêm hàm `ocr_health() -> tuple[bool, str]` trong `ocr_read.py`: kiểm tra đủ tài sản
  + nạp được engine, trả về `(ok, lý_do)`. Không tự nạp model nếu chỉ kiểm tra file.
- [x] **6.4** Thêm `tests/unit/test_ocr_read.py::test_ocr_health_bao_loi_ro_khi_thieu_tai_san` —
  monkeypatch đường dẫn sang thư mục rỗng, khẳng định `ocr_health()` trả `False` và lý do có nhắc
  tên script cần chạy. Test này **không cần** `data/` hay GPU.
- [x] **6.5** Gọi `ocr_health()` trong `scripts/api/main.py` lúc khởi động và in cảnh báo nổi bật
  nếu đỏ (không chặn khởi động — OCR là tín hiệu phụ).
- [x] **6.6** Thêm `data/models/` vào `.gitignore` (151 MB trọng số không lên git).
- [x] **6.7** Chạy thật: `python -c "from scripts.agent.tools.ocr_read import ocr_health; print(ocr_health())"`
  → phải xanh. Rồi chạy `tests/e2e/test_phase5_ocr.py` để xác nhận OCR đọc được chữ thật.
- [x] **6.8** `pytest tests/unit -q` xanh. Commit.

---

## Task 7 — Công cụ gán nhãn (giao sớm cho người dùng)

**Files:** tạo `tests/eval/normalize_gt.py` · viết lại `tests/eval/EVAL_GUIDE.md`

Task này **không đổi hành vi pipeline**. Ưu tiên giao sớm để người dùng gán nhãn song song.

- [x] **7.1** `normalize_gt.py`: đọc file v2 (`{"entries": [...]}`) → ghi file v1 (mảng) mà
  `run_eval.py` đọc được. Quy tắc chuyển đổi:
  - `query_text` → `text_vi`; sinh `text_en` bằng `scripts/agent/tools/translate_raw.py`
    (máy dịch, **không** LLM ⇒ tất định), ghi cờ `text_en_reviewed: false`.
  - `gt_frame` → `gt_frame_start = gt_frame_end = gt_frame` (**một keyframe**, chặt nhất).
    Chỉ dùng `gt_frame_end` nếu người ghi đã tự nhập.
  - `events[].gt_frame` → tương tự cho từng mốc TRAKE.
  - Giữ nguyên `question`, `gt_answers`, `gt_video_id`, `difficulty_tags`.
  - **Không tự nới khoảng.** Không gọi `widen_gt_windows.py`.
- [x] **7.2** Cờ `--check`: chỉ xác thực, không ghi. Báo rõ từng câu thiếu field, `gt_video_id`
  không có trong `data/extracted/keyframes/`, hoặc `gt_frame` không trùng keyframe nào.
- [x] **7.3** Danh sách `difficulty_tags` chuẩn (cố định, để breakdown gom nhóm được):
  `small_object` · `similar_distractors` · `short_action` · `temporal_order` · `counting` ·
  `text_in_frame` · `negation` · `local_dialect` · `screen_in_screen` · `chart_reading`.
  `normalize_gt.py --check` cảnh báo khi gặp tag ngoài danh sách.
- [x] **7.4** Test ở `tests/unit/test_normalize_gt.py`: v2 mẫu → v1 đúng schema
  `run_eval._validate_query()` chấp nhận; khẳng định `gt_frame_start == gt_frame_end` khi người
  ghi chỉ nhập một số. Monkeypatch `translate_raw` để test không cần mạng.
- [x] **7.5** Viết lại `EVAL_GUIDE.md`:
  - **Mục mới — quy trình ngược (đề thi → tìm video)**: chiều người dùng sắp làm, hiện chưa có
    dòng nào. Nguồn: `tests/data/*.csv`, `data/extracted/Bo_De_Thi_Dot2/`.
  - Sửa cỡ mẫu: `~50` → bảng đích 140 câu (KIS 80 / QA 30 / TRAKE 30) theo spec §5.4.
  - Nói rõ **`text_en` là biến đối chứng đông cứng**, và giới hạn ở spec §5.3 (KIS luôn chấm trên
    tiếng Anh ⇒ đo bài dễ hơn bài thi thật).
  - Nói rõ **đánh dấu keyframe, không đánh dấu mốc thời gian tuỳ ý** — khoảng không chứa keyframe
    nào thì câu đó vĩnh viễn 0 điểm.
  - **Cảnh báo vòng tròn**: hệ thống/VLM được đề xuất ứng viên, mắt người phải xác nhận. Nhãn do
    AI đoán là nhãn đo lại chính mình.
  - Cách ghi câu **chưa tìm được đáp án** (đề thi có thể trỏ tới video ngoài `L21`–`L30`):
    `"status": "unresolved"`, `normalize_gt.py` bỏ qua, không tính vào mẫu.
  - Danh sách tag chuẩn ở 7.3.
- [x] **7.6** Chạy `normalize_gt.py --check` trên `eval_ground_truth_v2_template.json` có sẵn —
  phải chỉ ra được vấn đề của 5 câu đó mà không crash. Commit.

---

## Task 8 — P2.4 + P2.7 (CHỜ ground truth ~140 câu)

**Files:** tạo `tests/eval/sweep_rerank.py`

⚠️ **Không chạy task này khi ground truth còn < 100 câu KIS.** Trên 38 câu, sai số ±9 điểm % lớn
hơn mức cải thiện định đo — chốt tham số ở đó là tinh chỉnh vào nhiễu.

- [x] **8.1** `sweep_rerank.py`: dùng lại `score_kis()` của `score_pipelines.py` (DRY, không viết
  lại bộ chấm). Chạy một lần retrieval, quét nhiều giá trị tham số trên cùng kết quả đó.
- [x] **8.2** Quét `MARGIN_THRESHOLD` ∈ {-1.0 (luôn spread), 0.004, 0.008, 0.012, 0.020, 0.035,
  1.0 (luôn bet)} → in Final + R@1/R@5/R@20/R@50/R@100 mỗi giá trị.
- [x] **8.3** Quét cách chấm điểm ứng viên đào sâu của `_bet_mode`: giữ nguyên vs. gán theo thứ
  hạng **trong video** thay vì sau toàn pool. In tỷ lệ ứng viên đào sâu thực sự lọt top-100.
- [x] **8.4** **CHỈ IN BẢNG SỐ — không tự chọn giá trị tốt nhất.** Theo tiền lệ
  `test_phase6_margin_sweep.py`. Người dùng đọc bảng rồi quyết.
- [x] **8.5** Ghi bảng vào `docs/reports/phase2_measurement_log.md`. Commit **chỉ harness**,
  chưa đổi tham số nào.

---

## Kết thúc

Sau Task 7 (Task 8 chờ ground truth):

- [x] `pytest tests/unit -q` xanh
- [x] `_smoke_test.py` chạy qua với `AIC_MODE=local`
- [x] Cập nhật `PLAN.md`: tick các mục P2 đã xong; sửa §10.0 (torch CUDA đã sẵn sàng, blocker
  không còn); thêm mục mới "multi_index chạy CPU dù CUDA sẵn sàng"
- [x] Cập nhật `docs/decisions-log.md`: bài học "đừng giả định harness chạm module mình định đo"
  (P2.7 trong PLAN.md sai thước đo) và "fail-soft có thể giấu lỗi hàng ngày" (OCR)
- [x] Hỏi người dùng về 9 file `CLAUDE.md` theo thư mục đang chưa commit
- [x] **REQUIRED SUB-SKILL:** `superpowers:finishing-a-development-branch`
