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
