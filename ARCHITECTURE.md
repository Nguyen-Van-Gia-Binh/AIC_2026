# AIC2026 — Architecture

> Xem [PLAN.md](PLAN.md) cho tiến độ/việc cần làm, [CLAUDE.md](CLAUDE.md) cho quy ước code chung,
> [docs/decisions-log.md](docs/decisions-log.md) cho lý do đằng sau các quyết định dưới đây.
>
> **Đây là kiến trúc mục tiêu cho vòng hiện tại (đợt 4, 04/09/2026)** — mô tả cả phần đã có (baseline
> đợt 1, đã nộp) lẫn phần đang triển khai thêm (6 hạng mục ưu tiên: config mode, risk-aware ranking,
> query rewrite mở rộng, temporal alignment TRAKE, cross-check tầng 3, OCR on-demand). Module nào chưa
> tồn tại trong code được đánh dấu **(mới)**. Kiến trúc round-1 gốc (trước khi có các module mới) đã lưu
> tại [docs/_archive/ARCHITECTURE_Lan1.md](docs/_archive/ARCHITECTURE_Lan1.md).

## 1. Sơ đồ luồng dữ liệu

```
Người dùng (thí sinh)
        │  nhập query trên UI, rà soát/sửa kết quả (human-in-the-loop)
        ▼
frontend/ (React + Vite)  ──HTTP──▶  scripts/api/ (FastAPI, routers: kis|qa|trake|queue|images|videos)
        │
   ┌────┴─────────────────┬──────────────────────┐
   ▼                      ▼                       ▼
pipeline_kis.py     pipeline_qa.py          pipeline_trake.py
(tuyến tính,         (orchestrator,          (2 giai đoạn: retrieve
 rewrite + rank)      tối đa 2 vòng           video → align N mốc
                       reflection)             bằng DP tăng dần
                                                + cross-check tầng 3)
   │                      │                       │
   │                      ▼                       │
   │              agent/tools/answer_qa.py ◄── agent/tools/ocr_read.py (mới)
   │              (objects JSON → OCR hint (mới) → LLM Vision → crosscheck)
   │                      │                       │
   └──────────┬───────────┴───────────┬───────────┘
              ▼                       ▼
   agent/tools/retrieve.py     agent/tools/rewrite.py (đã thêm rule phủ định)
   (CLIP cosine similarity      agent/tools/rerank.py (risk-aware rerank + NMS)
    trên ma trận 177K keyframe) agent/tools/objects_lookup.py (đọc Objects JSON)
              │                 agent/config.py (call_llm() → LiteLLM → PROVIDER_CHAIN,
              │                  + AIC_MODE=test|contest chọn model — mới)
              ▼
        submit/build_submission.py → CSV (kis/qa/trake) → submit/validate_submission.py → zip
```
## 2. Trách nhiệm từng module

> Cập nhật 2026-08-31 sau đợt chuẩn hoá: `scripts/index.py` và `scripts/app.py` đã retire vào
> `docs/_archive/`; `retrieve.py` tách làm 4; `answer_qa.py` tách làm 4; DP của TRAKE tách riêng.

| Path | Vai trò | Vì sao ở đây |
| --- | --- | --- |
| `agent/tools/index_store.py` | Sở hữu ma trận embedding + metadata + text encoder (singleton/tiến trình). `get_index(qa)`, `preload()`, `row_to_hit()`, `key_index()`, `load_model()`, `encode_mean()`. | Một chủ duy nhất cho state; `row_to_hit()` là **điểm duy nhất** quy đổi `frame_id = frame_idx + 1` |
| `agent/tools/retrieve.py` | `fast_retrieve()` (KIS/TRAKE), `fast_retrieve_qa()`, `fast_retrieve_for_video()` (alignment TRAKE), `fast_retrieve_multi()`. | Tầng truy vấn dense thuần, không giữ state |
| `agent/tools/hybrid.py` | `hybrid_retrieve()` (dense + BM25 → RRF), `fast_retrieve_multi_model()`. | Lai ghép nhiều nguồn — mối quan tâm khác với truy vấn dense đơn |
| `agent/tools/frames.py` | `get_neighbor_frames()`, `get_all_frames()`, `get_keyframe_path()`. | Tiện ích cho tầng UI, không phải kết quả truy vấn (không có score) |
| `agent/tools/sparse_index.py` | BM25 offline trên Objects JSON + caption. CLI `--build` (~3,5 phút, bắt buộc 1 lần). | Bù đúng khoảng trống của SigLIP: tên object cụ thể, chữ/số |
| `agent/tools/fusion.py` | RRF thuần: `reciprocal_rank_fusion()`, `rrf_fuse_hits()`. | **Module thuần** — eval và production dùng chung đúng một hàm |
| `agent/tools/temporal_nms.py` | Khử trùng lặp thời gian, thuần. | **Module thuần** (như trên) |
| `agent/tools/query_expand.py` | Multi-Aspect Prompt Expansion, template tất định (+ nhánh LLM tuỳ chọn). | **Module thuần**; mặc định TẮT vì đo thật cho thấy làm tụt điểm |
| `agent/tools/rerank.py` | `apply_risk_aware_ranking()`: đặt cược / trải rủi ro theo margin, + Temporal NMS, + `_preserve_recall_tail()` giữ đuôi danh sách theo thứ tự retrieval gốc. | Cô lập chiến lược phân bổ 100 dòng khỏi retrieval thuần |
| `agent/tools/objects_lookup.py` | Đọc Objects JSON (Faster R-CNN/OpenImages) offline. **KHÔNG phải OCR** — chỉ trả tên object. | Miễn phí; nguồn cross-check cho Q&A và TRAKE. (Tên cũ `ocr_lookup.py` gây hiểu nhầm, đã đổi 2026-08-31) |
| `agent/tools/ocr_read.py` | OCR thật (PaddleOCR + VietOCR), chạy **on-demand** tối đa 3 ảnh; `rerank_by_ocr()`. | Lấp khoảng trống đọc chữ/số. ⚠️ Hiện không hoạt động — xem §5 |
| `agent/tools/asr_lookup.py` | Tra transcript quanh một mốc thời gian. | Tín hiệu phụ miễn phí cho Q&A/TRAKE |
| `agent/tools/rewrite.py` | `rewrite_query()` VN→EN + tối ưu visual-centric qua LLM; `rewrite_query_candidates()` cho UI. | Dùng chung cho Q&A và TRAKE |
| `agent/tools/translate_raw.py` | Dịch thô VN→EN (deep-translator), **không** qua LLM. | Để người dùng đối chiếu bản dịch sát nghĩa với bản rewrite |
| `agent/tools/answer_qa.py` | `answer_from_hits()` — 3 tầng (Objects JSON → Vision + evidence bundle → knowledge fallback) + `_crosscheck_answer()` + OCR Direct Overwrite. | Cô lập logic chống ảo giác — rủi ro lớn nhất của bài Q&A |
| `agent/tools/qa_prompts.py` | 9 prompt template của nhánh Q&A. | Phần sửa nhiều nhất khi tinh chỉnh chất lượng; sửa ở đây LÀ đổi hành vi |
| `agent/tools/qa_classify.py` | Nhận dạng loại câu hỏi: đếm vật thể / cần đọc chữ / hỏi số hiển thị. | Ba nhóm đi ba đường khác nhau trong `answer_from_hits()` |
| `agent/tools/qa_normalize.py` | `canonicalize_answer()`, `is_non_answer()`, `normalize_answer()`, `extract_visual_count()`. | Chấm điểm BTC so khớp chuỗi — câu đúng ý mà bọc trong câu văn vẫn trượt |
| `agent/tools/trake_align.py` | `find_best_increasing_chain()` (quy hoạch động), `rule_plausibility()`. | **Module thuần** — kiểm thử được không cần index/LLM |
| `agent/config.py` | `call_llm()` — bọc LiteLLM, fallback `PROVIDER_CHAIN`, `AIC_MODE=test\|contest`. | Nguồn cấu hình LLM duy nhất |
| `agent/pipeline_kis.py` | `run_kis()` — expand → hybrid_retrieve(pool=500) → risk-aware rank + NMS → rerank_by_ocr. **Không LLM, không loop ⇒ tất định.** | Task đóng, không cần agent (xem §3) |
| `agent/pipeline_qa.py` | `run_qa()` — rewrite → retrieve → rank → answer theo từng cụm video → (confidence thấp) thử vòng 2. | Orchestrator-workers, có gate rõ ràng |
| `agent/pipeline_trake.py` | `run_trake()` — Coverage Pooling → DP đơn điệu → cổng rule (miễn phí) → cổng LLM (chỉ khi #1–#2 sát nhau). | Pipeline cố định; ràng buộc thứ tự do thuật toán đảm bảo, không do LLM tự kiểm |
| `api/` | FastAPI: `main.py`, `schemas.py`, `state.py`, `routers/{kis,qa,trake,queue,images,videos}.py`. | Tầng HTTP; gọi pipeline, không chứa logic retrieval riêng |
| `submit/build_submission.py` | `build_kis_csv/build_qa_csv/build_trake_csv/build_zip_submission`. | Điểm duy nhất sinh format nộp bài |
| `submit/validate_submission.py` | `validate_csv_file()`, `validate_zip()`. | Lưới an toàn cuối trước khi nộp |
| `offline/` | `captions/` · `ocr/` · `shards/` · `analysis/` — chạy một lần, ghi vào `data/`. | Không nằm trên đường truy vấn; tách khỏi runtime để khỏi nhầm |

### 2.1. Tham số đã hiệu chỉnh — và hiệu chỉnh trên thang đo nào

| Tham số | Giá trị | Hiệu chỉnh trên | Ghi chú |
| --- | --- | --- | --- |
| `rerank.MARGIN_THRESHOLD` | 0.012 | cosine của `clip_vitb32` — **model đã retire 2026-08-28** | Thang cosine SigLIP hẹp hơn (~0.05–0.15). Giá trị chưa hiệu chỉnh lại trên thang mới ⇒ xem PLAN.md Pha 2 |
| `rerank.RECALL_HEAD_N` | 20 | 18 câu KIS, 2026-08-31 | Final 0.667 → 0.722 |
| `rerank.BET_VIDEO_SHARE` / `SPREAD_MAX_PER_VIDEO` | 0.5 / 3 | 18 câu KIS | |
| `hybrid.SPARSE_TOP_K` | 50 | 18 câu KIS, 2026-08-28 | Đưa cả 500 ứng viên BM25 vào làm Final tụt 0.667 → 0.656 |
| `temporal_nms.MIN_TIME_GAP` | 3.0 s | bước lấy keyframe BTC (~2,5–3 s) | Thực chất chỉ loại keyframe kề, không loại cảnh trùng dài |
| `fusion.RRF_K` / `W_DENSE` / `W_SPARSE` | 60 / 0.75 / 0.25 | k=60 theo Cormack et al. 2009 | |
| `pipeline_trake.GATE_MARGIN` | 0.02 | chưa có benchmark rộng | |
| `pipeline_qa.MAX_ANSWER_CLUSTERS` | 3 | đánh đổi chi phí/độ phủ | ~97/100 dòng mang answer của video khác ⇒ xem PLAN.md Pha 2 |

## 3. Quyết định kiến trúc đã chốt

- **Không dùng 1 kiến trúc agent chung cho cả 3 dạng bài** — chọn theo độ mở của task
  (nguyên tắc từ `docs/training/AIC2026_TongHop_LuatThi_va_KienTrucAgent.md`, dựa trên
  "Building Effective AI Agents" của Anthropic):
  - **KIS** = workflow tuyến tính, không LLM, có hậu xử lý ranking (`rerank.py`). Task đóng, không cần agent.
    ⚠️ **Kế hoạch ở [§6.4](#64-quyết-định-kiến-trúc-v2) (2026-08-28)** là thêm một bước VLM rerank
    một chiều (`vlm_rerank.py`) cho KIS. **Module này CHƯA tồn tại** (xem PLAN.md 10.4) — tính đến
    2026-08-31, KIS vẫn hoàn toàn không gọi LLM, và đó là lý do golden snapshot của nó tất định.
  - **Q&A** = orchestrator-workers, loop có trần (`MAX_AGENT_LOOPS=2`), có gate confidence rõ ràng.
    Task mở vừa phải (không biết trước câu hỏi cần bao nhiêu tầng info) nhưng rủi ro sai cao
    (trả lời sai answer = R-Score về 0 dù đúng frame) nên **bắt buộc cross-check** trước khi trả lời.
  - **TRAKE** = pipeline 2 giai đoạn cố định (không phải agent tự do), vì thứ tự N mốc đã biết trước;
    ràng buộc thứ tự được đảm bảo bằng thuật toán (DP), không phải bằng LLM tự kiểm tra.
- **1 nguồn cấu hình LLM duy nhất**: `scripts/agent/config.py`. Mọi lời gọi LLM đi qua `call_llm()`,
  không gọi `litellm` trực tiếp ở nơi khác.
- **`AIC_MODE` theo đúng tiền lệ `AIC_RETRIEVE_MODEL`**: env var, mặc định giữ hành vi rẻ/hiện tại
  (`test`), opt-in rõ ràng để đổi sang cấu hình mạnh hơn (`contest`) — không đổi mặc định production
  chỉ vì "chắc tốt hơn", đúng nguyên tắc đã áp dụng cho việc so sánh embedding model ở Phase 6 cũ.
- **Risk-aware ranking dùng margin tương đối, không dùng ngưỡng tuyệt đối**: cosine similarity của
  `clip-ViT-B-32` không nằm gọn trong khoảng dễ đọc như [0,1] theo trực giác — so sánh score giữa các
  video ứng viên với nhau (margin) ổn định hơn là đặt 1 số tuyệt đối "confidence > 0.7".
- **OCR thật (`ocr_read.py`) là tín hiệu phụ, không phải nguồn trả lời**: chỉ chạy on-demand trên tối đa
  3 ảnh/câu hỏi cần đọc chữ, kết quả được chèn vào prompt Vision chứ không tự động trở thành câu trả
  lời — giữ nguyên tầng chống ảo giác (`_crosscheck_answer`) đã có.
- **DP thay greedy cho TRAKE stage 2**: bản greedy cũ (so `frame_idx` với mốc ngay trước) có 2 lỗ hổng
  đã xác nhận khi đọc code (fallback gán cứng `frame_id=1` khi rỗng hit, fallback về hit điểm cao nhất
  bất kể thứ tự khi không có candidate hợp lệ) — DP đảm bảo ràng buộc tăng dần đúng ở mức thuật toán,
  loại thẳng video không có chuỗi hợp lệ thay vì âm thầm trả sai.
- **Anti-hallucination bắt buộc cho Q&A**: mọi answer từ tầng vision phải qua `_crosscheck_answer()`
  đối chiếu với Objects JSON trước khi coi là đáng tin (`confidence` cao/thấp theo kết quả cross-check).
- **File-based, không DB**: toàn bộ state là file (`.npy`/`.csv` index, `tests/**/*.json`,
  `submissions/*.csv|zip`). Hàng đợi submission trong `app.py` chỉ sống trong session Gradio (RAM).
- **frame_id luôn tính từ `frame_idx + 1`** ngay tại `retrieve.py` (điểm duy nhất) — pipeline và UI
  phía sau không tự +1 lần nữa ở đâu khác.
- **Human-in-the-loop là một phần thiết kế, không phải fallback**: `app.py` luôn cho sửa tay
  (dataframe) trước khi add-to-queue, đúng tinh thần luật thi cho phép con người rà soát.

Lý do chi tiết đằng sau từng quyết định (kể cả các quyết định của round-1) → [docs/decisions-log.md](docs/decisions-log.md).

## 4. Không được làm (forbidden)

- Không gọi `litellm` (Gemini/Groq/NVIDIA NIM) trực tiếp bên ngoài `agent/config.py:call_llm()`.
- Không viết CSV/ZIP submission ở đâu khác ngoài `submit/build_submission.py`.
- Không để pipeline (`pipeline_kis/qa/trake.py`) tự thêm `.mp4` hoặc tự trừ/cộng `frame_id` — việc
  quy đổi `frame_id = frame_idx + 1` chỉ xảy ra ở **một hàm duy nhất**:
  `agent/tools/index_store.py:row_to_hit()` (đọc), và `submit/build_submission.py` (ghi).
- Comment/docstring viết tiếng Việt **có dấu** trên toàn bộ `scripts/` (xem `CLAUDE.md`). Ngoại lệ
  duy nhất: nội dung prompt gửi cho LLM (`tools/qa_prompts.py`, `TRAKE_CROSSCHECK_PROMPT`) viết tiếng
  Anh — sửa một ký tự ở đó là đổi hành vi mô hình.
- Không commit `.env` hoặc bất kỳ file nào chứa key thật (chỉ `.env.example` với placeholder được
  commit).
- Không để TRAKE/Q&A pipeline chạy vòng lặp không giới hạn — mọi reflection loop phải có trần cứng
  (hiện là `MAX_AGENT_LOOPS=2`), theo nguyên tắc ACI (giới hạn tool-call loop để kiểm soát cost/latency).
- Không precompute OCR/mô tả VLM cho toàn bộ 177K keyframe (chi phí/thời gian vượt ngân sách) — mọi
  OCR/tín hiệu phụ mới đều phải chạy **on-demand**, chỉ trên candidate đã retrieve.
  ⚠️ **Đã làm rõ ranh giới ở [§6.4](#64-quyết-định-kiến-trúc-v2) (2026-08-28)**: lệnh cấm này nhắm vào
  việc **SINH** nội dung hàng loạt bằng VLM/OCR (vẫn cấm). **ENCODE** văn bản đã có sẵn (caption
  Vintern-1B qua BGE-M3, ~10–15 phút GPU) không thuộc phạm vi cấm.
- Không đổi ngưỡng risk-aware ranking / margin cross-check TRAKE mà không hiệu chỉnh lại bằng
  `tests/eval/run_eval.py` trên `tests/eval/eval_ground_truth.json` trước.

## 5. Điểm giao tiếp (interface)

- **Entry point ứng dụng**: backend `python -m uvicorn scripts.api.main:app --port 8000`
  (health: `http://127.0.0.1:8000/api/health`) + frontend `cd frontend; npm run dev`
  (`http://localhost:5173`, proxy `/api` → `:8000`). Gradio đã retire → `docs/_archive/app_gradio.py`.
- **Entry point pipeline (dùng độc lập/CLI)** — chữ ký không đổi so với round-1:
  - `run_kis(query_text: str, top_k: int = 100) -> list[dict]`
  - `run_qa(query_text: str, question: str | None = None, top_k: int = 100) -> dict`
    (trả `results`, `answer`, `best_hit`, `n_loops`, `confidence`)
  - `run_trake(query_text: str, events: list[str], top_k_video=5, top_k_frame=10) -> dict`
    (trả `results`, `best`, `n_events`)
- **Schema hit chuẩn** (không đổi, mọi module mới phải tôn trọng đúng field này):
  `{video_id, n, frame_idx, frame_id, pts_time, score, jpg_path}`
- **Không có database/API bên ngoài nào khác** ngoài LLM provider (qua LiteLLM) và OCR local
  (PaddleOCR, chạy trên máy, không phải API). Dữ liệu vào là file tĩnh dưới `data/extracted/`.
- **External service**: LLM qua LiteLLM, theo chuỗi fallback `PROVIDER_CHAIN` trong `agent/config.py`.
- ⚠️ **Phụ thuộc ngoài chưa được kiểm soát**: `tools/ocr_read.py` tải config VietOCR từ `vocr.vn`
  lúc chạy. Chứng chỉ SSL của site đã hết hạn (phát hiện 2026-08-31) ⇒ OCR thật hiện KHÔNG hoạt
  động; module bắt lỗi và chạy tiếp nên lỗi này vô hình. Xem PLAN.md Pha 2.
  Key trong `.env` (không commit); provider nào thiếu key sẽ tự bị bỏ qua trong chuỗi.

---

## 6. Kiến trúc v2 (Phase 10 — chốt 2026-08-28)

> Phần này **thay thế** hai quyết định ở §3/§4 (đánh dấu ⚠️ tại chỗ) và bổ sung 4 module mới. Lý do
> đằng sau → [docs/decisions-log.md](docs/decisions-log.md). Việc cần làm → [PLAN.md](PLAN.md) Phase 10.

### 6.1. Ba phát hiện đo được đã dẫn tới v2

**(1) Trần điểm TRAKE ≈ 0.12 — nút thắt không nằm ở thuật toán chọn keyframe.**

Luật BTC (`docs/rules/Thong tin vong So tuyen AIC2026.md` §2.1.3): cửa sổ đáp án của mỗi mốc TRAKE
"thường rất ngắn, thông thường là dưới 10 frame". Đo phân bố khoảng cách keyframe liên tiếp trên
400 video / 90.519 gap của `data/extracted/map-keyframes/`:

| p10 | p25 | trung vị | p75 | p90 | trung bình | tỉ lệ gap ≤ 10 frame |
|-----|-----|----------|-----|-----|------------|----------------------|
| 9   | 34  | **80**   | 150 | 150 | 85,3       | 10,7 %               |

⇒ `P(một keyframe bất kỳ rơi vào cửa sổ 10 frame) ≈ 10 / 85,3 ≈ 12 %`.

Nghĩa là kể cả khi Coverage Pooling chọn đúng video, DP đơn điệu chọn đúng khoảnh khắc ngữ nghĩa và
VLM verify xác nhận đúng, ta vẫn trượt ~88 % số mốc — vì **trong kho keyframe không tồn tại frame nằm
trong cửa sổ đáp án**. Toàn bộ §5 bản đặc tả đang tối ưu hệ số nhân của một trần 0,12.

**(2) `Final Score` biến việc xếp 100 dòng thành bài toán "hạng của cú trúng ĐẦU TIÊN".**

`Final = (1/5)·Σ_{k∈{1,5,20,50,100}} R@k`, `R@k = max` trong k dòng đầu. Nếu dòng đúng duy nhất ở hạng r:

| hạng r | 1 | 2–5 | 6–20 | 21–50 | 51–100 |
|--------|---|-----|------|-------|--------|
| Final  | **1,00** | 0,80 | 0,60 | 0,40 | 0,20 |

Hệ quả: (a) chỉ cú trúng đầu tiên có giá trị — dòng thứ hai của cùng một cảnh đáng ≈ 0; đây mới là
lý luận đúng cho Temporal NMS, không phải "tiết kiệm dung lượng 100 dòng"; (b) 50 dòng cuối cộng lại
đáng 0,2 trong khi kéo một cú trúng từ hạng 6 lên hạng 1 đáng **+0,4** ⇒ **dòng 1–20 phải là 20 giả
thuyết thực sự khác nhau; dòng 21–100 là vé số, không đáng tinh chỉnh**.

**(3) Ngân sách tính toán lớn hơn nhiều so với giả định của bản đặc tả.**

- Máy chạy có **RTX 5050 Laptop, 8151 MiB VRAM, driver 592.82** (Blackwell, sm_120) nhưng venv đang
  cài `torch 2.13.0+cpu` ⇒ GPU chưa từng được dùng. Cần wheel `cu128`/`cu129`.
- Mỗi gói đề chỉ có **~42–45 truy vấn** (`THUNGHIEM-bo-de-thi/bo_de_thi.csv` 42 dòng,
  `tests/data/sotuyen1_bo_de_thi.csv` 45 dòng), và vòng sơ tuyển **chấm offline theo file nộp, không
  giới hạn thời gian chạy**.

Ước lượng khi GPU được bật: định vị dưới keyframe cho TRAKE ~20–30 s/truy vấn; cho KIS ~20 phút/gói
đề; BGE-M3 encode 177K caption ~10–15 phút; encode lại 177K keyframe bằng 1 backbone ~40 phút.

### 6.2. Sơ đồ v2 (chỉ phần khác v1)

```
query ──► [4-leg hybrid retrieval] ─────────────────────────────► pool 500
             ├─ dense ảnh   : siglip / siglip2      (đã có)
             ├─ dense text  : BGE-M3 trên caption   (MỚI, mức frame)
             ├─ sparse BM25 : Objects JSON + OCR    (đã có)
             └─ ASR         : PhoWhisper            (MỚI, mức VIDEO — mọi frame
                                                     của video V thừa hưởng rank_asr(V))
                              │  RRF k=60, 4 số hạng
                              ▼
                      rerank.py (đặt cược / trải rủi ro + temporal NMS)
                              │
                   ┌──────────┴───────────┐
                   ▼                      ▼
        vlm_rerank.py (MỚI)          [Q&A / TRAKE giữ luồng cũ, thêm 3 điểm:]
        Gemini 2.5 Flash Vision       • câu HỎI ghép vào truy vấn retrieval
        chấm top-50, trộn với RRF     • tái xếp hạng frame theo đáp án đã sinh
                   │                  • biến thể đáp án phân bổ trên các dòng
                   ▼
        refine_frame.py (MỚI) ◄── decode .mp4 gốc ở fps thật
        định vị DƯỚI mức keyframe
                   │
                   ▼
        build_submission.py (không đổi)
```

### 6.3. Module mới

| Path | Vai trò | Vì sao ở đây |
|------|---------|--------------|
| **`scripts/agent/tools/refine_frame.py` (mới)** | `refine(video_id, frame_idx_center, query_text, half_window) -> frame_idx`. Decode dải frame gốc từ `data/extracted/video/**/{video_id}.mp4` ở fps thật quanh keyframe đã chọn → encode SigLIP → **làm mượt đường điểm (moving average ~15 frame) rồi lấy TÂM của đoạn liên tục vượt ngưỡng, KHÔNG lấy argmax**. | Gỡ trần 0,12 của TRAKE. Chạy sau khi đã chốt video+keyframe nên chỉ tốn trên 1–3 video ứng viên. Dùng chung cho cả 3 pipeline. |
| **`scripts/agent/tools/vlm_rerank.py` (mới)** | Chấm top-50 ứng viên KIS bằng Gemini 2.5 Flash Vision **qua `config.py:call_llm()`** ("ảnh khớp mô tả tới mức nào, 0–10"), trộn điểm với RRF. | Đòn bẩy R@1 lớn nhất còn lại cho KIS. Đi qua `call_llm()` nên không phá quy tắc §4. Không chiếm VRAM. |
| **`scripts/agent/tools/model_registry.py` (mới)** | Nạp theo yêu cầu / giải phóng model ít dùng nhất + `torch.cuda.empty_cache()` khi thiếu VRAM. Thay pattern singleton "giữ model sống mãi" hiện có ở `retrieve.py`, `vlm_ocr_caption.py`, `ocr_read.py`. | 8 GB VRAM **không chứa nổi** SigLIP (1,7 GB) + SigLIP2 (1,7 GB) + BGE-M3 (1,1 GB) + VietOCR cùng lúc. Không có tầng này thì thêm bất kỳ model nào cũng OOM. |
| **`scripts/agent/tools/text_index.py` (mới)** | Index BGE-M3 trên 177K caption Vintern-1B (mức frame) + trên segment ASR PhoWhisper (mức video). Cấp `rank_caption(d)` và `rank_asr(video)` cho `fusion.py`. | BGE-M3 ra cả dense + sparse từ vựng + ColBERT trong một lần chạy, tiếng Việt tốt; thay được luôn BM25 tự viết trong `sparse_index.py` nếu đo thấy hơn. |

### 6.4. Quyết định kiến trúc v2

- **⚠️ Lật quyết định §3 "KIS = workflow tuyến tính, không LLM".** Lý do ban đầu (kiểm soát
  cost/latency) không còn đúng: vòng sơ tuyển chấm offline không giới hạn thời gian, và mỗi gói đề
  chỉ ~44 truy vấn ⇒ VLM rerank top-50 = ~2.200 lượt chấm ảnh cho cả gói đề. KIS vẫn **không có
  vòng lặp reflection** — chỉ thêm đúng một bước rerank một chiều, có công tắc tắt được.
- **⚠️ Nới quyết định §4 "không precompute cho toàn bộ 177K keyframe".** Lệnh cấm đó nhắm vào việc
  chạy **VLM/OCR sinh nội dung** cho 177K ảnh (vẫn giữ nguyên, vẫn cấm). Encode **văn bản đã có sẵn**
  (caption Vintern-1B) bằng BGE-M3 tốn ~10–15 phút GPU — không thuộc phạm vi lệnh cấm. Ranh giới mới:
  cấm **sinh** nội dung hàng loạt, cho phép **encode** nội dung đã có.
- **`refine_frame` lấy tâm đoạn, không lấy argmax.** Điểm SigLIP trên ~120 frame gần như y hệt nhau
  dao động ngẫu nhiên; argmax rơi vào đỉnh nhiễu ở rìa. Nếu `[s,e]` ngắn thì BTC gần như chắc chắn đặt
  nó quanh tâm ngữ nghĩa của khoảnh khắc; nếu `[s,e]` dài cỡ shot thì tâm đoạn cũng nằm gọn bên trong.
  **Tâm đoạn an toàn ở cả hai giả thuyết về độ dài `[s,e]` của KIS — vốn là ẩn số chưa xác định** (luật
  BTC không định nghĩa cách dựng `[s,e]`; ví dụ minh hoạ trong luật là `[500, 510]`, tức 11 frame).
- **ASR vào RRF như danh sách hạng thứ tư ở mức VIDEO, không phải mức frame.** Lời nói mô tả cả thứ
  không nằm trong khung hình: ASR trả lời "video nào", SigLIP trả lời "frame nào". Xếp hạng video theo
  độ khớp ASR rồi cho mọi frame thuộc video V thừa hưởng hạng đó — vẫn là RRF thuần, không thêm thang
  đo mới cần chuẩn hoá.
- **Độ dài `[s,e]` của KIS chi phối luôn quy tắc đặt cược/trải rủi ro.** Với `p` = P(đúng video),
  `q` = P(frame trúng cửa sổ | đúng video): dồn 5 dòng vào video tốt nhất cho `p·(1−(1−q)⁵)`, rải 5
  video khác nhau cho `Σpᵢ·q`. Cửa sổ ngắn (`q` nhỏ) ⇒ nên **dồn dòng trong video**; cửa sổ dài
  (`q≈1`) ⇒ nên **rải sang nhiều video**. `SPREAD_MAX_PER_VIDEO=3` + NMS `Δt≥3s` hiện tại đang mặc
  định giả thuyết "cửa sổ dài" — tức đang cược một chiều vào ẩn số. `refine_frame` nâng `q` lên, và
  chỉ khi `q` cao thì việc rải mới đúng: **hai tham số này phải chỉnh cùng nhau, không tách rời**.
- **PaddleOCR detection vẫn LUÔN chạy CPU, kể cả sau khi torch chuyển sang bản CUDA.** Xung đột DLL
  `paddlepaddle-gpu` × `torch` trên Windows đã xác nhận (xem [docs/decisions-log.md](docs/decisions-log.md)); torch
  chạy CUDA làm rủi ro này **tăng**, không giảm. VietOCR (thuần torch, dùng chung torch đã import)
  vẫn an toàn trên GPU.
- **Mọi bước v2 đều có công tắc bật/tắt và phải đo trước–sau** bằng Regression Guard đã dựng ở
  Phase 9 (`run_eval.py` tầng 1, `score_pipelines.py --save-baseline` tầng 2) — giữ nguyên nguyên tắc
  của Phase 9, không nới.
