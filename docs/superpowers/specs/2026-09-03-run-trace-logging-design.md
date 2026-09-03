# Thiết kế: Run-trace logging + quy trình xử lý sai

> Ngày: 2026-09-03 · Trạng thái: chờ duyệt · Loại: kiến trúc (subsystem mới)

## 1. Mục tiêu

Hiện `logs/backend_*.log` trộn 3 thứ: request HTTP phục vụ ảnh UI (~90% số dòng, vô giá trị
phân tích), dòng `[uvicorn.access]` trùng lặp 100% với `[api.http]`, và dấu vết pipeline
(`[kis]/[qa]/[trake]`) — thứ duy nhất đáng giữ nhưng bị chìm.

Cần: mỗi câu query sinh **một dấu vết có cấu trúc, gói trong một file**, ghi **ngay lúc chạy**,
đủ để (a) truy ngược vì sao kết quả sai, (b) biết khâu nào chậm, (c) biết mỗi query tốn bao nhiêu
lần gọi LLM, (d) tái hiện / so sánh giữa các lần chỉnh tham số. File phải kéo lẻ gửi qua Zalo
được và người nhận mở ra đọc được mà không cần chạy lại.

Không nằm trong phạm vi: đổi thuật toán pipeline, thêm provider LLM, dashboard web, gửi log lên
dịch vụ ngoài.

## 2. Khái niệm cốt lõi

**1 query = 1 run**, định danh bằng `run_id`:

```
<YYYYMMDD>_<HHMMSS>_<host>_<rand6>
vd: 20260903_182557_binhpc_a1b2c3
```

- `host` = `socket.gethostname()` đã lọc ký tự lạ, cắt 12 ký tự → file bạn bè gửi không đụng tên
  file của mình.
- `rand6` = `secrets.token_hex(3)` → hai run cùng giây trên cùng máy không trùng.

Mỗi run ghi ra 2 file cùng tên:

```
logs/runs/<YYYYMMDD>/<run_id>.json   # cho máy đọc — lọc / thống kê
logs/runs/<YYYYMMDD>/<run_id>.txt    # cho người đọc — toàn bộ câu chuyện 1 query gọn 1 màn hình
logs/runs/incoming/                  # thư mục thả file nhận qua Zalo; script phân tích đọc luôn ở đây
```

`logs/` đã nằm trong `.gitignore` — giữ nguyên, không chia sẻ qua git (workflow Zalo không cần).

## 3. Kiến trúc

### 3.1. Module mới: `scripts/agent/tools/run_trace.py`

Module **thuần** (chỉ import stdlib: `json`, `time`, `secrets`, `socket`, `os`, `contextvars`,
`datetime`, `pathlib`). Không import index / model / LLM / `config.py` → không tạo vòng import.
Đặt ở `tools/` vì cả 3 pipeline dùng chung (đúng bucket, không mở bucket thứ năm).

API:

```python
class RunTrace:
    run_id: str

    def __init__(self, query_type: str, query_text: str, params: dict): ...

    def __enter__(self) -> "RunTrace":      # đặt contextvar "current trace"
    def __exit__(self, *exc):               # gỡ contextvar, ghi 2 file (kể cả khi có exception)

    def stage(self, name: str):             # context manager: đo ms + ok/lỗi của 1 khâu
    def record(self, section: str, data):   # gắn dữ liệu có cấu trúc: "retrieval", "rerank", "qa", "trake"
    def add_llm_call(self, **fields):       # 1 bản ghi gọi LLM (config.call_llm gọi hàm này)
    def add_error(self, stage, exc, fallback=None):
    def set_result(self, video_id=None, frame_ids=None, answer=None): ...

def current_trace() -> "RunTrace | None":   # đọc contextvar; config.py dùng để tự gắn llm_call
def tracing_enabled() -> bool:              # False nếu env AIC_TRACE=0 hoặc đang chạy dưới pytest
```

- Khi `tracing_enabled()` là `False`: `RunTrace` thành no-op, **không ghi file** → giữ
  `tests/e2e/golden_kis_snapshot.py --check` và `tests/unit` tất định, hermetic.
- `contextvars` (không phải biến global) → an toàn với các request đồng thời của uvicorn.

### 3.2. Điểm sửa

| File | Sửa gì | Ràng buộc |
|---|---|---|
| `scripts/agent/tools/run_trace.py` | **mới** — class `RunTrace` + helpers ở trên | thuần, chỉ stdlib |
| `scripts/agent/config.py` `call_llm()` | thêm kwarg `purpose: str = "unknown"`; sau mỗi `_call_one` thành công/thất bại, nếu `current_trace()` khác `None` thì `trace.add_llm_call(purpose=..., model=..., key_index=..., ms=..., response=<cắt 300 ký tự>)` | **vẫn là điểm gọi LLM duy nhất** — không đụng chỗ khác; kwarg mới có default nên không phá caller cũ |
| `scripts/agent/pipeline_kis.py` `run_kis()` | bọc thân hàm trong `with RunTrace("kis", query_text, params) as trace:`; `trace.record("retrieval", …)` sau hybrid, `trace.record("rerank", …)` sau risk-aware ranking + OCR rerank; `trace.set_result(...)` cuối | **không đổi giá trị trả về** (list[dict] giữ nguyên) |
| `scripts/agent/pipeline_qa.py` | như trên; khâu: `rewrite`, `retrieve`, `rank`, `answer`, `crosscheck`, `normalize`; `trace.record("qa", {rewrite, tier, evidence_source, answer_raw, normalized, crosscheck})` | |
| `scripts/agent/pipeline_trake.py` | như trên; khâu: `parse_events`, `global_query`, `per_event_query`, `video_candidates`, `align`, `llm_gate`, `finalize`; `trace.record("trake", {events, global_query, event_queries, video_candidates, alignment})` | prompt crosscheck tiếng Anh **giữ nguyên** |
| `scripts/api/routers/kis.py` `qa.py` `trake.py` | thêm `run_id` vào response JSON (để frontend hiện được) | pipeline trả kèm `run_id`; giữ tương thích — thêm field, không bỏ field |
| `scripts/api/main.py` middleware | chỉ log `[REQ]/[RES]` khi path bắt đầu bằng `/api/kis`, `/api/qa`, `/api/trake`, `/api/queue`, `/api/rewrite` **HOẶC** status ≥ 400 **HOẶC** thời gian > 1000ms; còn lại im lặng | route lỗi vẫn phải log |
| `scripts/api/logging_config.py` | `logging.getLogger("uvicorn.access").propagate = False` (nội dung trùng `api.http`); mở rộng `cleanup_old_logs` để xoá thư mục `logs/runs/<ngày>/` cũ hơn `max_sessions` ngày | giữ `uvicorn.error` |

### 3.3. Tên khâu chuẩn (để script phân tích ổn định)

- **KIS**: `expand` (tùy chọn) · `retrieve` · `rank` · `ocr_rerank` (tùy chọn)
- **QA**: `rewrite` · `retrieve` · `rank` · `answer` · `crosscheck` · `normalize`
- **TRAKE**: `parse_events` · `global_query` · `per_event_query` · `video_candidates` · `align` ·
  `llm_gate` (tùy chọn) · `finalize`

## 4. Schema file JSON (`schema_version: 1`)

```json
{
  "run_id": "20260903_182557_binhpc_a1b2c3",
  "schema_version": 1,
  "created_at": "2026-09-03T18:25:57+07:00",
  "host": "binhpc",
  "aic_mode": "test",
  "query_type": "trake",
  "query_text": "Cắt nấm, củ năng, đậu hũ rồi bật bếp",
  "params": {"top_k": 100, "use_hybrid": true, "use_nms": true, "backbone": "siglip"},

  "stages": [
    {"name": "retrieve", "ms": 812.4, "ok": true},
    {"name": "align", "ms": 41.0, "ok": true},
    {"name": "llm_gate", "ms": 3100.0, "ok": true}
  ],

  "retrieval": {
    "backbone": "siglip",
    "pool_size": 500,
    "candidates": [
      {"rank": 1, "video_id": "L26_V214", "frame_id": 2433, "score": 0.2841, "dense": 0.27, "bm25": 0.10}
    ]
  },

  "rerank": {
    "margin_top2": 0.0122,
    "gate_threshold": 0.02,
    "gate_opened": true,
    "penalties": [{"video_id": "L26_V230", "reason": "spread_per_video", "delta": -0.03}],
    "final": [{"rank": 1, "video_id": "L26_V214", "frame_id": 2433, "score": 0.18}]
  },

  "llm_calls": [
    {"seq": 1, "purpose": "trake_event_rewrite", "model": "gemini/gemini-3.5-flash-lite",
     "key_index": "3/28", "ms": 640, "candidate": null, "prompt_chars": 512,
     "response": "A knife slicing fresh mushrooms on a cutting board close up"}
  ],

  "qa": null,
  "trake": {
    "events": ["Khoảnh khắc đầu tiên thấy cắt nấm", "..."],
    "global_query": "Fresh mushrooms on a cutting board in a kitchen",
    "event_queries": ["A knife slicing fresh mushrooms...", "..."],
    "video_candidates": ["L26_V214", "L26_V230", "L26_V497"],
    "alignment": {"video_id": "L26_V214", "frame_ids": [2433, 2547, 2561, 2817], "dp_score": 0.134}
  },

  "result": {"video_id": "L26_V214", "frame_ids": [2433, 2547, 2561, 2817], "answer": null},

  "totals": {
    "wall_ms": 9800,
    "llm_calls": 12,
    "llm_ms": 7200,
    "llm_by_model": {"gemini/gemini-3.5-flash-lite": 12}
  },

  "errors": [
    {"stage": "answer", "type": "TimeoutError", "message": "...", "fallback": "tier2->tier3"}
  ]
}
```

Quy tắc:
- `qa` **hoặc** `trake` có giá trị, cái còn lại `null` (KIS thì cả hai `null`).
- `retrieval.candidates`: giữ **top 20**. `rerank.final`: giữ **top 10**.
- `llm_calls[].response`: cắt còn 300 ký tự (đủ để nhìn LLM nói gì, không phình file).
- `errors`: rỗng nếu không lỗi. Có exception giữa chừng vẫn ghi file (trong `__exit__`).

### File `.txt` (bản tóm tắt người đọc)

```
run_id : 20260903_182557_binhpc_a1b2c3
type   : TRAKE      mode=test    wall=9.8s   llm=12 calls / 7.2s
query  : "Cắt nấm, củ năng, đậu hũ rồi bật bếp"

[stages]  retrieve 812ms · align 41ms · llm_gate 3100ms · finalize 12ms
[trake]   events=4  candidates=[L26_V214, L26_V230, L26_V497]
          margin #1-#2 = 0.0122 <= 0.02  -> LLM gate OPENED
          L26_V214  trake=0.134 rule=0.12 llm=0.85 -> 0.180   <-- chosen
          L26_V230  trake=0.120 rule=0.09 llm=0.15 -> 0.130
[result]  video=L26_V214  frames=[2433, 2547, 2561, 2817]
[errors]  none
```

## 5. Quy trình xử lý sai (dùng chính đống trace này)

Không phải module. Là checklist truy ngược:

**Bước 0 — Lấy run.** `run_id` in ở cuối response API và dòng đầu file `.txt`. File bạn bè gửi:
bỏ vào `logs/runs/incoming/`.

**Bước 1 — Phân loại lỗi** (kết quả cuối vs kỳ vọng):

| Triệu chứng | Nghi khâu |
|---|---|
| Sai hẳn video | `retrieve` / `rewrite` |
| Đúng video, sai frame | `rank` / `align` |
| KIS đúng, `answer` sai | `answer` / nguồn bằng chứng |
| Kết quả rỗng hoặc exception | `errors[]` / nhánh fallback |

**Bước 2 — Đi ngược pipeline**, đọc thẳng field JSON:

| Khâu | Field | "Thủ phạm" khi… | "Ổn, đi tiếp" khi… |
|---|---|---|---|
| `rewrite` | `qa.rewrite` / `trake.event_queries` | bản EN sai nghĩa / mất chi tiết chính | câu EN giữ đúng ý |
| `retrieve` | `retrieval.candidates[]` | đáp án đúng **không có** trong top 20; điểm top thấp & sát nhau | đáp án đúng có trong top 20 nhưng tụt hạng |
| `rank` | `rerank.margin_top2`, `rerank.gate_opened`, `rerank.penalties` | đáp án đúng bị phạt/tụt; cổng LLM không mở dù margin sát ngưỡng | thứ hạng đổi hợp lý |
| LLM | `llm_calls[].purpose/candidate/response` | LLM chấm ngược (đúng → điểm thấp); response cho thấy prompt thiếu ngữ cảnh | điểm LLM khớp trực giác |
| `answer` | `qa.tier`, `qa.evidence_source`, `qa.answer_raw`, `qa.normalized` | tier chọn nhầm nguồn; chuẩn hoá bóp méo đáp án | bằng chứng + chuẩn hoá đều đúng |

**Bước 3 — Ghi lại.** Một dòng vào `docs/decisions-log.md`: query + `run_id` + khâu lỗi + giả
thuyết nguyên nhân.

## 6. Script phân tích (tùy chọn, Phase 3)

`scripts/offline/analysis/scan_runs.py` — đọc `logs/runs/**/*.json` (+ `incoming/`), in bảng:
câu tốn nhiều LLM nhất, khâu chậm nhất trung bình, tỉ lệ mở cổng LLM, tỉ lệ kết quả rỗng.
Chạy tay, không nằm trên đường query. Đúng bucket `scripts/offline/analysis/`.

## 7. Kế hoạch theo pha (mỗi pha ship độc lập)

1. **Phase 1 — lõi.** `run_trace.py` + nối vào 3 pipeline + `config.call_llm()` + unit test.
   Đây là phần mang lại giá trị chính.
2. **Phase 2 — giảm nhiễu.** Lọc middleware `main.py` + tắt propagate `uvicorn.access` +
   prune `logs/runs/` trong `cleanup_old_logs`.
3. **Phase 3 — tổng hợp.** `scan_runs.py`.
4. **Phase 4 — UI.** Frontend hiện `run_id` + link tải file `.txt`/`.json` của run vừa chạy.

## 8. Kiểm thử

- `tests/unit/test_run_trace.py` — `RunTrace` dựng đúng dict; ghi cả 2 file; `run_id` không
  trùng qua 1000 lần tạo; no-op khi `AIC_TRACE=0`; `current_trace()` trả `None` ngoài `with`.
- `tests/e2e/golden_kis_snapshot.py --check` — **phải khớp y hệt** sau khi nối trace vào
  `run_kis` (trace không đổi giá trị trả về; ghi file bị tắt dưới pytest).
- `scripts/api/_smoke_test.py` — sau 1 lượt KIS + QA + TRAKE, có đúng 3 file `logs/runs/<ngày>/*.json`
  với các key ở §4.

## 9. Rủi ro / đánh đổi

- **`config.py` phải biết `run_trace`.** Chấp nhận: `run_trace` thuần stdlib, không import ngược
  → không vòng. Nếu sau này thành vấn đề, đổi sang inject `trace` qua tham số thay vì contextvar.
- **Quên gọi `trace.record()` ở một khâu** → khâu đó trống trong JSON. Giảm thiểu bằng việc
  `stage()` luôn ghi được ms/ok kể cả khi quên `record()` dữ liệu chi tiết.
- **File `.txt` phình theo số event TRAKE.** Chấp nhận — vẫn 1 màn hình cho ≤ 10 event.
