# Phase 5 — OCR on-demand cho Q&A — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm khả năng đọc chữ/số thật (PaddleOCR) chạy on-demand cho `pipeline_qa.py`, chỉ trên tối
đa 3 ảnh candidate của câu hỏi thực sự cần đọc chữ/số (biển số, giá tiền, số áo...), làm gợi ý phụ cho
LLM Vision — không thay thế nó, không precompute cho 177K keyframe.

**Architecture:** 1 module mới `scripts/agent/tools/ocr_read.py` (singleton PaddleOCR engine,
`read_text_from_hits(hits, top_n=3) -> dict[int, list[str]]`), wire vào Tier 2 (Vision) của
`answer_qa.py` — chỉ khi `_needs_text_reading(question)` đã True (hàm có sẵn từ round trước). Kết quả
OCR chèn vào `ANSWER_FROM_IMAGES_PROMPT` dưới dạng 1 khối hint, `_crosscheck_answer()` giữ nguyên
không đổi.

**Tech Stack:** `paddleocr==2.7.3` + `paddlepaddle==2.6.2` (CPU) — pin cứng vì API PaddleOCR đổi khác
hẳn giữa 2.x và 3.x (xem Global Constraints).

**Spec:** [PLAN.md](../../../PLAN.md) mục "Phase 5: OCR on-demand cho Q&A", [ARCHITECTURE.md](../../../ARCHITECTURE.md)
§2 (dòng `ocr_read.py (mới)`), [DECISION.md](../../../DECISION.md) mục "OCR on-demand (Phase 5)".

## Global Constraints

- UI text và code comment viết bằng tiếng Việt (không dấu hoặc có dấu đều được, theo đúng phong cách
  file đang sửa) — áp dụng cho toàn bộ file trong task này (`ocr_read.py`, `answer_qa.py`, script test).
- `snake_case` cho mọi tên hàm/biến mới. Không camelCase.
- Không gọi `litellm`/`call_llm()` trong `ocr_read.py` — đây là tín hiệu phụ thuần local (PaddleOCR
  chạy trên máy), không phải LLM call.
- Không precompute OCR cho toàn bộ 177K keyframe — `read_text_from_hits()` chỉ nhận `hits` đã retrieve
  sẵn, giới hạn cứng `top_n` (mặc định 3).
- OCR là gợi ý phụ, không thay thế Vision, không bỏ qua `_crosscheck_answer()` đang có trong
  `answer_qa.py` — chỉ chèn thêm text vào prompt Tier 2, không tự tạo answer.
- Không đổi shape trả về của `answer_from_hits()`: vẫn `{answer, best_hit, confidence, method}`.
- Nếu PaddleOCR chưa cài được / lỗi lúc load / lỗi lúc OCR 1 ảnh cụ thể: không crash toàn bộ
  pipeline — log cảnh báo `[ocr_read] CẢNH BÁO: ...` rồi trả về rỗng, `answer_qa.py` chạy tiếp như
  không có gợi ý OCR (khớp success criterion PLAN.md Phase 5: "không phát sinh crash khi OCR không
  đọc được gì").
- Logging: `print()` với prefix `[ocr_read]` (module mới) / `[qa]` nếu log thêm trong `answer_qa.py`
  (giữ đúng quy ước có sẵn, không thêm framework logging).
- `frame_id`/`video_id` không tự +1 hoặc thêm `.mp4` ở đây — chỉ đọc `hit["jpg_path"]` đã có sẵn từ
  `retrieve.py`.

---

## Task 1: Module `ocr_read.py` — PaddleOCR wrapper + self-test thuần (không LLM)

**Files:**
- Modify: `requirements.txt` (thêm 2 dòng dependency)
- Modify: `PLAN.md:28-29,220-221` (sửa lại `EasyOCR` → `PaddleOCR` — 2 chỗ còn sót lại từ lần revert
  `6838fd1`, DECISION.md đã chốt PaddleOCR từ 2026-08-24 nhưng PLAN.md mục chuẩn bị ngày 1 và mục
  Blockers chưa cập nhật theo)
- Create: `scripts/agent/tools/ocr_read.py`

**Interfaces:**
- Produces (dùng ở Task 2):
  - `read_text_from_hits(hits: list[dict], top_n: int = 3) -> dict[int, list[str]]` — key là index
    trong `hits` (0-based, KHÔNG phải `frame_id`), value là list dòng chữ đọc được (rỗng/không xuất
    hiện key nếu ảnh không có chữ hoặc OCR lỗi).
  - `format_ocr_hint(ocr_results: dict[int, list[str]]) -> str` — trả về `""` nếu `ocr_results` rỗng,
    ngược lại trả về đoạn text nhiều dòng liệt kê chữ đọc được theo từng candidate.

- [ ] **Step 1: Thêm dependency vào `requirements.txt`**

Mở [requirements.txt](../../../requirements.txt), thêm 2 dòng ngay sau `python-dotenv==1.2.3` (trước
khối comment `# scripts/eval/`):

```
paddlepaddle==2.6.2
paddleocr==2.7.3
```

Cài thử trên máy đang làm Phase 5:

```
.venv\Scripts\python.exe -m pip install paddlepaddle==2.6.2 paddleocr==2.7.3
```

Lần đầu import `paddleocr` sẽ tự tải model PP-OCRv4 (vài chục MB) — chạy thử ngay bước này, không để
việc tải model rơi vào lúc chạy self-test ở Step 4:

```
.venv\Scripts\python.exe -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='vi', ocr_version='PP-OCRv4')"
```

Nếu lệnh trên lỗi (mạng chặn tải model, xung đột đúng như rủi ro đã ghi ở PLAN.md mục Blockers) — ghi
lại lỗi cụ thể, đây là tín hiệu cần fallback graceful ở Step 3 (không phải lý do dừng task, vì
`_get_engine()` đã thiết kế để không crash).

- [ ] **Step 2: Sửa 2 chỗ PLAN.md còn ghi EasyOCR (khớp DECISION.md đã chốt PaddleOCR)**

Ở [PLAN.md](../../../PLAN.md) dòng 28-29, đổi:

```
- Người D cài thử `pip install easyocr` trên máy sẽ làm Phase 5 **trước** ngày bắt đầu — lần đầu chạy
  EasyOCR tự tải model, tốn vài phút, không nên để việc này rơi vào lúc đang code.
```

thành:

```
- Người D cài thử `pip install paddlepaddle paddleocr` trên máy sẽ làm Phase 5 **trước** ngày bắt
  đầu — lần đầu chạy PaddleOCR tự tải model, kiểm tra xung đột môi trường sớm nếu có.
```

Ở dòng 220-221 (mục Blockers/Risks), đổi:

```
- **EasyOCR (Phase 5) là dependency mới hoàn toàn** — rủi ro cài đặt/tải model lần đầu chậm hơn dự
  kiến trên máy nào đó trong nhóm; đã đưa vào mục chuẩn bị ngày 1 để giảm rủi ro này.
```

thành:

```
- **PaddleOCR (Phase 5) là dependency mới** — rủi ro xung đột cài đặt `paddlepaddle` trên một số máy;
  đã đưa vào mục chuẩn bị ngày 1 để test cài đặt sớm.
```

(Đây đúng là nội dung DECISION.md mục "OCR on-demand (Phase 5)" đã chốt 2026-08-24 — commit `6838fd1`
chỉ revert vì bị lẫn nhầm vào commit Phase 4, không phải đảo ngược quyết định.)

- [ ] **Step 3: Viết `scripts/agent/tools/ocr_read.py`**

```python
"""
ocr_read.py — OCR that (PaddleOCR) chay on-demand tren cac keyframe candidate can doc chu/so.

Chi duoc goi khi cau hoi Q&A thuc su can doc chu/so tren man hinh (bien so, gia tien, so ao...) —
xem _needs_text_reading() trong answer_qa.py, ham nay tai su dung lam dieu kien kich hoat OCR luon.
KHONG precompute OCR cho toan bo 177K keyframe — chi nhan hits da retrieve san, gioi han cung top_n.

Ket qua OCR la GOI Y cho LLM Vision (chen vao prompt), khong tu dong tro thanh cau tra loi —
answer_qa.py van chay _crosscheck_answer() nhu cu, khong bo qua co che chong ao giac.

PaddleOCR nap model lan dau se tu tai model PP-OCRv4 (vai chuc MB, can mang lan dau chay). Neu
import/khoi tao/OCR that bai vi bat ky ly do gi, module nay KHONG crash pipeline — tra ve rong va in
canh bao, de answer_qa.py chay tiep binh thuong khong co goi y OCR.

Usage:
    from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
    ocr_results = read_text_from_hits(hits, top_n=3)   # {hit_index: [text_line, ...]}
    hint_text   = format_ocr_hint(ocr_results)          # "" neu khong doc duoc gi
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ENGINE = None
_ENGINE_LOAD_FAILED = False


def _get_engine():
    """Singleton PaddleOCR — nap 1 lan/process. Tra ve None neu load that bai (khong retry lai trong
    cung 1 process, tranh lap lai loi mang/thieu dependency nhieu lan)."""
    global _ENGINE, _ENGINE_LOAD_FAILED
    if _ENGINE is not None or _ENGINE_LOAD_FAILED:
        return _ENGINE
    try:
        from paddleocr import PaddleOCR
        print("[ocr_read] Dang nap PaddleOCR (lan dau co the tu tai model PP-OCRv4)...")
        _ENGINE = PaddleOCR(use_angle_cls=True, lang="vi", ocr_version="PP-OCRv4", show_log=False)
        print("[ocr_read] PaddleOCR san sang.")
    except Exception as error:
        print(f"[ocr_read] CANH BAO: khong nap duoc PaddleOCR ({type(error).__name__}: {error}) "
              f"— bo qua OCR cho phien nay, answer_qa.py se chay tiep khong co goi y OCR.")
        _ENGINE_LOAD_FAILED = True
        _ENGINE = None
    return _ENGINE


def _ocr_single_image(image_path: str) -> list[str]:
    """OCR 1 anh, tra ve list dong chu doc duoc (co the rong neu anh khong co chu hoac OCR loi)."""
    engine = _get_engine()
    if engine is None:
        return []
    try:
        result = engine.ocr(image_path, cls=True)
    except Exception as error:
        print(f"[ocr_read] CANH BAO: OCR that bai tren {image_path} ({type(error).__name__}: {error})")
        return []

    lines: list[str] = []
    for page in (result or []):
        for entry in (page or []):
            # entry dang [box, (text, confidence)] theo API PaddleOCR 2.7.x
            if len(entry) > 1 and entry[1]:
                text = entry[1][0]
                if text:
                    lines.append(text)
    return lines


def read_text_from_hits(hits: list[dict], top_n: int = 3) -> dict[int, list[str]]:
    """
    Chay OCR tren toi da top_n candidate hit dau tien co jpg_path ton tai tren dia.

    Args:
        hits:  list[dict] tu fast_retrieve()/fast_retrieve_for_video(), can co truong 'jpg_path'.
        top_n: So anh toi da can OCR (mac dinh 3 — gioi han chi phi/thoi gian on-demand).

    Returns:
        dict[int, list[str]]: {hit_index: [text_line, ...]}. Chi hit doc duoc >=1 dong chu moi co
        mat trong dict — dung de format_ocr_hint() phan biet duoc "khong OCR duoc gi" (dict rong).
    """
    result: dict[int, list[str]] = {}
    for i, hit in enumerate(hits[:top_n]):
        jpg_path = hit.get("jpg_path")
        if jpg_path and Path(jpg_path).exists():
            lines = _ocr_single_image(jpg_path)
            if lines:
                result[i] = lines
    return result


def format_ocr_hint(ocr_results: dict[int, list[str]]) -> str:
    """Dinh dang ket qua OCR thanh doan text ngan de chen vao prompt Vision. Rong neu khong doc
    duoc gi tu bat ky candidate nao."""
    if not ocr_results:
        return ""
    lines = []
    for hit_index in sorted(ocr_results):
        texts = ", ".join(f'"{t}"' for t in ocr_results[hit_index])
        lines.append(f"  - Candidate frame #{hit_index + 1}: {texts}")
    return "\n".join(lines)


# CLI test
if __name__ == "__main__":
    _ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

    def _fake_hit(jpg_rel_path: str) -> dict:
        return {"video_id": "", "n": 0, "frame_idx": 0, "frame_id": 1, "pts_time": 0.0,
                 "score": 1.0, "jpg_path": str(_ROOT_DIR / jpg_rel_path)}

    print("[ocr_read] === Self-test 1: hits rong / jpg_path None khong crash ===")
    assert read_text_from_hits([]) == {}
    assert read_text_from_hits([{"jpg_path": None}]) == {}
    assert read_text_from_hits([{"jpg_path": "khong_ton_tai.jpg"}]) == {}
    print("[ocr_read] Self-test 1: PASS")

    print("\n[ocr_read] === Self-test 2: OCR anh that co chu (kiem tra bang mat) ===")
    known_hits = [
        _fake_hit("data/extracted/keyframes/L22/L22_V001/120.jpg"),   # GT: "DIANA 1961 1997"
        _fake_hit("data/extracted/keyframes/L28/L28_V003/190.jpg"),   # GT: "AG-09399" / "AG-12627"
        _fake_hit("data/extracted/keyframes/L27/L27_V001/110.jpg"),   # GT: "CHÚA XỨ THÁNH MẪU"
    ]
    ocr_out = read_text_from_hits(known_hits, top_n=3)
    for i, hit in enumerate(known_hits):
        lines = ocr_out.get(i, [])
        print(f"  candidate #{i+1} ({Path(hit['jpg_path']).name}): {lines}")
    print(f"\n  format_ocr_hint():\n{format_ocr_hint(ocr_out)}")
    print("\n[ocr_read] Self-test 2 xong — tu kiem tra bang mat: co doc duoc it nhat 1 phan chu/so "
          "gan dung so voi GT ghi trong comment o tren khong? (khong hard-assert vi OCR khong dam bao "
          "chinh xac 100%).")
```

- [ ] **Step 4: Chạy self-test, xác nhận không crash**

```
.venv\Scripts\python.exe scripts\agent\tools\ocr_read.py
```

Expected: `Self-test 1: PASS` in ra, không exception. Ở self-test 2, tự đọc output — nếu cấu trúc
`result` in ra khác hẳn dạng `[box, (text, score)]` mô tả trong comment (API PaddleOCR có thể lệch
theo đúng phiên bản cài được), sửa lại vòng lặp trong `_ocr_single_image()` cho khớp cấu trúc thật rồi
chạy lại bước này tới khi self-test 1 PASS và self-test 2 in ra được text hợp lý (không bắt buộc khớp
100% GT, chỉ cần thấy rõ ràng có đọc được chữ/số, không phải toàn chuỗi rỗng cho cả 3 ảnh).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt PLAN.md scripts/agent/tools/ocr_read.py
git commit -m "feat(phase5): add ocr_read.py — PaddleOCR wrapper for on-demand text reading"
```

---

## Task 2: Wire OCR hint vào `answer_qa.py` Tier 2 (Vision)

**Files:**
- Modify: `scripts/agent/tools/answer_qa.py`

**Interfaces:**
- Consumes: `read_text_from_hits(hits, top_n=3) -> dict[int, list[str]]`,
  `format_ocr_hint(ocr_results) -> str` (Task 1).
- Produces: `answer_from_hits()` giữ nguyên signature/shape trả về — không đổi gì cho code gọi nó
  (`pipeline_qa.py` không cần sửa).

- [ ] **Step 1: Thêm import**

Trong [scripts/agent/tools/answer_qa.py](../../../scripts/agent/tools/answer_qa.py) dòng 27, ngay sau
dòng import `ocr_lookup`:

```python
from agent.tools.ocr_lookup import get_objects, objects_contain_keywords
from agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
```

- [ ] **Step 2: Thêm placeholder `{ocr_hint}` vào `ANSWER_FROM_IMAGES_PROMPT` + hằng số hint template**

Thay khối `ANSWER_FROM_IMAGES_PROMPT` (dòng 51-66) — chỉ thêm 1 dòng `{ocr_hint}` sau dòng Question,
không đổi phần còn lại:

```python
ANSWER_FROM_IMAGES_PROMPT = """\
You are analyzing up to 3 candidate video keyframes retrieved for the same scene to answer a question.
They may show the same moment at slightly different times — one may be clearer than the others.

Question: {question}
{ocr_hint}
Look at the image(s) carefully and answer concisely:
- If the question asks for a NUMBER, COUNT, or TEXT visible on a display/gauge/sign/banner/scoreboard/
    price tag, read the digits/characters literally, one by one, and report EXACTLY what is shown across
    the clearest frame — do not round, estimate, or invent a "plausible" number.
- If the question asks to COUNT people/objects, count carefully what is visible in the frame(s).
- If the target detail is not visible/legible in ANY of the frames, say so briefly instead of guessing.
- If the question is in Vietnamese, answer in Vietnamese; if in English, answer in English.
- Keep the answer SHORT (1-5 words if possible) and factual, based only on what you can see.

Answer:"""

OCR_HINT_TEMPLATE = """\
Automated OCR hint (from a text-reading model on the candidate frame(s) — may contain errors; treat \
as a hint, verify every digit/word against what you actually see in the image before trusting it):
{ocr_lines}
"""
```

- [ ] **Step 3: Chạy OCR khi cần, chèn hint vào prompt Tier 2**

Trong hàm `answer_from_hits()`, thay khối Tier 2 (dòng 186-213):

```python
    # --- Tang 2: Vision (chi khi co anh) ---
    # Gom toi da 3 anh candidate dau tien (thay vi chi anh top-1) de model doi chieu giua cac frame —
    # frame chua so/chu can doc co the khong phai frame co score CLIP cao nhat.
    vision_hits = [h for h in candidates if h.get("jpg_path") and Path(h["jpg_path"]).exists()][:3]
    if vision_hits:
        image_paths = [h["jpg_path"] for h in vision_hits]

        # OCR that (Phase 5) — chi chay khi cau hoi thuc su can doc chu/so (dieu kien tai su dung tu
        # skip_objects_tier o tren), chi lam goi y phu cho Vision, khong thay the no.
        ocr_hint = ""
        if skip_objects_tier:
            ocr_results = read_text_from_hits(vision_hits, top_n=3)
            formatted = format_ocr_hint(ocr_results)
            if formatted:
                ocr_hint = OCR_HINT_TEMPLATE.format(ocr_lines=formatted)

        prompt2 = ANSWER_FROM_IMAGES_PROMPT.format(question=question, ocr_hint=ocr_hint)
        ans2 = call_llm(
            prompt2,
            image_paths=image_paths,
            model="vision",
            temperature=0.1,
            max_tokens=80,
        )
        # Cross-check voi objects gom tu tat ca anh da gui cho vision
        combined_objs = []
        for h in vision_hits:
            hit_n, hit_vid = h.get("n"), h.get("video_id", "")
            if hit_n:
                combined_objs.extend(get_objects(hit_vid, int(hit_n)))
        crosscheck = _crosscheck_answer(question, ans2, list(dict.fromkeys(combined_objs)))
        conf = 0.85 if crosscheck else 0.6
        return {
            "answer":     _normalize_answer(ans2),
            "best_hit":   vision_hits[0],
            "confidence": conf,
            "method":     "vision",
        }
```

- [ ] **Step 4: Chạy self-test CLI có sẵn của `answer_qa.py`, xác nhận không crash**

```
.venv\Scripts\python.exe scripts\agent\tools\answer_qa.py
```

Expected: in ra `answer`/`confidence`/`method`/`best_hit` như trước (câu hỏi mẫu trong file này không
cần đọc chữ nên `ocr_hint` sẽ rỗng — đây là test "không regression", không phải test OCR thật; OCR
thật được test ở Task 3).

- [ ] **Step 5: Commit**

```bash
git add scripts/agent/tools/answer_qa.py
git commit -m "feat(phase5): wire OCR hint into answer_qa.py Tier 2 vision prompt"
```

---

## Task 3: Benchmark before/after + cập nhật PLAN.md

**Files:**
- Create: `scripts/test_phase5_ocr.py`
- Modify: `PLAN.md` (mục Phase 5 — thêm "Đã làm" theo đúng format các Phase trước)

**Interfaces:**
- Consumes: `answer_from_hits()` (Task 2), `scripts.agent.tools.answer_qa` module object (để
  monkeypatch `read_text_from_hits` giống cách `test_phase4_trake.py` đã monkeypatch `rewrite_query`
  — xem file đó dòng 32-39 để tham khảo đúng kỹ thuật).

- [ ] **Step 1: Viết `scripts/test_phase5_ocr.py`**

3 câu hỏi tự tạo tái dùng đúng `video_id`/`frame_id` GT đã có sẵn trong `queries/eval_ground_truth.json`
(e-kis-ai-007, e-kis-ai-016, e-kis-ai-013 — cả 3 đều mô tả rõ chữ/số nhìn thấy trong frame, tra `n` từ
`data/extracted/map-keyframes/` như đã làm lúc viết plan này), tránh phụ thuộc chất lượng retrieval
(dùng thẳng đúng `video_id`+`n` đã biết, không gọi `fast_retrieve`) — đúng tinh thần khử nhiễu benchmark
mà Task 2 fix round 1 của Phase 4 đã áp dụng.

```python
"""
test_phase5_ocr.py — Benchmark truoc/sau cho OCR on-demand (Phase 5, answer_qa.py Tier 2).

Dung 3 cau hoi tu tao, moi cau tro thang vao 1 frame GT co san trong eval_ground_truth.json ma mo ta
ro chu/so nhin thay duoc (e-kis-ai-007/016/013) — KHONG goi fast_retrieve() de tranh phu thuoc chat
luong retrieval, hit duy nhat duoc dung la dung video_id/n cua GT (giong tinh than Phase 4 Task2 fix
round 1: khu nhieu benchmark bang cach co dinh dau vao, chi do dung 1 bien so — o day la co/khong OCR
hint, khong phai retrieval).

Chay 2 lan tren cung 1 bo cau: pass "before" monkeypatch read_text_from_hits() thanh ham tra ve {}
(mo phong "chua co Phase 5"), pass "after" dung ham that. In answer/confidence/method canh nhau —
KHONG cham diem dung/sai (khong co gt_answer cho 3 cau nay, chi la cau tu tao de kiem tra OCR co doc
duoc chu that hay khong) — nguoi dung tu doc va danh gia.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_phase5_ocr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.agent.tools.answer_qa as _answer_qa_module
from scripts.agent.tools.answer_qa import answer_from_hits

_KEYFRAMES_DIR = _ROOT / "data" / "extracted" / "keyframes"


def _hit(video_id: str, n: int) -> dict:
    batch = video_id.split("_")[0]
    jpg_path = _KEYFRAMES_DIR / batch / video_id / f"{n:03d}.jpg"
    return {
        "video_id": video_id, "n": n, "frame_idx": n - 1, "frame_id": n,
        "pts_time": 0.0, "score": 1.0,
        "jpg_path": str(jpg_path) if jpg_path.exists() else None,
    }


# 3 cau hoi tu tao, moi cau 1 hit duy nhat tro dung frame GT da biet ro noi dung chu/so (n tra tu
# data/extracted/map-keyframes/{video_id}.csv, xem chi tiet trong docs/superpowers/plans/2026-08-24-phase5-ocr-on-demand.md).
CASES = [
    {
        "question": "What years are written on the memorial poster?",
        "hits": [_hit("L22_V001", 120)],  # GT text: "DIANA 1961 1997"
    },
    {
        "question": "What are the registration numbers painted on the two ferries?",
        "hits": [_hit("L28_V003", 190)],  # GT text: "AG-09399" / "AG-12627"
    },
    {
        "question": "What Vietnamese phrase is written on the temple sign panel?",
        "hits": [_hit("L27_V001", 110)],  # GT text: "CHÚA XỨ THÁNH MẪU"
    },
]


def _run_pass(label: str) -> list[dict]:
    results = []
    for case in CASES:
        out = answer_from_hits(case["question"], case["hits"], top_n=1)
        print(f"  [{label}] Q: {case['question']!r}")
        print(f"        answer={out['answer']!r}  confidence={out['confidence']:.2f}  method={out['method']}")
        results.append(out)
    return results


def main() -> None:
    print(f"[test_phase5] {len(CASES)} cau hoi tu tao, moi cau 1 frame GT co san (xem comment CASES).")

    # answer_from_hits() goi read_text_from_hits(...) nhu 1 ten global tra trong namespace cua module
    # answer_qa — patch thang _answer_qa_module.read_text_from_hits la du, khong can reload module
    # (giong ky thuat monkeypatch rewrite_query cua test_phase4_trake.py, khong dung lai ham da import).
    _original_read_text_from_hits = _answer_qa_module.read_text_from_hits

    print("\n[test_phase5] === Pass 1: KHONG co OCR hint (mo phong truoc Phase 5) ===")
    _answer_qa_module.read_text_from_hits = lambda hits, top_n=3: {}
    before = _run_pass("before")

    print("\n[test_phase5] === Pass 2: CO OCR hint (Phase 5 that) ===")
    _answer_qa_module.read_text_from_hits = _original_read_text_from_hits
    after = _run_pass("after")

    print("\n[test_phase5] === Ket qua tho, chua danh gia — xem lai bang mat ===")
    for case, b, a in zip(CASES, before, after):
        print(f"  Q: {case['question']!r}")
        print(f"    before: {b['answer']!r}")
        print(f"    after:  {a['answer']!r}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Chạy benchmark, dán nguyên output vào report cho người dùng**

```
.venv\Scripts\python.exe scripts\test_phase5_ocr.py
```

Chỉ dán lại số liệu/output thô (answer/confidence/method mỗi pass) khi báo cáo — **không** tự nhận
định OCR "tốt hơn"/"chính xác hơn" hay chấm điểm chất lượng; đây là phần người dùng tự trải nghiệm và
đánh giá lại (đã được người dùng yêu cầu rõ, xem hội thoại lúc lập plan này).

- [ ] **Step 3: Cập nhật `PLAN.md` mục Phase 5**

Thêm đoạn "Đã làm" ngay dưới đoạn success line hiện có của Phase 5 (dòng 177-178), theo đúng format
các Phase 1-4 đã dùng: liệt kê file mới/sửa, tóm tắt cơ chế, kết quả self-test (PASS/FAIL thô), link
tới chính plan file này. Đổi trạng thái heading từ `(⏳ Todo)` thành `(✅ Done)`.

- [ ] **Step 4: Commit**

```bash
git add scripts/test_phase5_ocr.py PLAN.md
git commit -m "feat(phase5): add before/after OCR benchmark, mark Phase 5 done in PLAN.md"
```

---

## Self-Review (đã chạy lúc viết plan này)

- **Spec coverage:** PLAN.md Phase 5 yêu cầu (1) OCR chỉ chạy khi câu hỏi cần đọc chữ/số → Task 2 Step 3
  dùng đúng `skip_objects_tier` (= `_needs_text_reading()`) làm điều kiện; (2) chỉ chạy trên vài ảnh
  candidate tốt nhất, không toàn bộ 177K keyframe → `top_n=3` mặc định ở Task 1; (3) OCR là gợi ý thêm,
  không thay thế Vision → Task 2 chỉ chèn hint vào prompt, giữ nguyên `_crosscheck_answer()`; (4) so
  sánh answer có/không OCR → Task 3; (5) không crash khi OCR không đọc được gì → xử lý try/except +
  self-test rỗng ở Task 1 Step 3.
- **Placeholder scan:** không còn "TBD"/"tương tự Task N" — mọi step có code cụ thể.
- **Type consistency:** `read_text_from_hits()` → `dict[int, list[str]]` dùng nhất quán ở Task 1 (định
  nghĩa) và Task 2/3 (tiêu thụ); `format_ocr_hint()` → `str` khớp cách dùng ở Task 2 Step 3.
