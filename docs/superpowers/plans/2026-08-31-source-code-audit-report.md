# Báo cáo Rà soát Toàn bộ Source Code AIC2026 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đọc toàn bộ source code trong repo AIC2026 và tạo **một** báo cáo Markdown giải thích ý nghĩa/vai trò của từng file, đồng thời chỉ ra các điểm bất hợp lý, thiếu logic và điểm yếu của hệ thống hiện tại.

**Architecture:** Báo cáo được xây theo **từng tầng kiến trúc** (root → retrieval core → tool nghiệp vụ → pipeline → API → submit/offline → tests → frontend → GPU jobs → tổng hợp), mỗi tầng là một task độc lập ghi thêm một chương vào cùng một file báo cáo. Mỗi file trong phạm vi có đúng **một** mục theo schema cố định (định nghĩa một lần ở §"Schema mục từng file", các task chỉ tham chiếu). Phát hiện bất thường được ghi **inline** tại mục của file (`⚠️ FINDING-nn`) và **tổng hợp lại** ở chương cuối — nghĩa là chương cuối chỉ gom, không phát sinh nội dung mới. Mỗi task kết thúc bằng các lệnh `grep`/`pytest` **thực thi được** để xác minh phát biểu trong chương đó, thay cho vòng đời TDD của plan viết code.

**Tech Stack:** Không thêm dependency. Chỉ dùng: `git`, `grep`/Grep tool, Read tool, `.venv\Scripts\python.exe -m pytest`, `python -c` cho vài phép đếm. Đầu ra là Markdown thuần.

**Spec:** Yêu cầu trực tiếp từ người dùng (2026-08-31): *"đọc toàn bộ source code của dự án, sau đó tạo một bản báo cáo chỉ ra chi tiết ý nghĩa từng file trong hệ thống. Yêu cầu báo cáo phải logic, chặt chẽ. Trong quá trình thực hiện đọc và tạo báo cáo nếu phát hiện những phần không hợp lý, thiếu logic thì cần chỉ ra rõ trong báo cáo luôn, nếu được thậm chí còn phải chỉ ra được điểm yếu của hệ thống hiện tại."* Các tài liệu đối chiếu bắt buộc: [CLAUDE.md](../../../CLAUDE.md), [ARCHITECTURE.md](../../../ARCHITECTURE.md), [PLAN.md](../../../PLAN.md), [docs/decisions-log.md](../../decisions-log.md).

---

## Global Constraints

Áp dụng cho **mọi** task bên dưới, không nhắc lại trong từng task:

- **Ngôn ngữ báo cáo: tiếng Việt có dấu.** Thuật ngữ kỹ thuật (`RRF`, `keyframe`, `embedding`, `router`, `singleton`) giữ nguyên tiếng Anh, không dịch. Đây là quy ước repo-wide trong [CLAUDE.md](../../../CLAUDE.md) §Code Rules.
- **File báo cáo duy nhất:** `docs/reports/source-code-audit-2026-08-31.md`. Không tạo file phụ, không tách phụ lục. Mỗi task **append** một chương, không sửa chương của task trước (trừ Task 10 được phép sửa mục lục + chèn Tóm tắt điều hành).
- **Tham chiếu file phải là markdown link tương đối từ vị trí báo cáo**, ví dụ `[index_store.py](../../scripts/agent/tools/index_store.py)`. Có dòng cụ thể thì dùng `#L150`. Không dùng backtick trần cho đường dẫn file.
- **Không file nào trong phạm vi được bỏ trống.** Cấm viết "tương tự file trên", "xem mục trước", "TODO", "sẽ bổ sung". File tầm thường (`__init__.py` rỗng) vẫn có mục, nội dung là một dòng nêu rõ nó rỗng và tại sao điều đó đúng/sai.
- **Mọi phát biểu về hành vi phải đọc từ code, không suy từ tên file và không suy từ tài liệu.** Khi code mâu thuẫn tài liệu (CLAUDE.md / ARCHITECTURE.md / docstring), đó là một FINDING — ghi lại, không "hòa giải" bằng cách chọn bên nghe hợp lý hơn.
- **Đánh số finding liên tục toàn báo cáo:** `FINDING-01`, `FINDING-02`, … Task N tiếp tục dãy số của Task N-1 (đọc số cuối cùng trong file trước khi ghi thêm). Mỗi finding gồm 4 phần bắt buộc: **Hiện trạng** (kèm file:line) · **Vì sao bất hợp lý** · **Hệ quả thực tế** · **Mức độ** (`Cao` / `Trung bình` / `Thấp`).
- **Phân biệt rạch ròi 3 loại nhận xét**, không trộn: (a) *Bất hợp lý* — code tự mâu thuẫn hoặc mâu thuẫn tài liệu; (b) *Điểm yếu hệ thống* — code đúng như thiết kế nhưng thiết kế có rủi ro; (c) *Ghi chú* — quan sát trung tính. Chỉ (a) và (b) được đánh số FINDING.
- **Không đánh giá chất lượng số liệu eval.** Nếu báo cáo trích số từ `docs/reports/` hoặc `tests/e2e/e2e_baseline.json`, chép nguyên số + nguồn, không viết "tốt", "kém", "đáng thất vọng". (Quy ước đã có của người dùng.)
- **Không sửa bất kỳ file source nào.** Task này là read-only trên `scripts/`, `tests/`, `frontend/`, `kaggle_jobs/`. Chỉ được tạo/sửa file báo cáo. Nếu phát hiện bug muốn sửa → ghi thành FINDING, không sửa.
- **Commit sau mỗi task**, message dạng `docs(audit): <chương> — <n> file, <m> finding`.

---

## Phạm vi (Scope)

**Luật tính phạm vi** — viết một lần, mọi phép đếm trong plan này dùng đúng nó:

> In-scope = file được `git ls-files` track, **trừ** phần mở rộng media/binary
> (`.jpg .jpeg .png .svg .pdf .pptx .npy .mp4`), **trừ** mọi đường dẫn chứa `_archive`,
> **trừ** `frontend/package-lock.json`, **trừ** các thư mục `.agents/ .superpowers/
> .claude/ docs/ data/ submissions/` — **cộng** đúng hai ngoại lệ tái đưa vào:
> `package-lock.json` ở root và `docs/decisions-log.md`.

Lệnh tái lập số liệu (chạy được, dùng ở Task 10 Step 7):

```bash
EX='\.(jpg|jpeg|png|svg|pdf|pptx|npy|mp4)$|_archive|frontend/package-lock\.json'
git ls-files scripts tests frontend kaggle_jobs colab_jobs | grep -Ev "$EX" | wc -l   # 197
# + 11 file tầng gốc của Task 1 = 208
```

**Trong phạm vi — 208 file** (số đã đối chiếu với cây làm việc tại HEAD `a73b208`):

| Nhóm | Số file | Task | `####` lũy kế sau task |
|---|---|---|---|
| Root: docs điều hướng + config | 11 | 1 | 11 |
| `scripts/agent/tools/` — retrieval core | 10 | 2 | 21 |
| `scripts/agent/tools/` — Q&A / TRAKE / evidence | 12 | 3 | 33 |
| `scripts/agent/` — pipeline + LLM config | 6 | 4 | 39 |
| `scripts/api/` | 13 | 5 | 52 |
| `scripts/submit/` (4) + `scripts/offline/` (25) | 29 | 6 | 81 |
| `tests/` | 49 | 7 | 130 |
| `frontend/` | 39 | 8 | 169 |
| `kaggle_jobs/` (35) + `colab_jobs/` (4) | 39 | 9 | 208 |

**Ngoài phạm vi — phải nêu rõ lý do trong §0.2 của báo cáo:**

- `.agents/`, `.superpowers/`, `.claude/` — cấu hình agent của công cụ khác (Antigravity) và cache plugin, không phải hệ thống retrieval. [CLAUDE.md](../../../CLAUDE.md) yêu cầu không coi chúng là chỉ dẫn.
- `data/`, `submissions/*.zip` — state ngoài, git-ignored, không có trong repo.
- `docs/` — tài liệu tham khảo, **trừ** `docs/decisions-log.md` được kéo vào Task 1 vì nó ghi lịch sử quyết định và sai lầm, là bằng chứng trực tiếp cho chương 10.
- `docs/_archive/`, `kaggle_jobs/_archive_logs_20260819/` (9 file log) — bản bị thay thế, giữ để tra cứu lịch sử.
- `frontend/package-lock.json`, `frontend/public/*.svg`, `scripts/offline/analysis/output/*.jpg` — lockfile sinh tự động và file media.
- `package-lock.json` ở **root** thì **ngược lại — nằm TRONG phạm vi** (Task 1 Step 4), vì sự tồn tại của nó ở root mâu thuẫn với tuyên bố "toolchain Node chỉ sống trong `frontend/`". Nó là đối tượng cần giải thích, không phải file cần bỏ qua.

**Quy ước heading (bắt buộc, mọi task):** `##` cho chương, `###` cho tiểu mục
(§0.1–§0.4, §10.1–§10.4), `####` **chỉ dành riêng** cho mục của một file. Nhờ vậy
`grep -c "^#### "` luôn bằng đúng số file đã viết — đó là cơ chế duy nhất phát hiện
bỏ sót file, không được phá.

**Quy ước độ sâu link trong BÁO CÁO** (báo cáo nằm ở `docs/reports/`, sâu 2 cấp):
file gốc repo → `../../CLAUDE.md`; file trong `docs/` → `../decisions-log.md`; code →
`../../scripts/agent/tools/hybrid.py`. (Plan này dùng `../../../` vì nó nằm sâu 3 cấp
— **đừng chép độ sâu của plan vào báo cáo**.)

---

## File Structure

Chỉ tạo **một** file mới:

- Create: `docs/reports/source-code-audit-2026-08-31.md`

Bố cục cố định (Task 1 dựng khung rỗng có sẵn đủ 11 heading `##`, các task sau chỉ điền vào chương của mình — nhờ vậy nhiều task có thể chạy mà không tranh chấp vị trí chèn):

```
# Báo cáo Rà soát Source Code — Hệ thống AIC2026
## 0. Bối cảnh, phạm vi và phương pháp        ← Task 1
## 1. Tầng gốc: tài liệu điều hướng và cấu hình ← Task 1
## 2. Lõi truy hồi (retrieval core)            ← Task 2
## 3. Tool nghiệp vụ: Q&A, TRAKE, bằng chứng   ← Task 3
## 4. Tầng pipeline và cổng gọi LLM            ← Task 4
## 5. Tầng API (FastAPI backend)               ← Task 5
## 6. Tầng nộp bài và tiền xử lý offline       ← Task 6
## 7. Tầng kiểm thử và đo chất lượng           ← Task 7
## 8. Frontend (React + Vite)                  ← Task 8
## 9. Job GPU ngoài (Kaggle / Colab)           ← Task 9
## 10. Tổng hợp: bất hợp lý và điểm yếu hệ thống ← Task 10
```

**Lý do đặt ở `docs/reports/`:** [CLAUDE.md](../../../CLAUDE.md) mô tả `docs/reports/` là "generated eval numbers". Báo cáo này là tài liệu sinh ra từ phân tích, gần bucket đó nhất; không tạo bucket `docs/` mới cho một file. Task 1 Step 6 ghi chú lựa chọn này ngay trong §0.2 để người đọc sau không nhầm nó là số liệu eval.

**Ngưỡng an toàn về độ dài:** dự kiến ~2.200–2.800 dòng cho 208 mục. Độ dài KHÔNG phải lý do tách file — báo cáo là tài liệu tra cứu, mục lục và `####` cố định làm nó điều hướng được. Vượt 3.000 dòng thì ghi một dòng vào ledger và đi tiếp.

---

## Schema mục từng file

Định nghĩa **một lần** ở đây. Mọi task từ 1→9 dùng đúng schema này, không biến tấu, không thêm/bớt trường. Task 1 Step 5 chép nguyên khối này vào §0.3 của báo cáo để người đọc biết cách đọc.

````markdown
#### [`<tên file>`](<đường dẫn tương đối>) — `<n>` dòng · `<nhãn>`

- **Vai trò:** một câu, nói *nó tồn tại để làm gì*, không mô tả lại tên file.
- **Đầu vào:** import nội bộ (dạng `scripts.…`), thư viện ngoài, file dưới `data/`, biến môi trường.
- **Đầu ra:** giá trị trả về / file ghi ra / endpoint expose.
- **Ai gọi nó:** liệt kê file gọi tới, lấy từ `grep`, không đoán. Không ai gọi → ghi thẳng "Không file nào import — xem FINDING-nn".
- **Điểm cần biết:** 1–3 gạch đầu dòng: hằng số đã tune, invariant, thuật toán chính, cạm bẫy.
- **⚠️ FINDING-nn (Mức độ):** chỉ xuất hiện khi có phát hiện. Đủ 4 phần: Hiện trạng (file:line) · Vì sao bất hợp lý · Hệ quả thực tế · Mức độ.
````

`<nhãn>` chọn từ tập đóng, để chương 10 thống kê được:
`pure` (không I/O, không model, không LLM) · `stateful` (giữ singleton/cache) · `io` (đọc/ghi `data/`) · `llm` (gọi `call_llm`) · `http` (endpoint) · `cli` (có `__main__`) · `test` · `config` · `doc` · `ui`.
Một file có thể mang nhiều nhãn, nối bằng `+` (ví dụ `stateful + io + cli`).

---

## Ví dụ mẫu đã kiểm chứng (dùng làm chuẩn chất lượng)

Mục dưới đây được viết sẵn từ dữ liệu **đã chạy thật** trong lúc lập kế hoạch. Người thực thi Task 2 chép nguyên nó vào báo cáo (đây là FINDING đầu tiên, đã xác minh) và bắt chước độ chi tiết này cho các mục còn lại:

````markdown
#### [`hybrid.py`](../../scripts/agent/tools/hybrid.py) — 165 dòng · `stateful + io`

- **Vai trò:** hợp nhất kết quả dense (cosine SigLIP) và sparse (BM25) bằng RRF để tăng recall cho truy vấn có thực thể/chữ trên màn hình.
- **Đầu vào:** `scripts.agent.tools.index_store` (ma trận embedding), `scripts.agent.tools.sparse_index` (cache BM25), `scripts.agent.tools.fusion` (RRF thuần).
- **Đầu ra:** danh sách hit đã fuse, mỗi hit là dict có `video_id` / `frame_id` / `score`.
- **Ai gọi nó:** `scripts/agent/pipeline_kis.py`, `scripts/api/routers/kis.py`.
- **Điểm cần biết:**
  - RRF được tách sang [`fusion.py`](../../scripts/agent/tools/fusion.py) dạng pure để `tests/eval/run_eval.py` dùng lại đúng thuật toán production.
  - Nhánh sparse im lặng trả rỗng nếu chưa build cache BM25 (`sparse_index.py --build`, ~3,5 phút).

- **⚠️ FINDING-01 (Trung bình):**
  - **Hiện trạng:** [hybrid.py:156](../../scripts/agent/tools/hybrid.py#L156) tự tính `"frame_id": frame_idx + 1`. Cùng lỗi ở [multi_index.py:78](../../scripts/agent/tools/multi_index.py#L78).
  - **Vì sao bất hợp lý:** [CLAUDE.md](../../CLAUDE.md) và chính docstring của [index_store.py:13](../../scripts/agent/tools/index_store.py#L13) khẳng định `row_to_hit()` là **điểm duy nhất trong toàn repo** quy đổi `frame_id = frame_idx + 1`. Có 2 chỗ khác đang tự quy đổi ⇒ invariant được tuyên bố nhưng không được giữ.
  - **Hệ quả thực tế:** nếu quy ước đánh số frame của BTC đổi, hoặc `row_to_hit()` thêm hậu xử lý (clamp, ánh xạ shard), hai đường này lệch âm thầm; đường hybrid và đường multi-model sinh `frame_id` khác đường dense trên cùng một keyframe, và sai số chỉ lộ ra ở file nộp.
  - **Mức độ:** Trung bình — hiện tại giá trị vẫn khớp, rủi ro là ở lần thay đổi tiếp theo.
````

---

## Task 1: Dựng khung báo cáo + Chương 0 và 1 (tầng gốc)

**Files:**
- Create: `docs/reports/source-code-audit-2026-08-31.md`
- Read: `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `PLAN.md`, `GEMINI.md`, `requirements.txt`, `.env.example`, `.gitignore`, `.claudeignore`, `package-lock.json`, `docs/decisions-log.md`

**Interfaces:**
- Consumes: không có (task đầu tiên).
- Produces: file báo cáo với **11 heading `##` đã có sẵn theo đúng thứ tự ở §File Structure**, §0.1–§0.4 và §1 đã điền. Dãy FINDING bắt đầu từ `FINDING-01`; task sau đọc số cuối để tiếp tục. §0.3 chứa bản chép của §Schema mục từng file. §0.4 chứa bảng "Bản đồ 10 chương ↔ nhóm file ↔ số file".

- [x] **Step 1: Đọc 6 tài liệu điều hướng**

Đọc trọn vẹn `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `PLAN.md`, `GEMINI.md`, `docs/decisions-log.md`. Vừa đọc vừa ghi ra scratchpad danh sách **phát biểu kiểm chứng được** mà tài liệu đưa ra — đây là input cho toàn bộ các task sau. Tối thiểu phải bắt được 6 phát biểu này:

1. `call_llm()` trong `scripts/agent/config.py` là nơi duy nhất gọi litellm.
2. `row_to_hit()` trong `index_store.py` là nơi duy nhất tính `frame_id = frame_idx + 1`.
3. `build_submission.py` là nơi duy nhất ghi file CSV/ZIP nộp bài.
4. `fusion.py` / `temporal_nms.py` / `query_expand.py` / `trake_align.py` là module **pure**.
5. Chỉ repo root nằm trên `sys.path`; không bao giờ đặt `scripts/` lên `sys.path`.
6. `scripts/` có **đúng 4** bucket: `agent/`, `api/`, `submit/`, `offline/`.

- [x] **Step 2: Chạy bộ lệnh xác minh 6 phát biểu**

```bash
# (1) litellm ngoài config.py — kỳ vọng: rỗng
grep -rn "import litellm\|from litellm\|litellm\." scripts tests --include=*.py | grep -v "scripts/agent/config.py"
# (2) tự quy đổi frame_idx+1 — kỳ vọng: chỉ index_store.py có dòng code (dòng khác chỉ là comment)
grep -rn "frame_idx + 1\|frame_idx+1" scripts --include=*.py
# (3) ai import build_submission
grep -rln "build_submission" scripts tests --include=*.py
# (4) module pure có import nặng không — kỳ vọng: rỗng
grep -n "^import\|^from" scripts/agent/tools/fusion.py scripts/agent/tools/temporal_nms.py scripts/agent/tools/query_expand.py scripts/agent/tools/trake_align.py | grep -E "torch|transformers|litellm|index_store|pandas|numpy"
# (5) ai đẩy scripts/ lên sys.path — kỳ vọng: rỗng
grep -rn "sys.path" scripts tests --include=*.py | grep -v "parents\[" | grep -iv "repo_root\|ROOT"
# (6) bucket dưới scripts/ — kỳ vọng: agent api offline submit
git ls-files scripts | cut -d/ -f2 | sort -u
```

Ghi nguyên **output** của từng lệnh vào scratchpad. Kết quả (2) đã biết trước từ lúc lập kế hoạch: `hybrid.py:156` và `multi_index.py:78` **vi phạm** — đó là `FINDING-01`, đã soạn sẵn ở §Ví dụ mẫu, Task 2 sẽ chép vào. Ba phát biểu (1), (5), (6) đã xác minh là **đúng** lúc lập kế hoạch; nếu chạy lại thấy khác, đó là finding mới.

- [x] **Step 3: Đối chiếu ARCHITECTURE.md với cây file thật**

```bash
git ls-files scripts tests frontend | wc -l
# Mọi file .py dưới scripts/ mà ARCHITECTURE.md hoặc CLAUDE.md không nhắc tên:
for f in $(git ls-files 'scripts/**/*.py'); do b=$(basename $f); grep -q "$b" ARCHITECTURE.md CLAUDE.md || echo "KHONG DUOC TAI LIEU NHAC: $f"; done
```

Mỗi file lọt ra ở lệnh thứ hai là ứng viên finding "code không có trong tài liệu kiến trúc" — chưa kết luận ở đây, chuyển cho task phụ trách bucket đó xác nhận (có thể nó chỉ là helper tầm thường).

- [x] **Step 4: Đọc 5 file cấu hình + soi bất thường lockfile**

Đọc `requirements.txt`, `.env.example`, `.gitignore`, `.claudeignore`, và **liếc 20 dòng đầu** `package-lock.json` ở root (không đọc hết — file sinh tự động).

```bash
head -20 package-lock.json
git ls-files | grep -c "^frontend/package"
grep -n "OPENROUTER\|LM_STUDIO\|AIC_MODE\|GEMINI" .env.example
```

Kiểm 3 điều, mỗi điều sai là một finding:
- `package-lock.json` ở **root** trong khi [CLAUDE.md](../../../CLAUDE.md) khẳng định "toolchain Node/npm chỉ sống trong `frontend/`". Xác định nó khai báo package gì và có `frontend/package.json` tương ứng không.
- `.env.example` có chứa key thật không (phải là placeholder 100%), và có liệt kê **đủ** biến mà `config.py` đọc không — để trống chỗ này thì người mới clone repo sẽ chết lúc chạy.
- `requirements.txt` có ghim version không, có liệt kê `torch` CUDA build không, có dependency nào không file nào import không.

- [x] **Step 5: Tạo file báo cáo với khung 11 chương + §0**

Tạo `docs/reports/source-code-audit-2026-08-31.md`. Bắt buộc có, theo đúng thứ tự:

1. Tiêu đề `# Báo cáo Rà soát Source Code — Hệ thống AIC2026`, dòng ngày `2026-08-31`, dòng commit `git rev-parse --short HEAD` và nhánh `fix/phase2` (chạy `git rev-parse --short HEAD` để lấy giá trị thật, không chép `8cc2615` một cách mù quáng).
2. Một chỗ giữ chỗ `<!-- TÓM TẮT ĐIỀU HÀNH — Task 10 điền -->` ngay dưới tiêu đề.
3. Mục lục 11 dòng link tới 11 heading.
4. `## 0. Bối cảnh, phạm vi và phương pháp` gồm:
   - **§0.1 Hệ thống này là gì** — 1 đoạn: bài toán text→video-frame retrieval AIC2026, 3 loại truy vấn KIS/Q&A/TRAKE, cách chấm R-Score/R@k.
   - **§0.2 Phạm vi và loại trừ** — chép bảng ở §Phạm vi của plan này, kèm lý do loại trừ từng nhóm, kèm ghi chú vì sao báo cáo nằm ở `docs/reports/`.
   - **§0.3 Cách đọc một mục file** — chép nguyên khối §Schema mục từng file (cả tập nhãn đóng).
   - **§0.4 Bản đồ chương ↔ nhóm file ↔ số file** — bảng 9 dòng.
5. Chín heading `##` còn lại (`## 1.` … `## 10.`), mỗi cái theo sau đúng một dòng `<!-- Task N điền -->`. **Phải tạo hết ở bước này** để các task sau chỉ thay thế comment, không phải tự tìm chỗ chèn.

- [x] **Step 6: Viết §1 — tầng gốc (11 file)**

Mỗi file một mục theo schema. Nội dung tối thiểu cho từng file:

- `README.md` — đối tượng đọc là ai, có trùng lặp/mâu thuẫn với CLAUDE.md không.
- `CLAUDE.md` — khế ước làm việc: 4 bucket, quy tắc single-call-site, quy ước ngôn ngữ, danh sách DO NOT.
- `ARCHITECTURE.md` — thiết kế + tham số đã tune; nêu rõ nó khác CLAUDE.md ở chỗ nào (thiết kế vs quy ước hằng ngày).
- `PLAN.md` — việc còn lại theo phase; ghi lại **phase hiện tại đang ở đâu** vì chương 10 cần đối chiếu "điểm yếu" với "đã có kế hoạch xử lý chưa".
- `docs/decisions-log.md` — lịch sử quyết định + sai lầm; liệt kê những bug đã tái phát (theo chính file đó, lỗi `sys.path` đã cắn 3 lần) vì đó là bằng chứng trực tiếp cho chương điểm yếu.
- `GEMINI.md` — cấu hình cho agent khác; nêu rủi ro hai bộ chỉ dẫn song song trôi lệch nhau.
- `requirements.txt`, `.env.example`, `.gitignore`, `.claudeignore`, `package-lock.json` — dùng kết quả Step 4.

Kết chương bằng bảng `| File | Vai trò một dòng | Finding |` cho 11 file.

- [x] **Step 7: Tự kiểm chương 1**

```bash
# Đủ 11 mục file?
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md
# Đủ 11 heading chương?
grep -c "^## " docs/reports/source-code-audit-2026-08-31.md
# Còn placeholder cấm không? Kỳ vọng: chỉ còn các comment "<!-- Task N điền -->"
grep -n "TODO\|TBD\|tương tự file trên\|sẽ bổ sung" docs/reports/source-code-audit-2026-08-31.md
```

Kỳ vọng: lệnh 1 ra `11`, lệnh 2 ra `11`, lệnh 3 rỗng.

- [x] **Step 8: Commit**

```bash
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): khung bao cao + chuong 0-1 tang goc"
```

---

## Task 2: Chương 2 — Lõi truy hồi (retrieval core)

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 2 điền -->` dưới `## 2.`)
- Read: `scripts/agent/tools/` → `index_store.py` (227), `multi_index.py` (353), `retrieve.py` (108), `hybrid.py` (165), `fusion.py` (95), `sparse_index.py` (372), `temporal_nms.py` (75), `frames.py` (82), `query_expand.py` (110), `rerank.py` (329)

**Interfaces:**
- Consumes: từ Task 1 — schema mục file (§0.3), số finding cuối cùng, danh sách phát biểu kiểm chứng được, output các lệnh grep ở Task 1 Step 2.
- Produces: §2 hoàn chỉnh 10 mục; số FINDING cuối cùng; **sơ đồ phụ thuộc của lõi retrieval** (khối mermaid `flowchart LR`) mà Task 4 và Task 10 sẽ tham chiếu, không vẽ lại.

- [x] **Step 1: Đọc trọn 10 file, không đọc lướt**

Thứ tự đọc bắt buộc, đi từ nền lên: `fusion.py` → `temporal_nms.py` → `query_expand.py` (3 module pure, dễ nắm) → `index_store.py` (singleton, nền của mọi thứ) → `retrieve.py` → `sparse_index.py` → `hybrid.py` → `multi_index.py` → `frames.py` → `rerank.py`.

Với mỗi file ghi vào scratchpad: danh sách hàm public, hằng số module-level viết HOA, mọi lệnh đọc file dưới `data/`, mọi biến `os.environ`.

- [x] **Step 2: Dựng bản đồ ai-gọi-ai bằng grep, không đoán**

```bash
for m in index_store multi_index retrieve hybrid fusion sparse_index temporal_nms frames query_expand rerank; do
  echo "=== $m <- duoc import boi ==="
  grep -rln "tools.$m\|tools import $m\|from scripts.agent.tools.$m" scripts tests --include=*.py
done
```

Điền cột **Ai gọi nó** cho cả 10 mục từ đúng output này. Module nào không ai import ⇒ finding "dead code hoặc entry point ẩn" — phải kiểm thêm xem nó có `__main__` không trước khi kết luận.

- [x] **Step 3: Xác minh 4 invariant riêng của lõi**

```bash
# (a) module pure có thực sự pure? Ky vong: rong
grep -n "open(\|np.load\|pd.read\|requests\.\|call_llm\|torch\|transformers" scripts/agent/tools/fusion.py scripts/agent/tools/temporal_nms.py scripts/agent/tools/query_expand.py
# (b) index/model co bi nap 2 lan? Dem so cho khoi tao
grep -rn "_load_index\|_INDEX\b\|lru_cache\|global _" scripts/agent/tools/index_store.py scripts/agent/tools/multi_index.py
# (c) hang so da tune nam o dau, harness nao cham toi
grep -rn "MARGIN_THRESHOLD\|RECALL_HEAD_N\|SPREAD_MAX_PER_VIDEO\|RRF_K\|TOP_K" scripts tests --include=*.py
# (d) embedding co duoc upcast float32 + renormalize khong
grep -n "float32\|astype\|norm\|normalize" scripts/agent/tools/index_store.py scripts/agent/tools/multi_index.py
```

Chú ý (c): [CLAUDE.md](../../../CLAUDE.md) cảnh báo `MARGIN_THRESHOLD` / `RECALL_HEAD_N` / `SPREAD_MAX_PER_VIDEO` sống trong `rerank.py` mà `tests/eval/run_eval.py` **không hề import**. Xác nhận điều đó bằng output lệnh (c) và ghi thành finding về **lỗ hổng harness** nếu đúng — đây là loại (b) *điểm yếu hệ thống*, không phải bug.

Chú ý (d): [CLAUDE.md](../../../CLAUDE.md) yêu cầu upcast float32 + re-normalize khi load. Nếu `multi_index.py` làm khác `index_store.py` ⇒ finding: hai đường load index có tiền xử lý lệch nhau thì điểm số hai backbone không so sánh được.

- [x] **Step 4: Viết 10 mục file**

Theo schema §0.3. Chép nguyên mục mẫu `hybrid.py` + `FINDING-01` từ §Ví dụ mẫu của plan này (đã kiểm chứng, chỉ cần đánh lại số finding nếu Task 1 đã dùng `FINDING-01`).

Ba mục dưới đây phải sâu hơn phần còn lại vì chúng là nơi bug hay trú:

- **`index_store.py`** — cơ chế singleton (biến global? `lru_cache`? import-time side effect?), thứ tự load, điều gì xảy ra khi `data/` thiếu, `row_to_hit()` trả đúng những key nào. Đối chiếu với ký ức đã ghi nhận về bug "nạp index 2 bản" — kiểm xem đường nào hiện còn có thể kích hoạt lại nó (đặc biệt `tests/`).
- **`rerank.py`** — giải thích *risk-aware ranking* và *recall-tail preservation* bằng lời, kèm giá trị hằng số thật. Nêu rõ hằng số này chỉ đo được bằng `tests/e2e/score_pipelines.py --types kis`, không đo được bằng `run_eval.py`.
- **`sparse_index.py`** — cache BM25 build offline ~3,5 phút; điều gì xảy ra khi cache **chưa** build (fail loud hay im lặng trả rỗng?). Nếu im lặng ⇒ finding mức Cao: hybrid âm thầm suy biến về dense-only mà không ai biết, và mọi số đo hybrid sau đó là giả.

- [x] **Step 5: Vẽ sơ đồ phụ thuộc lõi**

Chèn cuối §2 một khối ```mermaid `flowchart LR` thể hiện: `index_store` ở gốc → `retrieve` / `multi_index` → `hybrid` (fuse cùng `sparse_index` qua `fusion`) → `temporal_nms` → `rerank` → đầu ra pipeline. Chỉ vẽ cạnh **có thật trong output Step 2**, không vẽ cạnh "hợp lý về mặt khái niệm".

- [x] **Step 6: Tự kiểm chương 2**

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 21 (11 + 10)
grep -o "FINDING-[0-9]*" docs/reports/source-code-audit-2026-08-31.md | sort -u   # so lien tuc, khong trung, khong nhay coc
```

- [x] **Step 7: Commit**

```bash
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 2 loi truy hoi — 10 file"
```

---

## Task 3: Chương 3 — Tool nghiệp vụ (Q&A, TRAKE, bằng chứng)

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 3 điền -->`)
- Read: `scripts/agent/tools/` → `answer_qa.py` (375), `qa_prompts.py` (121), `qa_classify.py`, `qa_normalize.py` (106), `trake_align.py` (102), `objects_lookup.py` (125), `ocr_read.py` (573), `asr_lookup.py` (85), `rewrite.py` (227), `translate_raw.py`, `__init__.py`, `CLAUDE.md`

**Interfaces:**
- Consumes: §0.3 schema; sơ đồ lõi từ Task 2 (để nói rõ tool nghiệp vụ *tiêu thụ* hit từ lõi chứ không tự truy hồi).
- Produces: §3 với 12 mục; bảng "tín hiệu bằng chứng" (OCR / Objects / ASR / caption) ghi rõ mỗi tín hiệu chạy **on-demand hay offline**, dữ liệu nằm ở đâu — Task 6 sẽ nối bảng này với phía sinh dữ liệu.

- [x] **Step 1: Đọc 12 file**

Thứ tự: `qa_classify.py` → `qa_normalize.py` → `qa_prompts.py` → `answer_qa.py` (nhánh Q&A, từ nhỏ tới lớn) → `trake_align.py` → `objects_lookup.py` → `asr_lookup.py` → `ocr_read.py` → `rewrite.py` → `translate_raw.py` → `__init__.py` → `CLAUDE.md`.

- [x] **Step 2: Xác minh ranh giới OCR vs Objects, và luật on-demand**

```bash
# objects_lookup KHONG duoc lam OCR that (CLAUDE.md noi ro "not OCR")
grep -n "paddle\|easyocr\|vietocr\|Image.open\|cv2" scripts/agent/tools/objects_lookup.py
# ocr_read chay on-demand: phai co gioi han so anh / chi chay tren candidate
grep -n "top_k\|max_\|limit\|candidates\|\[:.*\]" scripts/agent/tools/ocr_read.py | head -40
# ai goi ocr_read, va goi voi bao nhieu anh
grep -rn "ocr_read\|read_ocr\|run_ocr" scripts tests --include=*.py | grep -v "scripts/agent/tools/ocr_read.py"
# rewrite/translate_raw: cai nao dung LLM, cai nao khong
grep -n "call_llm" scripts/agent/tools/rewrite.py scripts/agent/tools/translate_raw.py scripts/agent/tools/qa_normalize.py scripts/agent/tools/query_expand.py
```

Điểm phải kết luận rõ ràng, vì [CLAUDE.md](../../../CLAUDE.md) cấm chạy OCR/VLM trên toàn bộ 177K keyframe ở đường truy vấn: `ocr_read.py` có **giới hạn cứng** số ảnh không? Nếu giới hạn đến từ *lời gọi* chứ không từ *chính module*, đó là finding — luật chỉ được thực thi bằng kỷ luật của người gọi, một call site mới là vi phạm.

- [x] **Step 3: Soi `ocr_read.py` (573 dòng — file lớn nhất repo)**

Liệt kê: có mấy backend OCR, chọn backend bằng gì, có fallback không, cache ở đâu, xử lý ảnh hỏng thế nào. Trả lời hai câu:
- File 573 dòng này có **nhiều hơn một** trách nhiệm không? (đọc ảnh + chạy OCR + hậu xử lý + cache + chọn backend). Nếu có ⇒ finding loại (b) *điểm yếu*: file khó test, khó giữ trong đầu, và [tests/unit/test_ocr_read.py](../../tests/unit/test_ocr_read.py) phủ được bao nhiêu phần trong số đó.
- Nó có phụ thuộc Elasticsearch không? Đối chiếu với `scripts/offline/ocr/es_index.py` và `index_ocr_es.py` ở Task 6 — nếu đường truy vấn cần ES mà `requirements.txt` không có client ES, hoặc ES không nằm trong Quick Start, đó là finding mức Cao (hệ thống có dependency hạ tầng ẩn).

- [x] **Step 4: Soi hợp đồng trả lời Q&A**

```bash
grep -rn "def " scripts/agent/tools/answer_qa.py | head -30
grep -rn "answer" tests/unit/test_qa_answer_contract.py | head -20
```

Mô tả **3 tầng trả lời + cross-check** bằng lời: tầng nào chạy trước, điều kiện xuống tầng sau, cross-check so cái gì với cái gì, và **chuyện gì xảy ra khi cả 3 tầng thất bại** (trả rỗng? bịa? trả chuỗi mặc định?). Đây là chỗ dễ sinh hallucination — nếu không có đường thoát an toàn rõ ràng ⇒ finding.

Ghi rõ ngoại lệ ngôn ngữ: prompt trong `qa_prompts.py` cố ý viết tiếng Anh, đổi một ký tự là đổi hành vi hệ thống. Đây là *ghi chú*, không phải finding.

- [x] **Step 5: Soi `trake_align.py` (pure, 102 dòng)**

Giải thích quy hoạch động đơn điệu (monotonic DP) và "rule-based plausibility" bằng lời + độ phức tạp. Kiểm: nó có thực sự pure không (dùng lệnh (a) ở Task 2 Step 3 cho file này), và [tests/unit/test_trake_align.py](../../tests/unit/test_trake_align.py) có phủ trường hợp **chuỗi sự kiện không tìm đủ frame** không.

- [x] **Step 6: Viết 12 mục + bảng tín hiệu bằng chứng**

Bảng đặt cuối §3: `| Tín hiệu | Module đọc | Nguồn dữ liệu (đường dẫn data/) | Sinh ra bởi (script offline) | On-demand hay precomputed |`. Cột "Sinh ra bởi" điền `?` nếu chưa xác định — Task 6 có nhiệm vụ quay lại đóng hết dấu `?`. Mọi `?` còn sót sau Task 6 là một finding "tín hiệu không rõ nguồn gốc".

- [x] **Step 7: Tự kiểm + commit**

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 33
grep -n "?" docs/reports/source-code-audit-2026-08-31.md | grep -c "Tín hiệu\|precomputed"   # ghi lai so dau ? con lai
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 3 tool nghiep vu — 12 file"
```

---

## Task 4: Chương 4 — Pipeline và cổng gọi LLM

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 4 điền -->`)
- Read: `scripts/agent/config.py` (263), `pipeline_kis.py` (122), `pipeline_qa.py` (230), `pipeline_trake.py` (305), `scripts/agent/__init__.py`, `scripts/agent/CLAUDE.md`

**Interfaces:**
- Consumes: sơ đồ lõi (Task 2), bảng tín hiệu bằng chứng (Task 3).
- Produces: §4 với 6 mục + **3 sơ đồ tuần tự** (một cho mỗi pipeline) mà Task 5 dùng để chỉ ra router nào gọi pipeline nào; danh sách đầy đủ **mọi call site của `call_llm`** kèm số vòng lặp tối đa — Task 10 dùng để tính chi phí/rủi ro.

- [x] **Step 1: Đọc `config.py` trước tiên**

Ghi lại chính xác: 3 chế độ `AIC_MODE` (`local` / `test` / `contest`) ánh xạ sang provider và biến môi trường nào; `MAX_AGENT_LOOPS` bằng bao nhiêu; có retry/timeout/fallback không; điều gì xảy ra khi thiếu API key.

```bash
grep -n "AIC_MODE\|LM_STUDIO\|OPENROUTER\|MAX_AGENT_LOOPS\|timeout\|retry\|fallback" scripts/agent/config.py
```

Kiểm hai điều [CLAUDE.md](../../../CLAUDE.md) khẳng định: (i) mode `local` **không có** fallback trả phí — nó phải fail loud khi LM Studio chết; (ii) `contest` dùng `OPENROUTER_MODEL_CONTEST`. Sai bất kỳ điều nào ⇒ finding mức Cao (rủi ro tiêu tiền âm thầm).

- [x] **Step 2: Liệt kê toàn bộ call site của `call_llm` + kiểm chặn vòng lặp**

```bash
grep -rn "call_llm" scripts --include=*.py | grep -v "def call_llm"
grep -rn "MAX_AGENT_LOOPS\|for _ in range\|while " scripts/agent/pipeline_qa.py scripts/agent/pipeline_trake.py scripts/agent/tools/answer_qa.py
```

Đã biết từ lúc lập kế hoạch: `call_llm` được gọi từ `pipeline_trake.py`, `answer_qa.py`, `qa_normalize.py`, `query_expand.py`, `rewrite.py`, `translate_raw.py`, và **`scripts/offline/ocr/vlm_ocr_caption.py`**. Hai điều phải kết luận:
- Mọi vòng reflection/retry có bị chặn bởi `MAX_AGENT_LOOPS` không? Vòng nào không bị chặn ⇒ finding mức Cao ([CLAUDE.md](../../../CLAUDE.md) DO NOT cấm vòng LLM không giới hạn).
- `query_expand.py` gọi `call_llm` **nhưng** [CLAUDE.md](../../../CLAUDE.md) xếp nó vào nhóm module **pure** ("no index, no model, no LLM, no I/O"). Nếu Task 2 Step 3 lệnh (a) và grep trên cùng xác nhận, đây là **mâu thuẫn tài liệu ↔ code** ⇒ finding: hoặc phân loại sai, hoặc `run_eval.py` đang tái dùng một hàm bí mật tốn tiền/không tất định. Kiểm thêm `run_eval.py` import gì từ `query_expand` (Task 7 xác nhận chéo).

- [x] **Step 3: Dựng 3 sơ đồ tuần tự**

Mỗi pipeline một khối ```mermaid `sequenceDiagram`, các bước theo đúng thứ tự gọi hàm trong code: nhận query → (rewrite?) → (expand?) → retrieve/hybrid → temporal_nms → rerank → (evidence?) → (LLM?) → kết quả. Ghi rõ bước nào **tốn LLM** và bước nào **tất định**.

- [x] **Step 4: Chỉ ra sự bất đối xứng giữa 3 pipeline**

Bảng `| Bước | KIS | Q&A | TRAKE |` với ô là ✔ / ✘ / tên hàm. Bắt buộc bàn tới:
- `pipeline_kis.py` cố ý **không** tự dịch VN→EN, trong khi Q&A/TRAKE có `rewrite.py`. [ARCHITECTURE.md](../../../ARCHITECTURE.md) nói đây là chủ ý. Nêu **hệ quả**: người dùng gõ tiếng Việt vào KIS sẽ nhận kết quả tệ hơn hẳn vì SigLIP mạnh nhất trên tiếng Anh, và UI có bù được không (Task 8 xác nhận). Đây là finding loại (b) *điểm yếu* nếu UI không bù.
- `pipeline_kis.py` chỉ 122 dòng còn `pipeline_trake.py` 305 dòng — chênh lệch này phản ánh gì.
- `rerank.py` import `build_submission` (phát hiện lúc lập kế hoạch qua grep). Kiểm bằng:
  ```bash
  grep -n "build_submission" scripts/agent/tools/rerank.py scripts/agent/pipeline_kis.py
  ```
  Một module *ranking* mà phụ thuộc module *serialize file nộp bài* là đảo ngược tầng — xác nhận rồi ghi finding về hướng phụ thuộc.

- [x] **Step 5: Viết 6 mục file + tự kiểm + commit**

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 39
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 4 pipeline va cong LLM — 6 file"
```

---

## Task 5: Chương 5 — Tầng API (FastAPI backend)

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 5 điền -->`)
- Read: `scripts/api/main.py`, `state.py`, `schemas.py` (113), `_smoke_test.py` (138), `__init__.py`, `CLAUDE.md`, `routers/__init__.py`, `routers/kis.py`, `qa.py`, `trake.py`, `queue.py` (75), `images.py`, `videos.py` (82)

**Interfaces:**
- Consumes: 3 sơ đồ tuần tự pipeline (Task 4).
- Produces: §5 với 13 mục + **bảng endpoint đầy đủ** (`| Method | Path | Router | Pipeline gọi tới | Có tốn LLM |`) — Task 8 đối chiếu bảng này với `frontend/src/api/client.ts` để tìm endpoint mồ côi hai chiều.

- [x] **Step 1: Trích toàn bộ endpoint bằng grep, rồi mới đọc file**

```bash
grep -rn "@router\.\(get\|post\|put\|delete\)\|@app\." scripts/api --include=*.py
grep -n "include_router\|prefix=" scripts/api/main.py
```

Bảng endpoint dựng từ output này, không dựng từ trí nhớ.

- [x] **Step 2: Đọc 13 file**

Thứ tự: `main.py` → `state.py` → `schemas.py` → 6 router → `_smoke_test.py` → 2 `__init__.py` → `CLAUDE.md`.

- [x] **Step 3: Kiểm 4 rủi ro đặc thù của tầng API**

```bash
# (a) API co bypass call_llm / build_submission khong? Ky vong: rong
grep -rn "litellm\|open(.*\.csv.*w\|to_csv\|ZipFile" scripts/api --include=*.py
# (b) index nap luc nao — import-time hay startup event? (bug "nap index 2 ban" da tung xay ra)
grep -rn "index_store\|get_index\|startup\|lifespan" scripts/api --include=*.py
# (c) state trong RAM: co khoa dong bo khong, co gioi han kich thuoc khong
grep -n "dict\|list\|global\|Lock\|session" scripts/api/state.py
# (d) xu ly loi: endpoint co bat exception va tra status ro rang khong
grep -rn "HTTPException\|try:\|except" scripts/api/routers --include=*.py | wc -l
grep -rLn "HTTPException" scripts/api/routers/*.py
```

Kết luận bắt buộc cho từng cái:
- (b) Nếu index nạp ở **import-time** thay vì `lifespan`/startup event, ghi finding và **nối thẳng** tới bug lịch sử "nạp index 2 bản" trong [docs/decisions-log.md](../../decisions-log.md) — đã sửa cho `scripts/` nhưng còn sót ở harness test tới tận 2026-08-31.
- (c) [CLAUDE.md](../../../CLAUDE.md) nói backend giữ state queue/session **trong RAM**. Nêu thẳng ba hệ quả: restart là mất sạch hàng đợi đang dựng; không chạy được nhiều worker uvicorn; không có khóa thì hai tab UI cùng sửa queue sẽ đua nhau. Đây là finding loại (b) *điểm yếu*, mức độ tùy vào việc thi đấu có dùng nhiều máy/nhiều tab không.
- (d) Router nào **không** có `HTTPException` (lệnh `grep -L`) ⇒ finding: lỗi rơi ra thành 500 trần, trái quy tắc "trong API endpoint, bắt lỗi và trả status rõ ràng".

- [x] **Step 4: Soi `images.py` và `videos.py` — hai router phục vụ file**

Trả lời: chúng phục vụ file từ đâu dưới `data/`, có kiểm đường dẫn không (path traversal: request `../../.env` thì sao), có giới hạn kích thước/stream không. Backend chỉ chạy localhost nên mức độ thường là Thấp, **nhưng vẫn phải ghi** vì đây là code phục vụ file theo tham số người dùng.

```bash
grep -n "Path\|resolve\|\.\.\|FileResponse\|StreamingResponse" scripts/api/routers/images.py scripts/api/routers/videos.py
```

- [x] **Step 5: Soi `_smoke_test.py`**

Nó nằm trong `scripts/api/` chứ không phải `tests/` — giải thích vì sao (cần API key + server đang chạy, không phải pytest tất định) và nêu cái giá: nó không bao giờ chạy trong `pytest tests/unit`, nên không ai phát hiện khi nó mục nát. Kiểm nó có còn khớp với bảng endpoint ở Step 1 không — endpoint nào smoke test **không** chạm tới ⇒ ghi vào cột trống của bảng.

- [x] **Step 6: Viết 13 mục + bảng endpoint + tự kiểm + commit**

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 52
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 5 tang API — 13 file"
```

---

## Task 6: Chương 6 — Nộp bài và tiền xử lý offline

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 6 điền -->`)
- Read (submit, 4): `scripts/submit/build_submission.py` (214), `validate_submission.py` (255), `__init__.py`, `CLAUDE.md`
- Read (offline, 25): `scripts/offline/CLAUDE.md`, `README.md`, `__init__.py`; `analysis/{__init__.py, analyze_frame_similarity.py}`; `captions/{__init__.py, build_caption_manifest.py, merge_captions.py, run_caption_shard_local.py}`; `ocr/{__init__.py, es_index.py, fetch_vietocr_assets.py, index_ocr_es.py, merge_ocr.py, run_ocr_shard_local.py, vlm_ocr_caption.py}`; `shards/{__init__.py, bundle_shards_self_contained.py, check_shards_status.py, download_all_shards.py, generate_sotuyen1_csv.py, generate_sotuyen2_csv.py, push_all_shards.py, setup_colab_shards.py, setup_kaggle_shards.py}`

**Interfaces:**
- Consumes: bảng tín hiệu bằng chứng của Task 3 (**phải đóng hết dấu `?` ở cột "Sinh ra bởi"**).
- Produces: §6 với 25 mục + **sơ đồ dòng dữ liệu offline** (script → file dưới `data/` → module runtime tiêu thụ). Task 9 nối tiếp sơ đồ này về phía GPU job.

- [x] **Step 1: Đọc 4 file `submit/` trước — đây là ranh giới đúng-sai của cuộc thi**

Với `build_submission.py`: định dạng CSV chính xác (cột, thứ tự, có header không), quy tắc đặt tên file, cấu trúc ZIP, số dòng tối đa. Với `validate_submission.py`: nó kiểm **những gì**, và quan trọng hơn — nó **không** kiểm gì.

```bash
grep -n "def \|columns\|header\|\.csv\|ZipFile\|max\|limit" scripts/submit/build_submission.py
grep -n "def \|assert\|raise\|check" scripts/submit/validate_submission.py
```

Câu hỏi phải trả lời dứt khoát: **validator có kiểm đủ mọi ràng buộc mà builder có thể vi phạm không?** Liệt kê ràng buộc từ [docs/rules/](../../rules/) mà validator bỏ sót ⇒ mỗi cái là một finding mức Cao (sai định dạng = mất điểm cả bài thi, và đây là loại lỗi chỉ lộ ra khi đã nộp).

- [x] **Step 2: Kiểm luật single-writer của file nộp bài**

```bash
grep -rn "to_csv\|csv.writer\|ZipFile\|\.zip" scripts tests --include=*.py | grep -v "scripts/submit/build_submission.py"
```

Bất kỳ chỗ nào ngoài `build_submission.py` ghi CSV/ZIP nộp bài ⇒ finding mức Cao. Lưu ý phân biệt: script ghi CSV **đề thi** (`generate_sotuyen1_csv.py`, `generate_sotuyen2_csv.py`) là hợp lệ, không phải file nộp bài — nêu rõ sự phân biệt này trong báo cáo để người đọc sau không báo động nhầm.

- [x] **Step 3: Đọc 21 file `offline/`, nhóm theo 4 thư mục con**

Mỗi thư mục con viết **một đoạn dẫn** trước các mục file: thư mục này sinh ra artifact gì, chạy một lần hay lặp lại, chạy ở đâu (máy dev / Kaggle / Colab).

Với nhóm `shards/` (9 file, ~2.000 dòng — lớn nhất `offline/`), trả lời: 9 script này là **một quy trình mạch lạc** hay là **các lần thử tích tụ lại**? Bằng chứng cần thu thập:

```bash
git log --oneline --diff-filter=A -- scripts/offline/shards/ | tail -20
grep -rn "def main\|if __name__" scripts/offline/shards/*.py
# setup_kaggle_shards.py (406) va setup_colab_shards.py (474) — trung lap bao nhieu?
diff <(grep -o "def [a-z_]*" scripts/offline/shards/setup_kaggle_shards.py) <(grep -o "def [a-z_]*" scripts/offline/shards/setup_colab_shards.py)
```

Nếu hai file setup trùng lặp phần lớn logic ⇒ finding loại (b): 880 dòng code sinh-job gần như song sinh, sửa một bên quên bên kia.

- [x] **Step 4: Truy vết Elasticsearch — dependency hạ tầng khả nghi**

```bash
grep -rn "elasticsearch\|Elasticsearch\|localhost:9200\|es_client" scripts tests --include=*.py
grep -in "elastic" requirements.txt README.md CLAUDE.md ARCHITECTURE.md
```

[CLAUDE.md](../../../CLAUDE.md) khẳng định "No database, no ORM, no message queue — everything is files". Nhưng có `es_index.py` và `index_ocr_es.py`. Xác định dứt khoát: đường truy vấn production có cần ES đang chạy không? Nếu **có** ⇒ finding mức Cao (tài liệu sai + hệ thống có dependency hạ tầng không được khai báo trong Quick Start). Nếu **không** (chỉ là nhánh thử nghiệm bỏ dở) ⇒ finding mức Trung bình (code chết còn nằm trong bucket production, gây hiểu nhầm cho người mới).

- [x] **Step 5: Đóng hết dấu `?` trong bảng tín hiệu bằng chứng**

Quay lại bảng cuối §3, điền cột "Sinh ra bởi" cho từng tín hiệu (OCR / Objects / ASR / caption). Dấu `?` nào không đóng được ⇒ ghi finding "tín hiệu runtime không truy được nguồn sinh" và nêu rõ đã tìm ở đâu.

- [x] **Step 6: Vẽ sơ đồ dòng dữ liệu offline**

```mermaid `flowchart TD`: script offline → artifact dưới `data/` (ghi tên đường dẫn thật) → module runtime đọc nó. Artifact nào **không** module runtime nào đọc ⇒ đánh dấu đỏ và ghi finding "tiền xử lý sinh ra dữ liệu không ai dùng".

- [x] **Step 7: Viết 29 mục + tự kiểm + commit**

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 81
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 6 nop bai va offline — 29 file"
```

---

## Task 7: Chương 7 — Kiểm thử và đo chất lượng

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 7 điền -->`)
- Read (gốc, 6): `tests/CLAUDE.md`, `README.md`, `conftest.py`, `data/sample_queries.json`, `data/sotuyen1_bo_de_thi.csv`, `data/thunghiem_bo_de_thi.csv`
- Read (e2e, 11): `e2e_baseline.json`, `eval_before_snapshot.md`, `golden_kis_snapshot.json`, `golden_kis_snapshot.py` (144), `score_pipelines.py` (350), `test_phase3_rerank.py`, `test_phase4_trake.py`, `test_phase5_ocr.py` (107), `test_phase6_margin_sweep.py` (126), `test_smoke_pipelines.py`, `test_smoke_tools.py`
- Read (eval, 14): `AUDIT_REPORT.md`, `EVAL_GUIDE.md`, `eval_ground_truth.json`, `eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`, `eval_ground_truth_thunghiem_draft.json`, `eval_ground_truth_v2_template.json`, `lookup_frame.py` (123), `normalize_gt.py` (303), `run_eval.py` (492), `split_eval_gt.py`, `sweep_rerank.py` (197), `widen_gt_windows.py` (116)
- Read (unit, 18): toàn bộ `tests/unit/test_*.py` (gồm cả `test_split_eval_gt.py`)

> **Cây làm việc đã đổi so với lúc khảo sát** (HEAD `8cc2615` → `a73b208`). `tests/eval/`
> có thêm 5 file và `tests/unit/` thêm 1. Dùng `git ls-files tests` để lấy danh sách
> **thật tại thời điểm chạy** thay vì tin danh sách trên; nếu lệch, danh sách thật thắng
> và ghi chú độ lệch vào đầu §7.

**Interfaces:**
- Consumes: bản đồ module của các Task 2–6 (để tính độ phủ theo module, không theo dòng).
- Produces: §7 + **ma trận phủ kiểm thử** `| Module production | Unit test | E2E test | Harness nào chạm tới hằng số của nó |` — Task 10 dùng làm bằng chứng chính cho chương điểm yếu.

- [x] **Step 1: Chạy thật bộ unit test và ghi output**

```bash
.venv\Scripts\python.exe -m pytest tests\unit -q
```

Chép nguyên dòng tổng kết (số pass/fail/skip, thời gian) vào báo cáo. **Không bình luận số liệu.** Test nào `skip` ⇒ ghi lý do skip.

- [x] **Step 2: Đối chiếu test ↔ module, tìm vùng trống**

```bash
for f in $(git ls-files 'scripts/agent/**/*.py' | grep -v __init__); do
  b=$(basename $f .py); n=$(grep -rl "$b" tests --include=*.py | wc -l)
  echo "$n  $f"
done | sort -n
```

Module có `0` ⇒ không test nào nhắc tên. Ứng viên đứng đầu danh sách (đã biết từ khảo sát): `index_store.py`, `hybrid.py`, `multi_index.py`, `retrieve.py`, `objects_lookup.py`, `frames.py` — tức **lõi truy hồi gần như không có unit test**, trong khi các module pure nhỏ (`fusion`, `temporal_nms`, `trake_align`) lại có. Xác nhận bằng output thật rồi ghi finding loại (b) mức Cao, nêu nguyên nhân cấu trúc: lõi cần `data/` nên khó test tất định, và hệ thống chưa có fixture index giả.

- [x] **Step 3: Phân loại 5 harness đo lường — chúng đo *cái gì* và *bỏ sót cái gì***

Bảng `| Harness | Chạm tới code nào | Cần data/ | Cần API key | Tất định | Đo được hằng số nào |` cho: `pytest tests/unit`, `golden_kis_snapshot.py --check`, `score_pipelines.py`, `run_eval.py`, `sweep_rerank.py`.

```bash
grep -n "^import\|^from" tests/eval/run_eval.py | head -30
grep -n "rerank\|MARGIN_THRESHOLD\|RECALL_HEAD_N" tests/eval/run_eval.py
grep -n "^import\|^from" tests/e2e/score_pipelines.py | head -30
```

Xác nhận cảnh báo trong [CLAUDE.md](../../../CLAUDE.md): `run_eval.py` **không** import `rerank.py`, nên tune `MARGIN_THRESHOLD` bằng nó là đo nhầm chỗ. Đây là finding loại (b) **mức Cao**: hệ thống có hai harness trông giống nhau, cái phổ biến hơn lại không chạm tới các hằng số hay bị chỉnh nhất — một cái bẫy có thật, và [CLAUDE.md](../../../CLAUDE.md) phải viết cả một mục cảnh báo chính là bằng chứng nó đã cắn người rồi.

- [x] **Step 4: Soi 6 file ground truth và quan hệ giữa chúng**

```bash
git status --short tests/eval/
for f in tests/eval/eval_ground_truth*.json; do
  echo -n "$f : "; python -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print(type(d).__name__, len(d))" "$f"
done
grep -rn "eval_ground_truth" scripts tests --include=*.py
```

Có **6** file ground truth cùng tồn tại: `eval_ground_truth.json` (bản hợp nhất), 3 bản tách `_kis` / `_qa` / `_trake` do `split_eval_gt.py` sinh, cùng `_thunghiem_draft` và `_v2_template`. Phải trả lời dứt khoát:

- File nào là **nguồn sự thật**, file nào là dẫn xuất? `split_eval_gt.py` sinh 3 bản tách từ bản hợp nhất, hay ngược lại?
- Ba bản tách có **được commit** không, tức là dẫn xuất bị check-in? Nếu có, chúng có thể lệch khỏi nguồn mà không ai biết ⇒ finding.
- `_thunghiem_draft` và `_v2_template` có script/test nào còn tham chiếu không (lệnh grep ở trên)? Nếu không ai dùng ⇒ finding "ground truth mồ côi", đặc biệt nguy hiểm ở thư mục ground truth vì người sau dễ sửa nhầm file chết.
- Bản hợp nhất phủ bao nhiêu query cho **mỗi** loại KIS / Q&A / TRAKE? Lệch nặng về KIS ⇒ finding: hai loại còn lại gần như không được đo.

- [x] **Step 4b: Đối chiếu với `tests/eval/AUDIT_REPORT.md` — báo cáo rà soát đã có sẵn**

Repo **đã có** một file tên `AUDIT_REPORT.md` trong `tests/eval/`. Đọc trọn nó và trả lời trong §7:

- Nó rà soát cái gì (chỉ ground truth, hay rộng hơn)? Phạm vi của nó có chồng lấn báo cáo này không?
- Kết luận của nó có còn đúng với code hiện tại không?
- Ghi vào cuối §7 một đoạn **"Quan hệ với AUDIT_REPORT.md có sẵn"** nêu rõ ranh giới: cái nào bao trùm cái nào, chỗ nào hai bên nói khác nhau. Nếu mâu thuẫn ⇒ finding. Task 10 sẽ nhắc lại ranh giới này trong tóm tắt điều hành để người đọc không tưởng đây là bản thay thế.

- [x] **Step 5: Soi `normalize_gt.py` (303) và `widen_gt_windows.py` (116)**

Hai script này **sửa ground truth**. Trả lời câu hỏi khó: nới cửa sổ ground truth làm điểm số tăng lên — có ranh giới nào ngăn việc nới cho tới khi số đẹp không? Có ghi lại tham số nới đã dùng ở đâu không? Nếu không ⇒ finding loại (b) mức Cao: thước đo có thể bị dịch chuyển mà không để lại dấu vết, khiến mọi so sánh lịch sử trong `docs/reports/` mất giá trị.

- [x] **Step 6: Viết 49 mục + ma trận phủ + tự kiểm + commit**

Với 18 file unit test, mỗi mục ngắn gọn nhưng **vẫn đủ 1 mục/file** — nêu nó khóa hành vi nào và có monkeypatch đúng module sở hữu hàm không (quy tắc trong [CLAUDE.md](../../../CLAUDE.md), đã từng sai).

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 130
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 7 kiem thu va do luong — 49 file"
```

---

## Task 8: Chương 8 — Frontend

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 8 điền -->`)
- Read (config/docs, 10): `frontend/CLAUDE.md`, `README.md`, `package.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `.oxlintrc.json`, `.gitignore`
- Read (src, 29): `main.tsx`, `App.tsx`, `session.ts`, `api/client.ts`, `types/chat.ts`, `mock/chatScenarios.ts`, `styles/{app.css, organic.css}`, `screens/{ChatScreen, KisScreen, QaScreen, QueueScreen, TrakeScreen}.tsx`, `components/{KeyframeDetail, QaKeyframeDetail, TrakeKeyframeDetail, RewriteChips, Thumb, TopKSlider, VideoVerifier}.tsx`, `components/chat/{AgentTraceAccordion, ChatBubble, ChatDrawer, ChatHeader, ChatInput, ChatTimeline, KisResultCards, QaResultBanner, TrakeSequenceView}.tsx`

**Interfaces:**
- Consumes: bảng endpoint của Task 5.
- Produces: §8 với 37 mục + **bảng đối chiếu hai chiều** endpoint backend ↔ lời gọi trong `client.ts`.

- [x] **Step 1: Đọc `client.ts` trước, rồi đối chiếu ngay với bảng endpoint Task 5**

```bash
grep -n "fetch\|/api/" frontend/src/api/client.ts
```

Dựng bảng `| Path | Backend có? | client.ts gọi? |`. Hai loại lệch, mỗi loại một finding:
- Endpoint backend **không** frontend nào gọi ⇒ code chết hoặc tính năng chưa nối dây.
- Lời gọi frontend **không** khớp endpoint backend nào ⇒ tính năng hỏng lúc chạy (TypeScript không bắt được vì URL là chuỗi).

- [x] **Step 2: Truy vết `mock/chatScenarios.ts` (161 dòng) — dữ liệu giả trong bundle production**

```bash
grep -rn "chatScenarios\|mock" frontend/src --include=*.tsx --include=*.ts | grep -v "mock/chatScenarios.ts"
```

Xác định: `ChatScreen.tsx` dùng mock hay dùng API thật? Có cờ bật/tắt không, hay mock được hardwire? Nếu màn Chat chạy bằng dữ liệu giả mà nhìn như thật ⇒ finding **mức Cao**: người dùng (và người demo trước ban giám khảo) có thể tưởng tính năng đã chạy. Nêu rõ mức độ hoàn thiện thật của màn Chat.

- [x] **Step 3: Kiểm bù trừ cho việc KIS không tự dịch**

Task 4 đã xác định `pipeline_kis.py` không tự dịch VN→EN. Kiểm frontend có bù không:

```bash
grep -rn "rewrite\|/api/rewrite\|dich\|translate" frontend/src --include=*.tsx --include=*.ts
```

Nếu `RewriteChips.tsx` cho người dùng chủ động dịch trước khi tìm ⇒ bù được, hạ mức finding của Task 4 xuống và **ghi rõ đã hạ vì lý do gì**. Nếu không ⇒ giữ nguyên và nâng thành finding chung của hệ thống.

- [x] **Step 4: Đánh giá cấu trúc, không đánh giá thẩm mỹ**

```bash
grep -c "useState" frontend/src/screens/*.tsx
grep -rn "useContext\|createContext\|zustand\|redux" frontend/src
wc -l frontend/src/styles/app.css frontend/src/styles/organic.css
```

Ba điều phải kết luận:
- 5 màn hình có **chia sẻ state** không, hay mỗi màn giữ state riêng? Nếu mỗi màn tự giữ, chuyển màn có mất kết quả tìm kiếm không ⇒ finding về UX/kiến trúc.
- `TrakeScreen.tsx` 377 dòng + `QaScreen.tsx` 285 dòng: có phải màn hình đang ôm cả logic gọi API lẫn render không (không có tầng hook riêng)?
- Hai file CSS 825 dòng tổng: `app.css` và `organic.css` chia theo tiêu chí gì, có chồng lấn không.

- [x] **Step 5: Kiểm quy ước ngôn ngữ ở frontend**

[CLAUDE.md](../../../CLAUDE.md) yêu cầu **UI text tiếng Việt có dấu**. Kiểm mẫu:

```bash
grep -rn "placeholder=\|>Search<\|>Submit<\|>Loading" frontend/src --include=*.tsx | head -30
```

Chuỗi UI tiếng Anh còn sót ⇒ finding mức Thấp, nhưng **liệt kê cụ thể file:line**, không nói chung chung.

- [x] **Step 6: Viết 39 mục + tự kiểm + commit**

10 file config viết ngắn (1–2 dòng/mục là đủ, nhưng vẫn phải có mục). 9 component trong `chat/` gộp cùng một đoạn dẫn rồi liệt kê từng mục.

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 169
wc -l docs/reports/source-code-audit-2026-08-31.md              # neu > 3000: ghi chu vao ledger, KHONG tu tach file
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 8 frontend — 39 file"
```

---

## Task 9: Chương 9 — Job GPU ngoài (Kaggle / Colab)

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 9 điền -->`)
- Read: `kaggle_jobs/CLAUDE.md`, `README.md`; 11 thư mục job (`01_vit_l14`, `02_siglip`, `02_siglip2`, `03_jina`, `04_dfn`, `05_qwen_vl_ocr_caption`, `06_paddleocr_ocr`, `06_paddleocr_ocr_shard0/1/2`, `07_vintern_caption`, `07_vintern_caption_shard0/1/2`, `_diag`) — mỗi thư mục gồm `main.py` + `kernel-metadata.json`; thêm `06_paddleocr_ocr/check_vietnamese*.py` (3 file); `colab_jobs/CLAUDE.md`

**Interfaces:**
- Consumes: sơ đồ dòng dữ liệu offline (Task 6) — chương này nối thêm đầu nguồn phía GPU.
- Produces: §9 + bảng `| Job | Model | Sinh ra artifact gì | Artifact đó có được dùng ở runtime không | Còn sống hay đã bỏ |`.

- [x] **Step 1: Đọc 2 file CLAUDE.md + README trước để hiểu quy ước job**

Lưu ý ràng buộc: **không được tự đẩy job GPU thật** ([CLAUDE.md](../../../CLAUDE.md)). Task này chỉ đọc.

- [x] **Step 2: Đối chiếu job ↔ `MODEL_REGISTRY` trong `multi_index.py`**

```bash
grep -n "MODEL_REGISTRY" -A 30 scripts/agent/tools/multi_index.py
ls kaggle_jobs/
```

Ánh xạ từng job sang tag backbone trong registry. Hai chiều đều là finding:
- Job đã chạy nhưng backbone **không** có trong registry ⇒ công GPU bỏ phí / thí nghiệm bỏ dở.
- Registry khai backbone mà **không** job nào sinh embedding ⇒ chọn tag đó lúc chạy sẽ hỏng.

- [x] **Step 3: Xác minh mâu thuẫn `colab_jobs/`**

```bash
git ls-files colab_jobs
grep -rn "colab_jobs" CLAUDE.md ARCHITECTURE.md scripts --include=*.md --include=*.py
```

`colab_jobs/` chứa 4 file được track: `CLAUDE.md` và **3 notebook** `06_paddleocr_vietocr_shard{0,1,2}/notebook.ipynb` — khớp với cách [CLAUDE.md](../../../CLAUDE.md) nhắc tới chúng. Câu hỏi cần trả lời (không giả định sẵn kết luận):

- 3 notebook này là artifact **viết tay và commit**, hay là **đầu ra sinh tự động** của `scripts/offline/shards/setup_colab_shards.py` (474 dòng)? Đọc script đó để xác định. Nếu là đầu ra sinh tự động mà vẫn check-in ⇒ finding: dẫn xuất bị commit, sẽ lệch khỏi generator mà không ai biết. Nếu viết tay ⇒ chỉ là *ghi chú*, nói rõ như vậy.
- 3 notebook có khác nhau ngoài chỉ số shard không? Dùng cùng phép đo ở Step 4.
- Đối chiếu với `kaggle_jobs/06_paddleocr_ocr_shard{0,1,2}/` — hai họ shard cùng làm PaddleOCR trên hai nền tảng. Có phải một cái đã thay thế cái kia mà bản cũ chưa được dọn không?

- [x] **Step 4: Đo mức trùng lặp giữa các job shard**

```bash
diff kaggle_jobs/06_paddleocr_ocr_shard0/main.py kaggle_jobs/06_paddleocr_ocr_shard1/main.py
diff kaggle_jobs/07_vintern_caption_shard0/main.py kaggle_jobs/07_vintern_caption_shard1/main.py
```

Nếu các shard chỉ khác nhau một hằng số chỉ số shard ⇒ finding loại (b): 6 bản sao gần như y hệt, sửa bug phải sửa 6 chỗ. Ghi rõ **số dòng khác nhau thật** từ output `diff`, không ước lượng.

- [x] **Step 5: Viết 39 mục + tự kiểm + commit**

Các job na ná nhau vẫn phải có **mục riêng** (cấm "tương tự trên"), nhưng mục có thể ngắn 3 dòng và trỏ tới đoạn dẫn chung của nhóm.

```bash
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md   # ky vong: 208
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 9 job GPU ngoai — 39 file"
```

---

## Task 10: Chương 10 — Tổng hợp bất hợp lý và điểm yếu + Tóm tắt điều hành

**Files:**
- Modify: `docs/reports/source-code-audit-2026-08-31.md` (thay `<!-- Task 10 điền -->`, và **chỉ** ở task này được sửa phần đầu file để chèn Tóm tắt điều hành + hoàn thiện mục lục)

**Interfaces:**
- Consumes: toàn bộ FINDING của Task 1–9, ma trận phủ kiểm thử (Task 7), bảng endpoint (Task 5), sơ đồ dòng dữ liệu (Task 6).
- Produces: chương cuối + tóm tắt điều hành. **Không phát sinh finding mới** — nếu trong lúc tổng hợp nảy ra phát hiện mới, phải quay lại chèn nó vào đúng mục file ở chương tương ứng rồi mới gom về đây.

- [x] **Step 1: Trích toàn bộ finding ra một chỗ**

```bash
grep -n "FINDING-" docs/reports/source-code-audit-2026-08-31.md | grep -v "xem FINDING"
grep -o "FINDING-[0-9]*" docs/reports/source-code-audit-2026-08-31.md | sort -u | wc -l
grep -c "Mức độ:\*\* Cao" docs/reports/source-code-audit-2026-08-31.md
```

Kiểm tính toàn vẹn: số liên tục, không nhảy cóc, không trùng. Số nào lệch ⇒ sửa tại chỗ trước khi viết tiếp.

- [x] **Step 2: Viết §10.1 — Bảng tổng hợp finding**

Bảng đầy đủ, sắp xếp **Cao → Trung bình → Thấp**, rồi theo số thứ tự:

`| # | Mức độ | Loại | Chương | File | Tóm tắt một dòng | Hệ quả nếu bỏ qua |`

Cột "Loại" chỉ nhận hai giá trị: `Bất hợp lý` (a) hoặc `Điểm yếu` (b).

- [x] **Step 3: Viết §10.2 — Điểm yếu hệ thống theo chủ đề**

Đây là phần có giá trị nhất của báo cáo. **Không** lặp lại bảng §10.1; mỗi chủ đề là một luận điểm, dẫn 2–4 finding làm bằng chứng, và nêu vì sao nhiều triệu chứng rời rạc lại cùng một gốc. Bắt buộc đủ 7 chủ đề (thêm được, không bớt):

1. **Invariant tuyên bố nhưng không được thực thi** — `frame_id +1` ở 3 nơi, luật "chỉ 4 bucket", luật on-demand OCR. Gốc rễ: mọi invariant chỉ sống trong tài liệu, không có test nào bảo vệ. Đề xuất kiểm chứng được, **viết ra dưới dạng đề xuất bằng văn bản**: một test `tests/unit/test_invariants.py` chạy chính các lệnh grep của báo cáo này. **KHÔNG tạo file đó** — ràng buộc read-only ở Global Constraints vẫn có hiệu lực; việc hiện thực hóa thuộc [PLAN.md](../../../PLAN.md).
2. **Lỗ hổng harness đo lường** — `run_eval.py` không chạm `rerank.py`; hằng số bị tune bằng thước đo sai chỗ; hai harness dễ nhầm lẫn.
3. **Lõi truy hồi gần như không có unit test** — module có test lại là module pure dễ nhất; module rủi ro nhất (`index_store`, `hybrid`, `multi_index`) không có. Nguyên nhân cấu trúc: thiếu fixture index giả.
4. **Suy biến âm thầm** — hybrid rơi về dense-only khi thiếu cache BM25; tín hiệu bằng chứng thiếu file thì bỏ qua lặng lẽ. Chung một dạng: hệ thống *vẫn trả kết quả* khi một nửa cơ chế đã chết, và không harness nào phân biệt được.
5. **Tài liệu trôi lệch khỏi code** — ES vs "no database"; `colab_jobs/`; `package-lock.json` ở root; `query_expand` bị gán nhãn pure. Gốc rễ: 4 file tài liệu điều hướng + 9 CLAUDE.md con, cập nhật thủ công, không cái nào được kiểm tự động.
6. **Trùng lặp bị nhân bản** — 6 job shard, 2 script setup Kaggle/Colab. Chi phí: mỗi lần sửa bug là N lần sửa, và N-1 cơ hội quên.
7. **Rủi ro vận hành ngày thi** — state queue trong RAM (restart là mất); màn Chat có thể đang chạy mock; validator có thể không phủ hết luật BTC; `.env` sai mode là tiêu tiền hoặc đo bằng model yếu.

- [x] **Step 4: Viết §10.3 — Ba câu hỏi rủi ro cao nhất, có kèm cách kiểm chứng**

Chọn đúng **3** finding nguy hiểm nhất cho kết quả thi đấu. Với mỗi cái, viết một khối:

```markdown
**Rủi ro N: <tên>**
- Bằng chứng: FINDING-xx, FINDING-yy
- Kiểm chứng trong 5 phút: `<lệnh chạy được>`
- Nếu đúng thì mất gì: <hậu quả cụ thể, đo được>
```

Không đề xuất giải pháp dài dòng — báo cáo này là chẩn đoán, không phải kế hoạch sửa. Việc sửa thuộc [PLAN.md](../../../PLAN.md).

- [x] **Step 5: Viết §10.4 — Những gì hệ thống làm ĐÚNG**

Bắt buộc có, để báo cáo cân bằng và đáng tin. Nêu 4–6 điểm, mỗi điểm dẫn bằng chứng cụ thể (ví dụ: tách module pure để eval tái dùng đúng thuật toán production; 4 bucket phân theo *thời điểm code chạy* thay vì theo chủ đề; `decisions-log.md` ghi cả sai lầm; ba chế độ `AIC_MODE` chống tiêu tiền nhầm). Một báo cáo chỉ toàn lỗi là báo cáo chưa đọc kỹ.

- [x] **Step 6: Chèn Tóm tắt điều hành + hoàn thiện mục lục**

Thay `<!-- TÓM TẮT ĐIỀU HÀNH — Task 10 điền -->` ở đầu file bằng **đúng 1 trang**: hệ thống làm gì, quy mô (số file / dòng theo tầng), tổng số finding chia theo mức độ, 3 rủi ro cao nhất (một dòng mỗi cái, link tới §10.3), và một câu đánh giá tổng thể về độ trưởng thành. Cập nhật mục lục thành link tới đủ 11 chương + các tiểu mục §10.1–§10.4.

- [x] **Step 7: Kiểm tra toàn vẹn lần cuối trên cả báo cáo**

```bash
# 1. Du 208 muc file?
grep -c "^#### " docs/reports/source-code-audit-2026-08-31.md
# 2. Doi chieu voi so file thuc te trong pham vi (dung dung luat loai tru o muc Pham vi)
EX='\.(jpg|jpeg|png|svg|pdf|pptx|npy|mp4)$|_archive|frontend/package-lock\.json'
echo $(( $(git ls-files scripts tests frontend kaggle_jobs colab_jobs | grep -Ev "$EX" | wc -l) + 11 ))
# 3. Khong con placeholder cam
grep -n "TODO\|TBD\|tương tự file trên\|xem mục trước\|sẽ bổ sung\|<!-- Task" docs/reports/source-code-audit-2026-08-31.md
# 4. Khong con link gay (kiem mau 20 duong dan dau tien)
grep -o "](\.\./\.\./[^)]*)" docs/reports/source-code-audit-2026-08-31.md | sed 's/](\.\.\/\.\.\///;s/)//' | sort -u | head -20 | while read p; do [ -e "$p" ] || echo "LINK GAY: $p"; done
# 5. FINDING lien tuc, khong trung
grep -o "FINDING-[0-9]*" docs/reports/source-code-audit-2026-08-31.md | sort -u
```

Kỳ vọng: (1) khớp (2) sau khi trừ các file đã loại trừ có ghi trong §0.2 — chênh lệch phải **giải thích được bằng danh sách loại trừ**, nếu không thì có file bị bỏ sót; (3) rỗng; (4) rỗng; (5) liên tục từ 01.

- [x] **Step 8: Commit**

```bash
git add docs/reports/source-code-audit-2026-08-31.md
git commit -m "docs(audit): chuong 10 tong hop diem yeu + tom tat dieu hanh"
```

---

## Self-Review (đã chạy khi viết plan)

**1. Spec coverage:**

| Yêu cầu trong spec | Task thực hiện |
|---|---|
| "đọc toàn bộ source code của dự án" | Task 1–9 phủ 120 file; Task 10 Step 7 lệnh (1)+(2) chứng minh không sót |
| "báo cáo chỉ ra chi tiết ý nghĩa từng file" | Schema §0.3 bắt buộc 1 mục/file, có trường **Vai trò**; cấm "tương tự file trên" |
| "báo cáo phải logic, chặt chẽ" | Bố cục theo tầng phụ thuộc; mọi phát biểu về quan hệ gọi nhau lấy từ output `grep`; Task 10 kiểm liên tục số finding + link gãy |
| "trong quá trình đọc… phát hiện phần không hợp lý thì chỉ ra rõ luôn" | Finding ghi **inline** tại mục file (schema §0.3), Task 10 chỉ gom lại — đúng yêu cầu "chỉ ra luôn" |
| "chỉ ra điểm yếu của hệ thống hiện tại" | §10.2 với 7 chủ đề bắt buộc + §10.3 ba rủi ro có cách kiểm chứng |

**2. Placeholder scan:** không có "TBD" / "thêm xử lý lỗi phù hợp" / "viết test cho phần trên". Mọi lệnh `grep`, `pytest`, `diff` đều viết đủ để dán chạy. Mục mẫu `hybrid.py` + FINDING-01 viết sẵn từ dữ liệu đã chạy thật, không phải minh họa giả.

**3. Type consistency:** tên file báo cáo `docs/reports/source-code-audit-2026-08-31.md` giống hệt ở cả 10 task. Tên trường schema (**Vai trò / Đầu vào / Đầu ra / Ai gọi nó / Điểm cần biết / FINDING**) không đổi giữa các task. Tập nhãn đóng (`pure`/`stateful`/`io`/`llm`/`http`/`cli`/`test`/`config`/`doc`/`ui`) định nghĩa một lần ở §Schema, Task 10 §10.2 dùng lại đúng tập đó. Số mục lũy kế kiểm ở mỗi task cộng dồn khớp: 11 → 21 → 33 → 39 → 52 → 81 → 130 → 169 → 208.

**Ba lỗ hổng đã bịt trong lúc self-review:**
- Task 1 ban đầu chỉ tạo §0 và §1; các task sau sẽ phải tự tìm chỗ chèn chương → đã đổi thành **tạo sẵn cả 11 heading + comment giữ chỗ** ở Task 1 Step 5.
- Bảng tín hiệu bằng chứng ở Task 3 có ô chưa biết → đã thêm cơ chế dấu `?` và giao Task 6 Step 5 đóng lại, kèm luật "`?` còn sót = finding".
- Phát hiện về KIS-không-tự-dịch (Task 4) có thể bị frontend bù trừ → đã thêm Task 8 Step 3 để xác nhận và hạ mức, tránh báo cáo kết luận sai vì đọc thiếu một tầng.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-31-source-code-audit-report.md`.**
