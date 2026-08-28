# AIC2026 — Architecture

> Xem [PLAN.md](PLAN.md) cho tiến độ/việc cần làm, [CLAUDE.md](CLAUDE.md) cho quy ước code chung,
> [DECISION.md](DECISION.md) cho lý do đằng sau các quyết định dưới đây.
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
scripts/app.py  (Gradio, 4 tab: KIS / Q&A / TRAKE / Export)
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
   (CLIP cosine similarity      agent/tools/rank.py (mới — risk-aware rerank)
    trên ma trận 177K keyframe) agent/tools/ocr_lookup.py (đọc Objects JSON, không đổi)
              │                 agent/config.py (call_llm() → LiteLLM → PROVIDER_CHAIN,
              │                  + AIC_MODE=test|contest chọn model — mới)
              ▼
        submit/build_submission.py → CSV (kis/qa/trake) → submit/validate_submission.py → zip
```

## 2. Trách nhiệm từng module

| Path                                                                          | Vai trò                                                                                                                                                                                                                                                                                                                                                            | Vì sao ở đây                                                                                                          |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| [scripts/index.py](scripts/index.py)                                           | **[RETIRED 2026-08-28]** Từng build ma trận CLIP `(N,512)` + metadata từ `clip-features-32/`. Đã retire sau khi benchmark 33 query: `clip_vitb32` Final=0.290 vs `siglip`=0.549. `clip-features-32/` đã xóa. File giữ nguyên để không phá import chain. | Layer dữ liệu gốc — đã retire, không gọi từ production nữa                                                          |
| [scripts/agent/tools/retrieve.py](scripts/agent/tools/retrieve.py)             | Per-task singleton: KIS/TRAKE dùng `siglip` (`features_siglip/`), Q&A dùng `siglip2` (`features_siglip2/`). API: `fast_retrieve()`, `fast_retrieve_for_video()`, `fast_retrieve_qa()` (mới). Escape-hatch: `AIC_RETRIEVE_MODEL` cho KIS/TRAKE, `AIC_QA_MODEL` cho Q&A. `clip_vitb32` đã retire 2026-08-28. | Điểm truy cập duy nhất tới ma trận vector — mọi pipeline đều gọi qua đây, không tự `build_index()` riêng |
| [scripts/agent/config.py](scripts/agent/config.py)                             | `call_llm(...)` — bọc LiteLLM, fallback qua `PROVIDER_CHAIN`. **Thêm (mới):** `AIC_MODE=test\|contest` (mặc định `test`) chọn `OPENROUTER_MODEL` (rẻ, dev) hay `OPENROUTER_MODEL_CONTEST` (mạnh hơn, dùng khi nộp thật) — cùng pattern với `AIC_RETRIEVE_MODEL` (env var, default giữ hành vi cũ, opt-in rõ ràng).                                             | Nguồn cấu hình LLM duy nhất; `AIC_MODE` cho phép tách chi phí dev khỏi chất lượng lúc thi mà không sửa code pipeline |
| **[scripts/agent/tools/rank.py](scripts/agent/tools/rank.py) (mới)**           | `apply_risk_aware_ranking(hits, top_k, query_text)` — hậu xử lý danh sách hit sau `fast_retrieve`: tự tin cao (margin video top-1/top-2 lớn) → đào thêm frame cùng video top-1 qua `fast_retrieve_for_video`, dồn nhiều dòng vào đó; tự tin thấp → áp trần số dòng/video, trải rủi ro ra nhiều video hơn.                                                        | Cô lập logic "đặt cược top-1 vs trải rủi ro" khỏi retrieval thuần — dùng chung được cho KIS lẫn Q&A                  |
| [scripts/agent/tools/rewrite.py](scripts/agent/tools/rewrite.py)               | `rewrite_query(query, feedback=None)` — dịch VN→EN + tối ưu visual-centric cho CLIP, đã có sẵn: chọn 1 khoảnh khắc trọng tâm khi query tả nhiều mốc, giữ nguyên số đếm/màu sắc, đưa "anchor object" lên đầu câu. **Thêm (mới):** 1 rule xử lý phủ định (`"không có"`/`"without"` → mô tả lại thành cái ĐANG hiện diện, vì CLIP khớp mô tả dương tính, không khớp phủ định logic). | Tách riêng khỏi pipeline để dùng chung cho cả Q&A và TRAKE; chỉ thêm đúng phần đang thiếu, không viết lại prompt      |
| [scripts/agent/tools/ocr_lookup.py](scripts/agent/tools/ocr_lookup.py)         | `get_objects()`, `get_objects_for_hits()`, `objects_contain_keywords()` — đọc Objects JSON (Faster R-CNN/OpenImages) offline. **Đây KHÔNG phải OCR thật** (không đọc chữ/số) dù tên module — giữ nguyên tên vì nhiều nơi đã import, không đổi.                                                                                                                    | Không tốn gọi API; nguồn "sự thật" để cross-check answer (Q&A) và cross-check video (TRAKE, mục dưới)            |
| **[scripts/agent/tools/ocr_read.py](scripts/agent/tools/ocr_read.py) (mới)**   | `read_text_from_hits(hits, top_n=3)` — OCR thật (PaddleOCR, singleton nạp 1 lần) chạy **on-demand** chỉ trên tối đa 3 ảnh candidate của câu hỏi đang cần đọc chữ/số (tái dùng regex `_needs_text_reading` đã có trong `answer_qa.py`) — không precompute toàn bộ 177K keyframe.                                                                                 | Lấp khoảng trống: repo chưa từng có OCR thật, chỉ có Gemini Vision "đọc bằng mắt" — OCR làm tín hiệu phụ giảm ảo giác đọc sai số/chữ (bẫy QA-04/05/06) |
| [scripts/agent/tools/answer_qa.py](scripts/agent/tools/answer_qa.py)           | `answer_from_hits()` — 2 tầng (objects JSON → LLM Vision) + `_crosscheck_answer()`. **Thêm (mới):** khi `_needs_text_reading()` đúng, chạy `ocr_read.read_text_from_hits()` trước, chèn kết quả (nếu có) làm gợi ý vào prompt Vision — OCR hỗ trợ, không thay thế lệnh gọi Vision, không đổi shape trả về (`answer, best_hit, confidence, method`). | Cô lập logic chống ảo giác (rủi ro AI-safety lớn nhất của bài Q&A); OCR chỉ là tín hiệu bổ sung, giữ nguyên interface |
| [scripts/agent/pipeline_kis.py](scripts/agent/pipeline_kis.py)                 | `run_kis()` — gọi `fast_retrieve`, **rồi qua `rank.apply_risk_aware_ranking()` (mới)** trước khi trả về. Vẫn không LLM, không loop.                                                                                                                                                                                                                                | KIS không cần agent (xem §3); risk-aware ranking là hậu xử lý thuần, không phá tính chất "linear, no LLM" |
| [scripts/agent/pipeline_qa.py](scripts/agent/pipeline_qa.py)                   | `run_qa()` — orchestrator: rewrite → retrieve → **rank (mới)** → answer → (nếu confidence<0.5) rewrite+feedback → retrieve → rank → answer lại                                                                                                                                                                                                                    | Orchestrator-workers pattern, có gate rõ ràng (không phải free-form agent loop)                                      |
| [scripts/agent/pipeline_trake.py](scripts/agent/pipeline_trake.py)             | `run_trake()` — giai đoạn 1 chọn top-video (không đổi). **Giai đoạn 2 (đổi):** thay ràng buộc tăng dần kiểu tham lam (dễ vỡ khi không có candidate hợp lệ trong top-k) bằng **quy hoạch động** chọn chuỗi `frame_idx` tăng dần nghiêm ngặt có tổng score cao nhất; loại hẳn video không tìm được chuỗi hợp lệ thay vì trả về sai thứ tự. **Thêm (mới) — cross-check tầng 3:** khi margin score giữa video hạng 1/2 nhỏ, dùng `objects_contain_keywords()` (miễn phí, không LLM) đối chiếu object trong frame đã chọn với từ khoá của `events` để phá thế cân bằng. | Structured pipeline cố định, không để LLM tự quyết định số bước; DP đảm bảo đúng ràng buộc "thứ tự tăng dần" mà bản greedy cũ không đảm bảo được |
| [scripts/submit/build_submission.py](scripts/submit/build_submission.py)       | `build_kis_csv/build_qa_csv/build_trake_csv/build_zip_submission`. Không đổi.                                                                                                                                                                                                                                                                                     | Điểm duy nhất sinh format nộp bài — pipeline không tự ghi CSV                                                     |
| [scripts/submit/validate_submission.py](scripts/submit/validate_submission.py) | `validate_csv_file()`, `validate_zip()`. Không đổi.                                                                                                                                                                                                                                                                                                                | Lưới an toàn cuối trước khi nộp; chạy độc lập, không phụ thuộc pipeline                                     |
| [scripts/app.py](scripts/app.py)                                               | Gradio UI — 4 tab, hàng đợi submission trong session, human-in-the-loop edit trước export. Không đổi.                                                                                                                                                                                                                                                              | UI **gọi** pipeline/submit, không chứa logic retrieval/answer riêng                                              |

## 3. Quyết định kiến trúc đã chốt

- **Không dùng 1 kiến trúc agent chung cho cả 3 dạng bài** — chọn theo độ mở của task
  (nguyên tắc từ `docs/Training/AIC2026_TongHop_LuatThi_va_KienTrucAgent.md`, dựa trên
  "Building Effective AI Agents" của Anthropic):
  - **KIS** = workflow tuyến tính, không LLM, có hậu xử lý ranking (rank.py). Task đóng, không cần agent.
    ⚠️ **Đã lật một phần ở [§6.4](#64-quyết-định-kiến-trúc-v2) (2026-08-28)**: KIS được thêm một bước
    VLM rerank một chiều (`vlm_rerank.py`). Phần "không có vòng lặp reflection" vẫn giữ nguyên.
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
- **File-based, không DB**: toàn bộ state là file (`.npy`/`.csv` index, `test_eval/**/*.json`,
  `submissions/*.csv|zip`). Hàng đợi submission trong `app.py` chỉ sống trong session Gradio (RAM).
- **frame_id luôn tính từ `frame_idx + 1`** ngay tại `retrieve.py` (điểm duy nhất) — pipeline và UI
  phía sau không tự +1 lần nữa ở đâu khác.
- **Human-in-the-loop là một phần thiết kế, không phải fallback**: `app.py` luôn cho sửa tay
  (dataframe) trước khi add-to-queue, đúng tinh thần luật thi cho phép con người rà soát.

Lý do chi tiết đằng sau từng quyết định (kể cả các quyết định của round-1) → [DECISION.md](DECISION.md).

## 4. Không được làm (forbidden)

- Không gọi `litellm` (Gemini/Groq/NVIDIA NIM) trực tiếp bên ngoài `agent/config.py:call_llm()`.
- Không viết CSV/ZIP submission ở đâu khác ngoài `submit/build_submission.py`.
- Không để pipeline (`pipeline_kis/qa/trake.py`) tự thêm `.mp4` hoặc tự trừ/cộng `frame_id` — việc
  chuẩn hoá `video_id`/`frame_id` chỉ xảy ra ở `retrieve.py` (đọc) và `build_submission.py` (ghi).
- Không thêm code/comment tiếng Anh vào `scripts/app.py`, `scripts/index.py` — quy ước Vietnamese-only
  của repo (xem `CLAUDE.md`).
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
  `test_eval/Eval/run_eval.py` trên `test_eval/Eval/eval_ground_truth.json` trước.

## 5. Điểm giao tiếp (interface)

- **Entry point ứng dụng**: `scripts/app.py` (Gradio, `python scripts/app.py`, mặc định
  `http://127.0.0.1:7860`).
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
  Key trong `.env` (không commit); provider nào thiếu key sẽ tự bị bỏ qua trong chuỗi.

---

## 6. Kiến trúc v2 (Phase 10 — chốt 2026-08-28)

> Phần này **thay thế** hai quyết định ở §3/§4 (đánh dấu ⚠️ tại chỗ) và bổ sung 4 module mới. Lý do
> đằng sau → [DECISION.md](DECISION.md). Việc cần làm → [PLAN.md](PLAN.md) Phase 10.

### 6.1. Ba phát hiện đo được đã dẫn tới v2

**(1) Trần điểm TRAKE ≈ 0.12 — nút thắt không nằm ở thuật toán chọn keyframe.**

Luật BTC (`docs/Thong tin vong So tuyen AIC2026.md` §2.1.3): cửa sổ đáp án của mỗi mốc TRAKE
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
  `test_eval/sotuyen1_bo_de_thi.csv` 45 dòng), và vòng sơ tuyển **chấm offline theo file nộp, không
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
  `paddlepaddle-gpu` × `torch` trên Windows đã xác nhận (xem [EXPERIMENT.md](EXPERIMENT.md)); torch
  chạy CUDA làm rủi ro này **tăng**, không giảm. VietOCR (thuần torch, dùng chung torch đã import)
  vẫn an toàn trên GPU.
- **Mọi bước v2 đều có công tắc bật/tắt và phải đo trước–sau** bằng Regression Guard đã dựng ở
  Phase 9 (`run_eval.py` tầng 1, `score_pipelines.py --save-baseline` tầng 2) — giữ nguyên nguyên tắc
  của Phase 9, không nới.
