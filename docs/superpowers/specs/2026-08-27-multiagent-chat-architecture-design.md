# Multi-Agent Chat Architecture — Design Spec (vòng sau)

> **Phạm vi:** Đây là kiến trúc định hướng cho **vòng thi sau** — không thuộc phạm vi Phase 1–6 của
> [PLAN.md](../../../PLAN.md), không cần fit vào deadline freeze 03/09/2026 / nộp 04/09/2026 của đợt
> hiện tại. Không implement gì từ spec này trước khi đợt 4 kết thúc, trừ khi người dùng nói rõ ngược lại.
>
> **Quan hệ với quyết định đã chốt:** [ARCHITECTURE.md](../../../ARCHITECTURE.md) §3 hiện chốt "không
> dùng 1 kiến trúc agent chung cho cả 3 dạng bài, chọn theo độ mở của task". Spec này **không phá**
> nguyên tắc đó — nó thêm 1 lớp orchestration (router hội thoại) *phía trên* 3 pipeline hiện có, nhưng
> mỗi pipeline con (KIS/QA/TRAKE) bên trong graph vẫn giữ đúng mức độ mở đã chốt (KIS không LLM, QA có
> trần loop, TRAKE dùng DP chứ không để LLM tự quyết định thứ tự). Khi nào round sau thực sự bắt đầu,
> quyết định §3 cần được cập nhật để phản ánh lớp orchestration mới này.

## 1. Bối cảnh & động lực

Đợt 1 đạt 5.6/10, sai chủ yếu ở Q&A/TRAKE. Người dùng muốn cho vòng sau:

1. **Nâng độ chính xác** bằng các sub-agent chuyên biệt (tìm / phản biện-verify / tổng hợp) thay vì
   1 hàm gộp nhiều việc như `answer_from_hits()` hiện tại.
2. **Xử lý câu hỏi mở/nhiều bước** — hệ thống tự quyết định cần tra thêm gì (OCR, objects JSON, video
   khác, retrieve lại) thay vì luồng cố định.
3. **Giao diện hội thoại kiểu ChatGPT** — nhận query thô, tự chọn pipeline/tool, hỏi lại khi cần, thay
   vì người dùng tự chọn tab KIS/QA/TRAKE.

Đã cân nhắc 3 hướng (A: thin router tái dùng nguyên trạng; B: layered multi-agent graph; C: agentic tự
do hoàn toàn). **Chọn hướng B** — vì C lặp lại đúng rủi ro đã né ở §3 (LLM tự quyết định thứ tự TRAKE,
tăng rủi ro cạn quota — nguyên nhân chính khiến đợt 1 mất điểm, xem [EXPERIMENT.md](../../../EXPERIMENT.md)),
còn A không đáp ứng đủ 2 mục tiêu đầu.

## 2. Kiến trúc tổng thể

### 2.1 Topology (2 tầng vật lý: Frontend ↔ Backend; AI là module logic bên trong Backend)

```
Frontend #1 (Gradio, hiện tại)  ─┐
Frontend #2 (tương lai, chưa xác định) ─┤──HTTP/JSON──►  Backend API (FastAPI, mới)
                                  ┘                          │
                                                    ┌─────────┴─────────┐
                                                AI/graph            tools/ + submit/
                                            (agent/graph/,          (agent/tools/,
                                             LangGraph, mới)         scripts/submit/, không đổi)
```

Lý do 2 tầng chứ không phải 3: AI (graph) và backend logic (`tools/`, `submit/`) đều là Python chạy
phía server — tách thành 2 service mạng riêng chỉ tốn thêm 1 network hop + serialize state mỗi lần gọi,
không ai cần scale AI độc lập với backend. Ranh giới vật lý cần thiết duy nhất là frontend ↔ backend,
vì đó là nơi sẽ có nhiều client (Gradio + frontend tương lai) cùng gọi vào.

### 2.2 Graph runtime

**LangGraph (chỉ package core, không cần full LangChain)** — không ép LLM client riêng, mỗi node vẫn
gọi thẳng `call_llm()` hiện có (giữ đúng rule "1 nơi gọi LLM" của CLAUDE.md). `recursion_limit` của graph
thay thế/mở rộng cơ chế `MAX_AGENT_LOOPS` đang dùng.

### 2.3 Cấu trúc graph

```
User message
     │
     ▼
[Router node]  ── LLM (call_llm) phân loại: KIS / QA / TRAKE / cần hỏi lại / tiếp nối lượt trước
     │
     ├── KIS ─────► [KIS node] (rewrite? → retrieve → rank → propose)
     │
     ├── QA ──────► [QA subgraph]
     │                 retrieve → rank → answer (vision) → critic/crosscheck
     │                    ▲                                      │
     │                    └── loop nếu confidence thấp & loop_count < cap ┘
     │
     ├── TRAKE ───► [TRAKE subgraph]
     │                 chọn video ứng viên → DP align (giữ nguyên thuật toán)
     │                    → crosscheck tầng 3 (khi margin nhỏ)
     │
     └── Không rõ ─► [Clarify node] → hỏi lại user qua chat, KHÔNG đoán bừa
                             │
                             ▼
                     [Propose node] → trả lời chat + điền dòng vào bảng review
                             │
                             ▼
              (Human review, bắt buộc) → build_submission.py (không đổi)
```

### 2.4 Mapping node → code hiện có (không viết lại thuật toán lõi nào)

| Node | Gọi lại đúng hàm hiện có |
|---|---|
| Router | LLM mới (prompt phân loại), qua `call_llm()` |
| KIS node | `retrieve.py:fast_retrieve` + `rerank.py:apply_risk_aware_ranking` |
| QA subgraph | `rewrite.py`, `retrieve.py`, `rerank.py`, `answer_qa.py:answer_from_hits` (kể cả `_crosscheck_answer` hiện có — giờ là 1 node riêng, có chỗ nâng cấp thành agent phản biện mạnh hơn sau này mà không đụng `answer_qa.py`) |
| TRAKE subgraph | DP align (Phase 4, `pipeline_trake.py`), cross-check tầng 3 (`ocr_lookup.py:objects_contain_keywords`) |

## 3. Backend API (FastAPI — dependency mới)

- `POST /chat/{session_id}/message` — 1 lượt hội thoại: Router → subgraph → Propose, trả draft
  answer/row. **MVP: đồng bộ** (trả 1 lần khi xong) — chưa streaming (SSE/WebSocket là fast-follow sau
  khi graph chạy ổn, YAGNI cho bản đầu).
- `GET /queue/{session_id}` / `POST /queue/{session_id}/add` / `DELETE /queue/{session_id}/{row_id}` —
  thao tác bảng review, thay cho biến Python nội bộ trong `app.py` hiện tại.
- `POST /export/{session_id}` — gọi `build_submission.py`, trả file zip.
- `POST /kis|qa|trake/run` — REST tương đương `run_kis/run_qa/run_trake`, giữ cho tab cũ hoạt động qua
  API thay vì gọi hàm in-process.

**Session state:** `session_id` (UUID) do frontend giữ (cookie/localStorage), backend lưu state theo
session **trong RAM** (dict) — chưa cần DB (không có yêu cầu nhiều người dùng chung 1 backend). Nếu sau
này cần persist qua restart server thì thêm SQLite nhẹ lúc đó, không làm trước khi cần.

## 4. Đa lượt hội thoại & Human-review gate

- State phiên giữ: lịch sử tin nhắn, `task_type` lượt trước, `hits`/draft answer lượt trước,
  `loop_count`.
- Follow-up (vd "video đó sai, tìm lại với video khác") → Router nhận diện là **tiếp nối** lượt trước
  (không phân loại lại từ đầu) → quay lại đúng subgraph cũ kèm feedback, tái dùng `feedback` param đã
  có sẵn trong `rewrite_query(query, feedback=...)` — không cần API mới.
- **Human-review gate không đổi:** `Propose node` chỉ điền vào bảng review có thể sửa tay (cùng loại
  dataframe các tab khác đang dùng) → user bấm "Thêm vào queue" (nút có sẵn) → `Export` vẫn là nơi duy
  nhất gọi `build_submission.py`. Graph không bao giờ tự ghi CSV/ZIP hay tự add-to-queue.
- Chat UI sống trong 1 tab mới ("Chat") của `app.py`, **thêm vào** bên cạnh KIS/Q&A/TRAKE/Export hiện
  có, không thay thế — các tab cũ vẫn hữu ích để thao tác trực tiếp/gỡ lỗi.

## 5. Error handling

- **Loop cap 2 lớp:** cap trong từng subgraph (QA reflection, giữ `MAX_AGENT_LOOPS=2`) + cap tổng số
  node đi qua trong 1 lượt (`recursion_limit` của graph).
- **LLM lỗi/hết quota:** không đổi, vẫn qua `PROVIDER_CHAIN` fallback trong `call_llm()`. **Rủi ro mới
  cần lưu ý:** Router thêm 1 lượt gọi LLM mỗi tin nhắn → tổng quota tiêu thụ/phiên tăng so với hiện tại
  (bài học đợt 1: cạn quota Gemini là nguyên nhân chính mất điểm, xem EXPERIMENT.md) → nên hiển thị cảnh
  báo quota còn lại ngay trong tab Chat.
- **Phân loại không chắc:** Router confidence thấp → nhánh `Clarify`, hỏi lại user qua chat thay vì
  đoán bừa.
- **Exception trong node bất kỳ:** bắt ở biên `Propose node`, hiển thị bong bóng chat `⚠️ ...` ngắn gọn
  — đúng convention hiện có (không để callback crash cả phiên).

## 6. Testing & Verification

Repo hiện tại không có test runner (script ad-hoc + assert/print, theo CLAUDE.md). **Riêng mảng API/
graph mới này dùng `pytest`** (đã được người dùng xác nhận) — số case (router/endpoint/multi-turn) nhiều
hơn mức ad-hoc còn dễ quản lý; phần code cũ không đổi quy ước.

1. **Router classification** — bộ câu test (KIS-dạng/QA-dạng/TRAKE-dạng/mơ hồ/follow-up) → assert
   đúng nhánh. Phần hoàn toàn mới, chưa có ground truth sẵn — cần viết mới.
2. **Thuật toán lõi trong từng node — không test lại**: DP-TRAKE, `apply_risk_aware_ranking`,
   `answer_from_hits` đã có benchmark/self-test riêng (Phase 3/4); node chỉ gọi lại nguyên hàm.
3. **API contract** — FastAPI `TestClient` (in-process): request/response shape từng endpoint, session
   state persist đúng giữa các lệnh gọi (`/chat` → `/queue` → `/export`).
4. **Kịch bản đa lượt (end-to-end)** — mô phỏng hội thoại ngắn (câu hỏi đầu → follow-up) → xác nhận
   state mang đúng sang lượt sau, feedback loop hoạt động.
5. **Error handling** — ép recursion cap, ép LLM lỗi (fallback qua lớp API vẫn chạy đúng), câu mơ hồ
   phải rơi vào `Clarify`.
6. **Parity check (quan trọng nhất):** so R@k khi gọi qua graph/API với R@k khi gọi trực tiếp
   `run_kis`/`run_qa` (benchmark cũ `scripts/test_phase3_rerank.py`) trên cùng `eval_ground_truth.json`
   — đảm bảo lớp orchestration mới không làm sai lệch kết quả so với pipeline gốc.

## 7. Dependency mới cần thêm

- `langgraph` (core only) — graph runtime cho AI layer.
- `fastapi` (+ `uvicorn` để chạy server) — backend API.
- `pytest` — riêng cho test mảng API/graph mới, không áp dụng ngược cho code cũ.

## 8. Ngoài phạm vi / chưa quyết (open questions cho round sau)

- Frontend #2 (thay/thêm Gradio) — chưa xác định cụ thể là gì, chỉ biết sẽ có.
- Streaming chat response (SSE/WebSocket) — fast-follow sau khi bản đồng bộ chạy ổn định.
- Persist session qua DB (SQLite) — chỉ làm nếu nhu cầu thực tế xuất hiện (vd cần nhiều người dùng
  chung 1 backend), không làm trước.
- Ngưỡng/threshold cụ thể cho Router confidence (khi nào vào `Clarify` thay vì đoán) — cần tinh chỉnh
  bằng dữ liệu thật, giống cách `MARGIN_THRESHOLD` ở Phase 3 đã làm — không đoán trước khi có benchmark.
- Cập nhật `ARCHITECTURE.md` §3 để phản ánh lớp orchestration mới — làm khi round sau chính thức bắt
  đầu, không phải lúc viết spec này.
