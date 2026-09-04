# Kế hoạch sửa lỗi kết nối query_en cho màn hình Q&A và TRAKE

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục lỗi kết nối khiến hai nút "Gợi ý câu truy vấn" và "Dịch thô" trên màn hình Q&A và TRAKE bị vô dụng: khi người dùng chọn chip tiếng Anh (hoặc chủ động điền câu tiếng Anh), frontend sẽ gửi `query_en` lên backend để bỏ qua bước LLM rewrite ngầm vòng 1, vừa tăng tốc 2–4s vừa bảo toàn nguyên vẹn từ khóa đã chọn.

**Architecture:** 
Backend API (`/api/qa/run` và `/api/trake/run`) và `client.ts` đã có sẵn tham số `query_en: str | None = None`. 
Tại frontend (`QaScreen.tsx` và `TrakeScreen.tsx`), bổ sung state điều khiển `skipRewrite` (tự động bật khi người dùng click chọn 1 chip gợi ý/dịch thô, hoặc người dùng có thể tự tích chọn). Khi ấn Run, nếu cờ này bật, chuỗi tiếng Anh trong ô input sẽ được truyền qua tham số `query_en` vào `api.qaRun` / `api.trakeRun`. Backend nhận diện `query_en` có sẵn và bỏ qua bước `rewrite_query` bằng LLM ở vòng 1.

**Tech Stack:** React 19, TypeScript, Vite, CSS, FastAPI, Pytest.

**Spec:** Quyết định kiến trúc trong `ARCHITECTURE.md` §2 và `scripts/agent/pipeline_qa.py` (vòng 1: `if query_en: dùng query_en có sẵn (bỏ qua rewrite)`).

## Global Constraints

- `pytest tests/unit -q` phải pass toàn bộ.
- `npm run build` trong thư mục `frontend/` (`tsc -b && vite build`) phải biên dịch thành công 0 lỗi.
- Comment/UI text bằng tiếng Việt có dấu theo quy ước toàn repo (GEMINI.md).
- Không thêm dependency mới ngoài các thư viện đã có.
- Không sửa đổi logic scoring hay phá vỡ các contract API hiện hành.

---

### Task 1: Thêm Unit Test cho Router QA và TRAKE nhận `query_en`

**Files:**
- Create: `tests/unit/test_api_qa_trake_query_en.py`

**Interfaces:**
- Consumes: `scripts.api.main:app`, `fastapi.testclient.TestClient`
- Produces: Test suite kiểm tra `POST /api/qa/run` và `POST /api/trake/run` truyền `query_en` chính xác xuống `run_qa` và `run_trake`.

- [ ] **Step 1: Viết test kiểm tra router truyền `query_en`**

Tạo file `tests/unit/test_api_qa_trake_query_en.py`:
```python
"""Kiểm tra router /api/qa/run và /api/trake/run truyền đúng tham số query_en xuống pipeline."""
from __future__ import annotations

from fastapi.testclient import TestClient
from scripts.api.main import app
from scripts.api.routers import qa as qa_router
from scripts.api.routers import trake as trake_router


def test_qa_run_passes_query_en(monkeypatch) -> None:
    captured: dict = {}

    def _fake_run_qa(query_text, question=None, top_k=100, query_en=None, use_hybrid=True, trace=None):
        captured["query_text"] = query_text
        captured["question"] = question
        captured["top_k"] = top_k
        captured["query_en"] = query_en
        return {
            "results": [{"video_id": "L21_V001", "frame_id": 1, "frame_idx": 0, "pts_time": 0.0, "score": 0.9, "answer": "test"}],
            "answer": "test",
            "confidence": 0.95,
            "n_loops": 1,
        }

    monkeypatch.setattr(qa_router, "run_qa", _fake_run_qa)

    client = TestClient(app)
    # 1. Trường hợp có query_en
    res = client.post("/api/qa/run", json={
        "query": "người mặc áo đỏ",
        "question": "ai mặc áo đỏ?",
        "top_k": 10,
        "query_en": "a person wearing a red shirt",
    })
    assert res.status_code == 200, res.text
    assert captured["query_en"] == "a person wearing a red shirt"
    assert captured["query_text"] == "người mặc áo đỏ"

    # 2. Trường hợp không truyền query_en (mặc định None)
    res2 = client.post("/api/qa/run", json={
        "query": "người mặc áo đỏ",
        "question": "ai mặc áo đỏ?",
        "top_k": 10,
    })
    assert res2.status_code == 200, res2.text
    assert captured["query_en"] is None


def test_trake_run_passes_query_en(monkeypatch) -> None:
    captured: dict = {}

    def _fake_run_trake(query_text, events, top_k_video=5, top_k_frame=10, query_en=None, trace=None, strict_monotonic=True):
        captured["query_text"] = query_text
        captured["events"] = events
        captured["top_k_video"] = top_k_video
        captured["query_en"] = query_en
        return {
            "results": [{"video_id": "L21_V001", "frame_ids": [1, 2], "score": 0.85}],
            "n_events": len(events),
        }

    monkeypatch.setattr(trake_router, "run_trake", _fake_run_trake)

    client = TestClient(app)
    # 1. Có query_en
    res = client.post("/api/trake/run", json={
        "query": "lễ hội xe hoa",
        "events": ["xe hoa xuất phát", "pháo hoa"],
        "top_k_video": 3,
        "query_en": "parade with flower float and fireworks",
    })
    assert res.status_code == 200, res.text
    assert captured["query_en"] == "parade with flower float and fireworks"

    # 2. Không truyền query_en
    res2 = client.post("/api/trake/run", json={
        "query": "lễ hội xe hoa",
        "events": ["xe hoa xuất phát", "pháo hoa"],
        "top_k_video": 3,
    })
    assert res2.status_code == 200, res2.text
    assert captured["query_en"] is None
```

- [ ] **Step 2: Chạy pytest kiểm tra test router**

Chạy lệnh:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_api_qa_trake_query_en.py -v
```
Kỳ vọng: PASS (vì router và schema backend đã hỗ trợ sẵn tham số này).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_api_qa_trake_query_en.py
git commit -m "test(api): verify qa_run and trake_run pass query_en to pipeline"
```

---

### Task 2: Cập nhật `QaScreen.tsx` — Kết nối chọn chip và truyền `query_en`

**Files:**
- Modify: `frontend/src/screens/QaScreen.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: `api.qaRun(query, question, topK, queryEn)`
- Produces: Giao diện QA cho phép tự động hoặc chủ động bật `skipRewrite`, truyền `query_en` khi người dùng chọn chip tiếng Anh.

- [ ] **Step 1: Cập nhật state và UI trong `QaScreen.tsx`**

1. Bổ sung state `skipRewrite`:
```typescript
const [skipRewrite, setSkipRewrite] = useState(false);
```

2. Khi chọn chip trong `RewriteChips`:
```typescript
function handlePickRewrite(pickedText: string) {
  setQuery(pickedText);
  setSkipRewrite(true);
}
```

3. Khi người dùng chỉnh sửa ô `query`:
Nếu ô bị xóa rỗng (`!e.target.value.trim()`), tự động tắt `setSkipRewrite(false)`.

4. Hiển thị checkbox điều khiển trực quan bên dưới `RewriteChips`:
```tsx
<label className="skip-rewrite-toggle">
  <input
    type="checkbox"
    checked={skipRewrite}
    onChange={(e) => setSkipRewrite(e.target.checked)}
  />
  <span>⚡ Dùng câu trên tìm kiếm trực tiếp (bỏ qua bước LLM rewrite vòng 1)</span>
</label>
```

5. Trong hàm `run()`:
```typescript
const chosenQueryEn = skipRewrite && query.trim() ? query.trim() : undefined;
const out = await api.qaRun(query, question || query, topK, chosenQueryEn);
```

- [ ] **Step 2: Thêm style CSS cho `.skip-rewrite-toggle` trong `frontend/src/styles/app.css`**

```css
/* Checkbox bỏ qua LLM rewrite khi đã có câu tiếng Anh (Q&A và TRAKE) */
.skip-rewrite-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-top: 6px;
  user-select: none;
}
.skip-rewrite-toggle input[type="checkbox"] {
  cursor: pointer;
  accent-color: var(--color-accent);
}
.skip-rewrite-toggle:hover {
  color: var(--color-text-primary);
}
```

- [ ] **Step 3: Kiểm tra build TypeScript của frontend**

Chạy lệnh:
```powershell
cd frontend; npm run build; cd ..
```
Kỳ vọng: Build thành công không có lỗi type hay lint.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/QaScreen.tsx frontend/src/styles/app.css
git commit -m "fix(frontend/qa): pass query_en when rewrite chip is selected or user opts to skip rewrite"
```

---

### Task 3: Cập nhật `TrakeScreen.tsx` — Kết nối chọn chip cho mô tả tổng quát

**Files:**
- Modify: `frontend/src/screens/TrakeScreen.tsx`

**Interfaces:**
- Consumes: `api.trakeRun(globalQuery, events, topKVideo, queryEn)`
- Produces: Giao diện TRAKE cho phép truyền `query_en` cho mô tả tổng quát khi chọn chip gợi ý hoặc dịch thô.

- [ ] **Step 1: Cập nhật state và UI trong `TrakeScreen.tsx`**

1. Bổ sung state `skipGlobalRewrite`:
```typescript
const [skipGlobalRewrite, setSkipGlobalRewrite] = useState(false);
```

2. Hàm xử lý khi chọn chip từ `RewriteChips`:
```typescript
function handlePickGlobalRewrite(pickedText: string) {
  setGlobalQuery(pickedText);
  setSkipGlobalRewrite(true);
}
```

3. Gắn `onPick={handlePickGlobalRewrite}` vào `RewriteChips` của `TrakeScreen.tsx`.

4. Thêm checkbox điều khiển bên dưới:
```tsx
<label className="skip-rewrite-toggle">
  <input
    type="checkbox"
    checked={skipGlobalRewrite}
    onChange={(e) => setSkipGlobalRewrite(e.target.checked)}
  />
  <span>⚡ Dùng câu trên tìm video trực tiếp (bỏ qua LLM rewrite cho mô tả tổng quát)</span>
</label>
```

5. Trong hàm `run()`:
```typescript
const chosenQueryEn = skipGlobalRewrite && globalQuery.trim() ? globalQuery.trim() : undefined;
const out = await api.trakeRun(globalQuery, events, topKVideo, chosenQueryEn);
```

- [ ] **Step 2: Kiểm tra build TypeScript của frontend**

Chạy lệnh:
```powershell
cd frontend; npm run build; cd ..
```
Kỳ vọng: Build thành công không có lỗi.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/TrakeScreen.tsx
git commit -m "fix(frontend/trake): pass query_en for global query when chip selected or opted in"
```

---

### Task 4: Kiểm thử tích hợp toàn diện (E2E / Regression Verification)

**Files:**
- Test: `tests/unit/test_api_qa_trake_query_en.py`
- Build: `frontend/`

- [ ] **Step 1: Chạy toàn bộ unit test suite**

Chạy lệnh:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit -q
```
Kỳ vọng: Tất cả các test đều pass (≥ 60 passed).

- [ ] **Step 2: Kiểm tra Frontend Build**

Chạy lệnh:
```powershell
cd frontend; npm run build; cd ..
```
Kỳ vọng: `tsc -b && vite build` hoàn thành 100%.

- [ ] **Step 3: Cập nhật tài liệu / kiến trúc (nếu cần)**

Kiểm tra và ghi chú ngắn vào `docs/reports/` hoặc commit note.
