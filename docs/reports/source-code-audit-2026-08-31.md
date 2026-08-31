# Báo cáo Rà soát Source Code — Hệ thống AIC2026

<!-- TÓM TẮT ĐIỀU HÀNH — Task 10 điền -->

- **Ngày:** 2026-08-31
- **Commit:** `7d7bcea`
- **Nhánh:** `fix/phase2`

Báo cáo này đọc từng file source trong phạm vi (xem §0.2), giải thích vai trò của nó, và ghi lại
mọi điểm bất hợp lý / điểm yếu phát hiện được dưới dạng `FINDING-nn` (đánh số liên tục toàn báo cáo).
Mọi phát biểu về hành vi đều lấy từ việc đọc code hoặc chạy lệnh, không suy từ tên file và không suy
từ tài liệu; khi code mâu thuẫn tài liệu thì chính điều đó là finding.

### Mục lục

- [0. Bối cảnh, phạm vi và phương pháp](#0-bối-cảnh-phạm-vi-và-phương-pháp)
- [1. Tầng gốc: tài liệu điều hướng và cấu hình](#1-tầng-gốc-tài-liệu-điều-hướng-và-cấu-hình)
- [2. Lõi truy hồi (retrieval core)](#2-lõi-truy-hồi-retrieval-core)
- [3. Tool nghiệp vụ: Q&A, TRAKE, bằng chứng](#3-tool-nghiệp-vụ-qa-trake-bằng-chứng)
- [4. Tầng pipeline và cổng gọi LLM](#4-tầng-pipeline-và-cổng-gọi-llm)
- [5. Tầng API (FastAPI backend)](#5-tầng-api-fastapi-backend)
- [6. Tầng nộp bài và tiền xử lý offline](#6-tầng-nộp-bài-và-tiền-xử-lý-offline)
- [7. Tầng kiểm thử và đo chất lượng](#7-tầng-kiểm-thử-và-đo-chất-lượng)
- [8. Frontend (React + Vite)](#8-frontend-react--vite)
- [9. Job GPU ngoài (Kaggle / Colab)](#9-job-gpu-ngoài-kaggle--colab)
- [10. Tổng hợp: bất hợp lý và điểm yếu hệ thống](#10-tổng-hợp-bất-hợp-lý-và-điểm-yếu-hệ-thống)

## 0. Bối cảnh, phạm vi và phương pháp

### 0.1. Hệ thống này là gì

AIC2026 là hệ thống **truy hồi frame video bằng ngôn ngữ tự nhiên** cho Hội thi Thử thách Trí tuệ
Nhân tạo TP.HCM 2026. Đầu vào là một câu mô tả sự kiện (tiếng Việt hoặc tiếng Anh); đầu ra tuỳ theo
ba loại truy vấn: **KIS** (Known-Item Search) trả về danh sách xếp hạng 100 dòng `video_id` +
`frame_id` cho một khoảnh khắc cụ thể; **Q&A** trả về frame mục tiêu kèm một `answer` cho câu hỏi nội
dung; **TRAKE** trả về một chuỗi `frame_id` theo đúng thứ tự thời gian cho N mốc sự kiện. Hệ thống
gồm một retriever dùng chung (ma trận embedding SigLIP / SigLIP 2 trên ~177K keyframe), ba pipeline
riêng cho KIS/Q&A/TRAKE, một tầng agent LLM cho Q&A và TRAKE, và bộ dựng + validate file nộp CSV/ZIP.
Chấm điểm theo công thức BTC: với mỗi truy vấn, `R@k` là chỉ báo có ít nhất một dòng đúng trong k
dòng đầu; **Final Score = (1/5) · Σ R@k** với `k ∈ {1, 5, 20, 50, 100}`, lấy trung bình trên toàn bộ
truy vấn. Vì `R@k` là hàm `max` trên k dòng đầu, chỉ cú trúng đầu tiên có giá trị và việc xếp đúng
20 dòng đầu quan trọng hơn hẳn 80 dòng còn lại.

### 0.2. Phạm vi và loại trừ

**Luật tính phạm vi** (viết một lần, mọi phép đếm dùng đúng nó):

> In-scope = file được `git ls-files` track, **trừ** phần mở rộng media/binary
> (`.jpg .jpeg .png .svg .pdf .pptx .npy .mp4`), **trừ** mọi đường dẫn chứa `_archive`,
> **trừ** `frontend/package-lock.json`, **trừ** các thư mục `.agents/ .superpowers/ .claude/ docs/
> data/ submissions/` — **cộng** đúng hai ngoại lệ tái đưa vào: `package-lock.json` ở root và
> `docs/decisions-log.md`.

Lệnh tái lập (chạy tại commit `7d7bcea`):

```
EX='\.(jpg|jpeg|png|svg|pdf|pptx|npy|mp4)$|_archive|frontend/package-lock\.json'
git ls-files scripts tests frontend kaggle_jobs colab_jobs | grep -Ev "$EX" | wc -l   # 197
# + 11 file tầng gốc của Task 1 = 208
```

**Trong phạm vi — 208 file:**

| Nhóm | Số file | Chương | `####` lũy kế sau chương |
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

**Ngoài phạm vi — lý do loại trừ từng nhóm:**

- `.agents/`, `.superpowers/`, `.claude/` — cấu hình agent của công cụ khác (Antigravity) và cache
  plugin / ghi chú SDD cục bộ, không phải hệ thống retrieval. [CLAUDE.md](../../CLAUDE.md#L108) yêu
  cầu không coi `.agents/` là chỉ dẫn cho Claude Code.
- `data/`, `submissions/*.zip` — state ngoài, git-ignored, không có trong repo (xem
  [.gitignore](../../.gitignore#L4) và [.gitignore](../../.gitignore#L12)).
- `docs/` — tài liệu tham khảo, **trừ** `docs/decisions-log.md` được kéo vào chương 1 vì nó ghi lịch
  sử quyết định và sai lầm, là bằng chứng trực tiếp cho chương 10.
- `docs/_archive/`, `kaggle_jobs/_archive_logs_20260819/` — bản bị thay thế, giữ để tra cứu lịch sử.
- `frontend/package-lock.json`, `frontend/public/*.svg`, các file `.jpg` sinh ra dưới
  `scripts/offline/` — lockfile sinh tự động (nằm trong toolchain riêng của `frontend/`) và file
  media/binary.
- `package-lock.json` ở **root** thì **ngược lại — nằm TRONG phạm vi** (chương 1), vì sự tồn tại của
  nó ở root mâu thuẫn với tuyên bố "toolchain Node chỉ sống trong `frontend/`". Nó là đối tượng cần
  giải thích, không phải file cần bỏ qua — xem FINDING-01.

**Vì sao báo cáo nằm ở `docs/reports/`:** [CLAUDE.md](../../CLAUDE.md#L110) mô tả `docs/reports/` là
nơi chứa "generated eval numbers". Báo cáo này là tài liệu sinh ra từ phân tích source, gần bucket đó
nhất; không tạo một bucket `docs/` mới cho một file duy nhất. Người đọc lưu ý: đây **không** phải số
liệu eval — mọi con số eval được trích trong báo cáo đều kèm nguồn và không kèm nhận xét chất lượng.

### 0.3. Cách đọc một mục file

Mỗi file trong phạm vi có **đúng một** mục theo schema cố định dưới đây. Mọi chương 1→9 dùng đúng
schema này, không biến tấu, không thêm/bớt trường. (Dòng tiêu đề `####` trong khối ví dụ bên dưới
được thụt lề để phép đếm `grep -c "^#### "` luôn bằng đúng số file đã viết — mục file **thật** đặt
`####` ở đầu dòng.)

```markdown
    #### [`<tên file>`](<đường dẫn tương đối>) — `<n>` dòng · `<nhãn>`

- **Vai trò:** một câu, nói *nó tồn tại để làm gì*, không mô tả lại tên file.
- **Đầu vào:** import nội bộ (dạng `scripts.…`), thư viện ngoài, file dưới `data/`, biến môi trường.
- **Đầu ra:** giá trị trả về / file ghi ra / endpoint expose.
- **Ai gọi nó:** liệt kê file gọi tới, lấy từ `grep`, không đoán. Không ai gọi → ghi thẳng "Không
  file nào import — xem FINDING-nn".
- **Điểm cần biết:** 1–3 gạch đầu dòng: hằng số đã tune, invariant, thuật toán chính, cạm bẫy.
- **⚠️ FINDING-nn (Mức độ):** chỉ xuất hiện khi có phát hiện. Đủ 4 phần: Hiện trạng (file:line) · Vì
  sao bất hợp lý · Hệ quả thực tế · Mức độ.
```

`<nhãn>` chọn từ **tập đóng** (để chương 10 thống kê được), nối nhiều nhãn bằng `+`:

`pure` (không I/O, không model, không LLM) · `stateful` (giữ singleton/cache) · `io` (đọc/ghi
`data/`) · `llm` (gọi `call_llm`) · `http` (endpoint) · `cli` (có `__main__`) · `test` · `config` ·
`doc` · `ui`.

Ba loại nhận xét được phân biệt rạch ròi, không trộn: **(a) Bất hợp lý** — code tự mâu thuẫn hoặc
mâu thuẫn tài liệu; **(b) Điểm yếu hệ thống** — code đúng như thiết kế nhưng thiết kế có rủi ro;
**(c) Ghi chú** — quan sát trung tính. Chỉ (a) và (b) được đánh số `FINDING`.

### 0.4. Bản đồ chương ↔ nhóm file ↔ số file

| Chương | Nội dung | Nhóm file | Số file | `####` lũy kế |
|---|---|---|---|---|
| 1 | Tầng gốc: tài liệu điều hướng + cấu hình | 11 file ở repo root (+ `docs/decisions-log.md`) | 11 | 11 |
| 2 | Lõi truy hồi | `scripts/agent/tools/` — retrieval core | 10 | 21 |
| 3 | Tool nghiệp vụ | `scripts/agent/tools/` — Q&A / TRAKE / evidence | 12 | 33 |
| 4 | Pipeline + cổng LLM | `scripts/agent/` — `config.py`, `pipeline_*.py`, `__init__`, `CLAUDE.md` | 6 | 39 |
| 5 | Tầng API | `scripts/api/` | 13 | 52 |
| 6 | Nộp bài + offline | `scripts/submit/` (4) + `scripts/offline/` (25) | 29 | 81 |
| 7 | Kiểm thử + đo chất lượng | `tests/` | 49 | 130 |
| 8 | Frontend | `frontend/` | 39 | 169 |
| 9 | Job GPU ngoài | `kaggle_jobs/` (35) + `colab_jobs/` (4) | 39 | 208 |

## 1. Tầng gốc: tài liệu điều hướng và cấu hình

Chương này rà 11 file ở repo root (kèm `docs/decisions-log.md` được kéo vào theo luật phạm vi §0.2).
Đây là "khế ước làm việc" của repo: chúng quy định 4 bucket dưới `scripts/`, các luật single-call-site
(LLM, ghi file nộp bài, quy đổi `frame_id`), quy ước ngôn ngữ, và danh sách DO NOT. Vì không có file
nào ở đây chạy trên đường truy vấn, "hành vi" của chúng là *nội dung tài liệu* và *cấu hình build* —
và mọi phát hiện ở chương này là dạng **tài liệu mâu thuẫn tài liệu** hoặc **tài liệu mâu thuẫn cây
file thật**.

Sáu phát biểu kiểm chứng được mà tài liệu đưa ra (input cho các chương sau), kèm kết quả chạy lại
lệnh xác minh tại commit `7d7bcea`:

| # | Phát biểu | Nguồn | Kết quả chạy lại |
|---|---|---|---|
| 1 | `call_llm()` trong `scripts/agent/config.py` là nơi **duy nhất** gọi litellm | [CLAUDE.md:179](../../CLAUDE.md#L179) | `grep -rn "litellm" scripts tests` (trừ `config.py`) → **rỗng**. Đúng như tài liệu. |
| 2 | `row_to_hit()` trong `index_store.py` là nơi **duy nhất** tính `frame_id = frame_idx + 1` | [CLAUDE.md:155](../../CLAUDE.md#L155) | `grep -rn "frame_idx + 1"` → có **dòng code** ở [hybrid.py:156](../../scripts/agent/tools/hybrid.py#L156) và [multi_index.py:78](../../scripts/agent/tools/multi_index.py#L78) ngoài `index_store.py:150`. **Vi phạm** — bàn giao cho chương 2 (xem cuối FINDING-03). |
| 3 | `build_submission.py` là nơi duy nhất ghi CSV/ZIP nộp bài | [CLAUDE.md:180](../../CLAUDE.md#L180) | `grep -rln "build_submission"` → import bởi `scripts/agent/pipeline_kis.py`, `scripts/agent/tools/rerank.py`, `scripts/api/routers/queue.py`, `tests/e2e/test_smoke_pipelines.py`. Việc `rerank.py` (module ranking) import module serialize là bất đối xứng tầng — bàn giao cho chương 4. |
| 4 | `fusion.py` / `temporal_nms.py` / `query_expand.py` / `trake_align.py` là module **pure** | [CLAUDE.md:100](../../CLAUDE.md#L100), [ARCHITECTURE.md:54](../../ARCHITECTURE.md#L54) | `grep -n "^import\|^from" … | grep -E "torch|transformers|litellm|index_store|pandas|numpy"` → **rỗng**. Không import nặng. Lưu ý: [ARCHITECTURE.md:56](../../ARCHITECTURE.md#L56) tự nhận `query_expand.py` có "nhánh LLM tuỳ chọn" — mâu thuẫn với nhãn "no LLM" của [CLAUDE.md:100](../../CLAUDE.md#L100); bàn giao xác minh cho chương 2/4. |
| 5 | Chỉ repo root nằm trên `sys.path`; không bao giờ đặt `scripts/` lên `sys.path` | [CLAUDE.md:148](../../CLAUDE.md#L148) | `grep -rn "sys.path"` → chỉ có `setup_colab_shards.py` (đẩy `/content/paddle_pkgs_isolated`, không phải `scripts/`) và `tests/e2e/test_phase6_margin_sweep.py` (đẩy repo root + `tests/e2e/`). Đúng như tài liệu. |
| 6 | `scripts/` có **đúng 4** bucket: `agent/`, `api/`, `submit/`, `offline/` | [CLAUDE.md:57](../../CLAUDE.md#L57) | `git ls-files scripts | cut -d/ -f2 | sort -u` → `agent api offline submit`. Đúng như tài liệu. |

#### [`README.md`](../../README.md) — 422 dòng · `doc`

- **Vai trò:** trang giới thiệu hướng ra ngoài (giám khảo / người mới clone) — mô tả bài toán, kiến
  trúc tổng thể, tech stack, cấu trúc thư mục, cách cài đặt & chạy, pipeline từng loại, bảng benchmark
  backbone, và thông tin đội thi.
- **Đầu vào:** không có (file người đọc). Trỏ tới `requirements.txt`, `.env.example`, và ngầm định
  các script dưới `scripts/` và `tests/`.
- **Đầu ra:** không có artifact máy sinh.
- **Ai gọi nó:** không file code nào import; là điểm vào cho người đọc. GitHub render mặc định.
- **Điểm cần biết:**
  - Đối tượng đọc khác [CLAUDE.md](../../CLAUDE.md): README là "brochure" (có mục lục, emoji, bảng
    thành viên, giấy phép); CLAUDE.md là khế ước vận hành cho agent. Nội dung chồng lấn ở phần tech
    stack và cấu trúc thư mục.
  - README §8 trích số benchmark backbone (ví dụ `SigLIP SO400M` Final `0.549`, `SigLIP 2` Final
    `0.551`) — các số này được chép nguyên, không kèm nhận xét chất lượng theo quy ước
    [CLAUDE.md](../../CLAUDE.md#L200) về số liệu eval.
  - README §2 và §5 nhắc "RAM tối thiểu 8GB / khuyên 16GB" và "`torch` (CPU build)" — nhất quán với
    `requirements.txt` nhưng **không** nhất quán với [CLAUDE.md:121](../../CLAUDE.md#L121) (xem
    FINDING-05).

- **⚠️ FINDING-03 (Trung bình):** [README.md:372](../../README.md#L372) ("chỉ chuyển đổi tại duy
  nhất `retrieve.py`") mâu thuẫn với sơ đồ cây ngay trong chính README ở
  [README.md:138](../../README.md#L138) ("`index_store.py` … ĐIỂM DUY NHẤT quy đổi frame_id"). Nội
  dung đầy đủ của finding này (dùng chung cho README + ARCHITECTURE.md + GEMINI.md, kèm bàn giao
  chương 2) ghi ở mục `ARCHITECTURE.md` bên dưới.

#### [`CLAUDE.md`](../../CLAUDE.md) — 211 dòng · `doc`

- **Vai trò:** khế ước làm việc cho Claude Code — "stable, day-to-day facts": cách chạy, nơi file
  được đặt, quy ước cần theo. Cố ý **không** ghi tiến độ hay lịch sử (đẩy sang PLAN.md /
  decisions-log.md).
- **Đầu vào:** không có. Được nạp tự động mỗi phiên Claude Code (project instructions).
- **Đầu ra:** không có.
- **Ai gọi nó:** không file code nào import; Claude Code nạp như chỉ dẫn.
- **Điểm cần biết:**
  - Định nghĩa **4 bucket** dưới `scripts/` theo *khi code chạy* (`agent` runtime · `api` HTTP ·
    `submit` serialize · `offline` chạy-một-lần), và cấm thêm bucket thứ năm ([CLAUDE.md:57](../../CLAUDE.md#L57)).
  - Ba luật **single-call-site**: litellm chỉ ở `config.py:call_llm()`
    ([CLAUDE.md:179](../../CLAUDE.md#L179)); ghi CSV/ZIP nộp bài chỉ ở `build_submission.py`
    ([CLAUDE.md:180](../../CLAUDE.md#L180)); quy đổi `frame_id = frame_idx + 1` chỉ ở
    `index_store.py:row_to_hit()` ([CLAUDE.md:155](../../CLAUDE.md#L155)).
  - Quy ước ngôn ngữ: comment/UI tiếng Việt **có dấu** toàn `scripts/`; ngoại lệ duy nhất là prompt
    LLM trong `qa_prompts.py` và crosscheck của `pipeline_trake.py` (tiếng Anh — đổi ký tự là đổi
    hành vi) ([CLAUDE.md:142](../../CLAUDE.md#L142)).
  - `sys.path`: chỉ repo root; đặt `scripts/` lên `sys.path` từng cắn 3 lần
    ([CLAUDE.md:148](../../CLAUDE.md#L148)).
  - Mục **DO NOT**: không gọi litellm ngoài `call_llm()`; không ghi file nộp bài ngoài
    `build_submission.py`; không commit `.env` / key thật vào `.env.example`; không vòng LLM vô hạn
    (`MAX_AGENT_LOOPS`); không precompute OCR/VLM cho 177K keyframe trên đường truy vấn; không
    force-push `main`.

- **⚠️ FINDING-05 (Trung bình):**
  - **Hiện trạng:** [CLAUDE.md:121](../../CLAUDE.md#L121) ghi `torch` là "CUDA build `2.8.0+cu129`;
    the machine has an RTX 5050 Laptop, sm_120, 8 GB VRAM" như một sự thật hiện hành, trong khi
    [requirements.txt:8](../../requirements.txt#L8) ghim `torch==2.13.0+cpu`. Khác cả số phiên bản
    (2.8.0 vs 2.13.0) lẫn build (`+cu129` vs `+cpu`).
  - **Vì sao bất hợp lý:** [ARCHITECTURE.md:213](../../ARCHITECTURE.md#L213) và
    [PLAN.md:177](../../PLAN.md#L177) đều nói rõ trạng thái **hiện tại** là `torch 2.13.0+cpu`, "GPU
    chưa từng được dùng", và bản CUDA mới chỉ là việc **kế hoạch** (Phase 10.0, checkbox chưa tick).
    CLAUDE.md — tài liệu tự nhận chỉ chứa "stable, day-to-day facts" — lại trình bày bản CUDA như đã
    cài xong.
  - **Hệ quả thực tế:** người đọc CLAUDE.md tin GPU đã sẵn sàng và tinh chỉnh theo giả định đó; số
    `2.8.0+cu129` cũng không khớp dòng `2.13.0` requirements đang ghim nên không dùng được để tái lập
    môi trường; agent theo CLAUDE.md có thể bỏ bước dựng `.venv-gpu/` mà PLAN.md Phase 10.0 bắt buộc.
  - **Mức độ:** Trung bình.

#### [`ARCHITECTURE.md`](../../ARCHITECTURE.md) — 289 dòng · `doc`

- **Vai trò:** mô tả thiết kế hệ thống — sơ đồ luồng dữ liệu, trách nhiệm từng module, **bảng tham số
  đã hiệu chỉnh** (và hiệu chỉnh trên thang đo nào), các quyết định kiến trúc đã chốt, danh sách
  forbidden, điểm giao tiếp interface, và toàn bộ "Kiến trúc v2" (Phase 10) chưa triển khai.
- **Đầu vào:** không có. Trỏ tới [PLAN.md](../../PLAN.md), [CLAUDE.md](../../CLAUDE.md),
  [docs/decisions-log.md](../decisions-log.md).
- **Đầu ra:** không có.
- **Ai gọi nó:** không file code nào import.
- **Điểm cần biết:**
  - Khác CLAUDE.md ở *mức trừu tượng*: CLAUDE.md = quy ước hằng ngày (chạy lệnh gì, đặt file ở đâu);
    ARCHITECTURE.md = *vì sao* thiết kế thế này (chọn 3 pipeline riêng thay vì 1 agent chung; margin
    tương đối thay vì ngưỡng tuyệt đối; DP thay greedy cho TRAKE).
  - §2.1 là bảng tham số tune kèm cảnh báo quan trọng: `rerank.MARGIN_THRESHOLD = 0.012` được hiệu
    chỉnh trên cosine của `clip_vitb32` — **model đã retire 2026-08-28**; `RECALL_HEAD_N = 20`,
    `SPARSE_TOP_K = 50`, `RRF_K = 60`, `MIN_TIME_GAP = 3.0s`, `GATE_MARGIN = 0.02`,
    `MAX_ANSWER_CLUSTERS = 3`. Chương 2 và 4 xác minh các hằng số này trong code.
  - §5 ghi hai phụ thuộc ngoài chưa kiểm soát: `ocr_read.py` tải config VietOCR từ `vocr.vn` (SSL hết
    hạn → OCR thật "hiện KHÔNG hoạt động"), và LLM qua `PROVIDER_CHAIN` trong `config.py`.
  - §6 ("Kiến trúc v2") mô tả 4 module **chưa tồn tại** (`refine_frame.py`, `vlm_rerank.py`,
    `model_registry.py`, `text_index.py`) — chương 2–4 phải phân biệt module thật với module kế hoạch.

- **⚠️ FINDING-03 (Trung bình):**
  - **Hiện trạng:** [README.md:372](../../README.md#L372) ("chỉ chuyển đổi tại duy nhất `retrieve.py`"),
    [ARCHITECTURE.md:123](../../ARCHITECTURE.md#L123) ("ngay tại `retrieve.py` (điểm duy nhất)") và
    [GEMINI.md:80](../../GEMINI.md#L80) ("chỉ chuyển đổi tại `retrieve.py`") đều nói phép
    `frame_id = frame_idx + 1` xảy ra ở `retrieve.py`. Dòng code thật (grep toàn `scripts/`) nằm ở
    [index_store.py:150](../../scripts/agent/tools/index_store.py#L150) trong `row_to_hit()`;
    [retrieve.py:6](../../scripts/agent/tools/retrieve.py#L6) chỉ có comment mô tả, không có dòng
    code. Cùng lúc [CLAUDE.md:155](../../CLAUDE.md#L155), [ARCHITECTURE.md:136](../../ARCHITECTURE.md#L136)
    và sơ đồ cây trong [README.md:138](../../README.md#L138) lại nói đúng là `index_store.py:row_to_hit()`.
    README và ARCHITECTURE **tự mâu thuẫn với chính chúng** (§ khác nhau chỉ tên file khác nhau).
  - **Vì sao bất hợp lý:** `retrieve.py` là tên từ trước "Pha chuẩn hoá repo" — [PLAN.md:314](../../PLAN.md#L314)
    ghi `retrieve.py` đã được tách thành `index_store` + `retrieve` + `hybrid` + `frames`; ba tài
    liệu chưa cập nhật sau khi tách. Đây là invariant được canh gác gắt nhất repo mà tài liệu điều
    hướng lại trỏ nhầm file.
  - **Hệ quả thực tế:** người sửa code tin README/ARCHITECTURE §3 sẽ mở nhầm file; tệ hơn, tưởng
    `retrieve.py` "thiếu" phép +1 rồi tự thêm vào ⇒ cộng đôi `frame_id`, sai lệ ra chỉ ở file nộp.
  - **Mức độ:** Trung bình.
  - **Bàn giao chương 2:** vi phạm ở **tầng code** — hai chỗ tự tính `frame_idx + 1` ngoài
    `row_to_hit()`: [hybrid.py:156](../../scripts/agent/tools/hybrid.py#L156) và
    [multi_index.py:78](../../scripts/agent/tools/multi_index.py#L78) — là finding riêng của chương 2,
    không ghi ở chương này.

#### [`PLAN.md`](../../PLAN.md) — 428 dòng · `doc`

- **Vai trò:** theo dõi tiến độ theo từng Phase (cột mốc lớn) — mỗi phiên làm việc đọc Phase đang
  `🔄/⏳` và mục Blockers trước.
- **Đầu vào:** không có. Trỏ tới [ARCHITECTURE.md](../../ARCHITECTURE.md),
  [docs/decisions-log.md](../decisions-log.md), và nhiều plan trong `docs/superpowers/plans/`.
- **Đầu ra:** không có.
- **Ai gọi nó:** không file code nào import.
- **Điểm cần biết:**
  - **Phase hiện tại:** "Pha 2 — Sửa lỗi hành vi" trên nhánh `fix/phase2`, mục "Bàn giao Pha 2
    (Hoàn tất 2026-08-31)" — tức Pha 2 vừa đóng. Kết quả sau Pha 2 được trích nguyên: **KIS Final
    0.652**, **TRAKE Final 0.430**, **Q&A Final 0.360**, golden digest `a67ade7f22d881cf`, 89/89
    unit test pass. Việc tiếp theo (Pha 3) là gán nhãn Ground Truth mở rộng ≥100 câu KIS.
  - "Pha chuẩn hoá repo (2026-08-31) — ✅ XONG" đã đưa `scripts/` về 4 bucket, tách `retrieve.py` /
    `answer_qa.py`, đổi `ocr_lookup.py` → `objects_lookup.py`, chuyển `test_eval/` → `tests/`.
  - Phase 10 ("Kiến trúc v2") là danh sách 10 hạng mục **chưa tick** — chương 10 của báo cáo cần đối
    chiếu "điểm yếu phát hiện" với "đã có kế hoạch xử lý chưa" ở đây.
  - Mục **Blockers / Risks** ghi 6 rủi ro đang mở, gồm: độ dài thật của cửa sổ đáp án `[s,e]` KIS là
    ẩn số; xung đột DLL `paddlepaddle` × `torch-CUDA` chưa kiểm chứng lại; mọi tham số đang chốt trên
    33 câu GT (Regression Guard "là guard giả"); phụ thuộc **một** LLM provider (OpenRouter) — chính
    là nguyên nhân mất điểm đợt 1.
  - "Lịch sử" ghi đợt 1 nộp **5.6/10** với nguyên nhân chính là "cạn quota Gemini free-tier giữa lúc
    thi" (số + nguyên nhân chép nguyên).

#### [`GEMINI.md`](../../GEMINI.md) — 91 dòng · `doc`

- **Vai trò:** chỉ dẫn tự-nạp cho Antigravity (một coding agent khác) — bản song song, rút gọn của
  CLAUDE.md.
- **Đầu vào:** không có. Nạp on-demand các skill dưới `.agents/skills/` (ngoài phạm vi báo cáo).
- **Đầu ra:** không có.
- **Ai gọi nó:** không file code nào import. Bị loại khỏi context của Claude Code bởi
  [.claudeignore:74](../../.claudeignore#L74).
- **Điểm cần biết:**
  - [CLAUDE.md:108](../../CLAUDE.md#L108) mô tả GEMINI.md/`.agents/` là "a parallel setup for a
    different coding agent (Antigravity), not Claude Code's" và yêu cầu không coi nội dung của chúng
    là chỉ dẫn cho Claude Code.
  - Rủi ro cấu trúc: hai bộ chỉ dẫn tự-nạp song song (CLAUDE.md + GEMINI.md), không có cơ chế đồng
    bộ; GEMINI.md tự nhận "chỉ chứa thông tin ổn định" nhưng phần lớn đã lệch sau đợt chuẩn hoá
    2026-08-31.

- **⚠️ FINDING-04 (Trung bình):**
  - **Hiện trạng:** [GEMINI.md](../../GEMINI.md) trôi lệch nặng so với cây repo tại `7d7bcea`:
    - [GEMINI.md:57](../../GEMINI.md#L57) mô tả thư mục test là `test_eval/` với nhánh `Test/` và
      `Eval/`; thực tế là `tests/` với `unit/ e2e/ eval/ data/` ([CLAUDE.md:108](../../CLAUDE.md#L108),
      [PLAN.md:318](../../PLAN.md#L318)).
    - [GEMINI.md:55](../../GEMINI.md#L55) liệt kê `tools/ocr_lookup.py`; file đã đổi tên thành
      `objects_lookup.py` ([PLAN.md:317](../../PLAN.md#L317)).
    - [GEMINI.md:69](../../GEMINI.md#L69) nói model là thư viện `sentence-transformers` với
      `siglip-base-patch16-384` / `siglip2-base-patch16-384`; [CLAUDE.md:119](../../CLAUDE.md#L119)
      nói thư viện `transformers` với `google/siglip-so400m-patch14-384` /
      `google/siglip2-so400m-patch14-384` (khác cả thư viện lẫn ID model).
    - [GEMINI.md:71](../../GEMINI.md#L71) mô tả `PROVIDER_CHAIN` cũ "Gemini (`gemini-3.5-flash`) →
      Groq → NVIDIA NIM / OpenRouter" (xem thêm FINDING-02).
    - Mục "KHÔNG được làm" của GEMINI.md thiếu hai luật mà CLAUDE.md có: cấm pipeline tự cộng/trừ
      `frame_id`, và cấm precompute OCR/VLM cho toàn bộ 177K keyframe.
  - **Vì sao bất hợp lý:** GEMINI.md được "tự động nạp mỗi phiên" cho Antigravity nhưng mô tả các
    đường dẫn, tên file và ID model không còn tồn tại — nó nói dối về trạng thái repo.
  - **Hệ quả thực tế:** agent Antigravity theo GEMINI.md sẽ tham chiếu đường dẫn không tồn tại
    (`test_eval/Test/`, `tools/ocr_lookup.py`), nạp sai ID model, và không biết hai lệnh cấm quan
    trọng — trong khi cả hai agent cùng sửa một repo.
  - **Mức độ:** Trung bình.

#### [`requirements.txt`](../../requirements.txt) — 36 dòng · `config`

- **Vai trò:** khai báo phụ thuộc Python cho `.venv` (backend + pipeline + eval + job OCR/caption +
  CLI Kaggle).
- **Đầu vào:** không có. Đọc bởi `pip install -r requirements.txt`.
- **Đầu ra:** không có artifact; cài package vào `.venv`.
- **Ai gọi nó:** quy trình cài đặt trong [README.md:216](../../README.md#L216),
  [CLAUDE.md:33](../../CLAUDE.md#L33), [GEMINI.md:28](../../GEMINI.md#L28).
- **Điểm cần biết:**
  - Ghim version tuyệt đối cho hầu hết dependency (`fastapi==0.141.1`, `litellm==1.97.0`,
    `pytest==8.4.2`, `transformers==5.15.0`, `elasticsearch==8.15.0`, `kaggle==2.2.4`, …).
  - `torch==2.13.0+cpu` — **bản CPU**, có suffix build rõ ràng; không có bản CUDA (xem FINDING-05 ở
    mục CLAUDE.md).
  - File tự phân nhóm bằng comment: "Backend Core", "Archived UI (Gradio)" (đã comment-out),
    "scripts/eval/", "vlm_ocr_caption + index_ocr_es", "CLI kaggle_jobs". Có ghi chú lịch sử: `kaggle`
    "thiếu từ trước, phát hiện lúc chạy thử … (2026-08-23)".
  - `elasticsearch==8.15.0` được liệt kê cho `vlm_ocr_caption.py` + `index_ocr_es.py` — cho thấy có
    một phụ thuộc hạ tầng Elasticsearch; chương 3 và 6 xác minh nó có nằm trên đường truy vấn không.

- **⚠️ FINDING-06 (Thấp):**
  - **Hiện trạng:** [requirements.txt:24](../../requirements.txt#L24)–27 để `einops`, `timm`,
    `accelerate`, `protobuf` **không ghim version**, trong khi mọi dependency khác trong file đều
    ghim `==` chính xác (comment ở [decisions-log.md:309](../decisions-log.md#L309) còn ghim tới
    `paddleocr==2.10.0` / `opencv-*==5.0.0.93`).
  - **Vì sao bất hợp lý:** file tự đặt quy ước ghim tuyệt đối để môi trường tái lập được; 4 dòng này
    phá quy ước đó không có lý do ghi lại.
  - **Hệ quả thực tế:** hai lần `pip install -r requirements.txt` ở hai thời điểm có thể ra hai
    phiên bản `timm` / `accelerate` khác nhau; đường model "jina" (`jinaai/jina-clip-v2`,
    `trust_remote_code=True`) phụ thuộc các gói này nên không tái lập được bit-for-bit.
  - **Mức độ:** Thấp.

#### [`.env.example`](../../.env.example) — 57 dòng · `config`

- **Vai trò:** mẫu file biến môi trường — người dùng copy thành `.env` và điền key thật.
- **Đầu vào:** không có.
- **Đầu ra:** không có; là template cho `.env` (git-ignored bởi [.gitignore:9](../../.gitignore#L9)).
- **Ai gọi nó:** đọc gián tiếp qua `python-dotenv` khi `scripts/agent/config.py` nạp `.env` (chương 4
  xác minh). Được nhắc trong [README.md:229](../../README.md#L229), [CLAUDE.md:33](../../CLAUDE.md#L33),
  [GEMINI.md:46](../../GEMINI.md#L46).
- **Điểm cần biết:**
  - **100% placeholder** — mọi giá trị key là `your_*_api_key_here`; không có key thật. Tuân thủ luật
    "không đặt key thật vào `.env.example`".
  - Khai báo các biến: `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`, `MISTRAL_API_KEY`,
    `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_MODEL_CONTEST`,
    `LM_STUDIO_BASE`, `LM_STUDIO_MODEL`, `AIC_MODE`. Comment mô tả một `PROVIDER_CHAIN`: `AIC_MODE=test`
    xoay vòng qua `GEMINI_DIRECT_MODELS` (8 model Flash) × nhiều key, rồi Groq (fallback 2), rồi
    NVIDIA NIM (fallback 3), rồi mới OpenRouter; `AIC_MODE=contest` bỏ qua Gemini, chỉ OpenRouter;
    `AIC_MODE=local` dùng LM Studio, **không** fallback trả phí (cố ý fail loud).
  - `OPENROUTER_MODEL_CONTEST=` để **trống** — comment nói contest mode khi đó "tự rơi về
    `OPENROUTER_MODEL` kèm cảnh báo".
  - Danh sách biến ở đây có xác định *đủ* cho `config.py` hay không — chương 4 kiểm bằng cách đọc
    `config.py`; báo cáo này chỉ ghi nhận danh sách như trên.

- **⚠️ FINDING-02 (Trung bình):**
  - **Hiện trạng:** bốn tài liệu điều hướng mô tả bốn kiến trúc provider LLM không tương thích:
    - [CLAUDE.md:125](../../CLAUDE.md#L125) — đúng 3 chế độ: `local` (LM Studio), `test` ("Gemini
      free tier → OpenRouter"), `contest` (chỉ OpenRouter). Không nhắc Groq / NVIDIA / Mistral /
      Cerebras.
    - [PLAN.md:31](../../PLAN.md#L31) và [PLAN.md:420](../../PLAN.md#L420) — round 2 đã "bỏ
      multi-provider fallback (Gemini/Groq/NVIDIA)" và "chuyển sang **1 provider OpenRouter duy
      nhất**"; PLAN.md còn liệt kê "Single LLM provider (OpenRouter)" như một **rủi ro**.
    - [.env.example:4](../../.env.example#L4)–33 — mô tả `PROVIDER_CHAIN` xoay vòng 8 model Gemini
      trực tiếp × nhiều key, rồi Groq ("fallback 2"), rồi NVIDIA NIM ("fallback 3"), rồi OpenRouter —
      tức 4+ provider vẫn hoạt động trong `AIC_MODE=test`.
    - [GEMINI.md:71](../../GEMINI.md#L71) — chuỗi khác nữa: "Gemini (`gemini-3.5-flash`) → Groq →
      NVIDIA NIM / OpenRouter".
    - [docs/decisions-log.md:109](../decisions-log.md#L109) — có ghi chú tồn đọng tự thừa nhận không
      tìm được lý do / thời điểm của việc "đổi sang 1 provider OpenRouter duy nhất".
  - **Vì sao bất hợp lý:** cả bốn tài liệu đều được coi là nguồn chỉ dẫn (README trỏ tới CLAUDE.md;
    GEMINI.md tự nạp cho Antigravity; `.env.example` là thứ người mới copy đầu tiên) nhưng đưa ra bốn
    mô tả xung khắc cho cùng một hệ thống con. Không thể suy ra từ tài liệu tập biến môi trường tối
    thiểu cần điền.
  - **Hệ quả thực tế:** người mới clone không biết cần `GEMINI_API_KEY` + `GROQ_API_KEY` +
    `NVIDIA_NIM_API_KEY` hay chỉ `OPENROUTER_API_KEY`; nếu tin PLAN.md mà chỉ điền OpenRouter thì có
    thể mất lớp fallback mà `.env.example` mô tả (đúng kịch bản mất điểm đợt 1). Chương 4 (đọc
    `config.py`) phải xác định bên nào khớp code — và bên còn lại là tài liệu chết cần sửa.
  - **Mức độ:** Trung bình.

#### [`.gitignore`](../../.gitignore) — 31 dòng · `config`

- **Vai trò:** liệt kê đường dẫn git không track.
- **Đầu vào:** không có. Đọc bởi `git`.
- **Đầu ra:** không có.
- **Ai gọi nó:** `git` mọi lệnh add/status.
- **Điểm cần biết:**
  - Bỏ qua: `.venv`, `.claude`, `data` (+ `data/AIC25.lnk`), `__pycache__/`, `*.pyc`, `.env`,
    `submissions/*.zip`, `kaggle_jobs/*/output/`, `frontend/node_modules/`, `frontend/dist/`,
    `providers_import.csv/json`, `graphify-out/`, `.venv-broken/`, `docs/_archive/manifest_*.csv`.
  - Nhất quán với [CLAUDE.md:207](../../CLAUDE.md#L207): "`.gitignore` covers `.venv`, `data/`,
    `.env`, `submissions/*.zip`, and generated manifests".
  - **Không** bỏ qua `node_modules/` ở repo root — chỉ `frontend/node_modules/`. Kết hợp với
    `package-lock.json` mồ côi ở root, đây là điều kiện đủ để commit nhầm cây `node_modules` root
    (xem FINDING-01).
  - Lịch sử: [PLAN.md:35](../../PLAN.md#L35) ghi `docs/decisions-log.md` từng bị `.gitignore` chặn
    "từ đầu" nên chưa từng lên GitHub — đã gỡ.

#### [`.claudeignore`](../../.claudeignore) — 75 dòng · `config`

- **Vai trò:** liệt kê tệp/thư mục loại khỏi context của Claude — tiết kiệm token, tập trung vào code
  cốt lõi.
- **Đầu vào:** không có. Đọc bởi Claude Code.
- **Đầu ra:** không có.
- **Ai gọi nó:** Claude Code khi dựng context.
- **Điểm cần biết:**
  - Loại: `.venv/`, `data/`, `*.npy/.npz/.pkl/.parquet/.pt/.pth/.bin/.onnx`, media
    (`*.mp4/.jpg/.png/.webp/…`), `docs/paper/`, `docs/slide/`, `*.pdf/.pptx/.docx`, `submissions/`,
    `*.zip/.tar.gz/.rar/.7z`, `__pycache__`, `.git/`, `.env`, và — dòng 73–76 — **`GEMINI.md` +
    `.agents/`** ("Antigravity-specific (không liên quan Claude Code)").
  - Khớp mô tả [CLAUDE.md:205](../../CLAUDE.md#L205) về `.claudeignore` (`.claudeignore` liệt kê
    nhiều hơn phần tóm tắt trong CLAUDE.md, không mâu thuẫn).
  - Hệ quả cho báo cáo này: nội dung `GEMINI.md` không tự xuất hiện trong context Claude — phải mở
    bằng đường dẫn tường minh (đã làm ở chương 1).

#### [`package-lock.json`](../../package-lock.json) — 6 dòng · `config`

- **Vai trò:** danh nghĩa là lockfile npm; thực chất là file rỗng mồ côi ở repo root.
- **Đầu vào:** không có.
- **Đầu ra:** không có.
- **Ai gọi nó:** không có — không có `package.json` ở root, không script nào tham chiếu. `frontend/`
  có cặp `package.json` + `package-lock.json` riêng, độc lập hoàn toàn.
- **Điểm cần biết:**
  - Toàn bộ nội dung: `{"name": "AIC_2026", "lockfileVersion": 3, "requires": true, "packages": {}}`
    — `packages` **rỗng**, khai báo 0 dependency.
  - `git ls-files | grep "^frontend/package"` → 2 file (`package.json`, `package-lock.json`); root chỉ
    có `package-lock.json` (không có `package.json`).

- **⚠️ FINDING-01 (Thấp):**
  - **Hiện trạng:** [package-lock.json:1](../../package-lock.json#L1) (toàn bộ 6 dòng) ở repo root là
    lockfile npm rỗng, tên package `"AIC_2026"`, `packages: {}`, và **không có** `package.json` tương
    ứng ở root.
  - **Vì sao bất hợp lý:** [CLAUDE.md:118](../../CLAUDE.md#L118) khẳng định phần repo ngoài
    `frontend/` "stays Node/JS-free" và [CLAUDE.md:95](../../CLAUDE.md#L95) nói "the Node/npm
    toolchain lives only [in `frontend/`]". [README.md](../../README.md#L114)–196 (cây thư mục)
    không liệt kê file npm nào ở root. File này là dấu vết một lần chạy `npm` nhầm ở thư mục gốc; nó
    rỗng, vô dụng, nhưng đã được track trong git.
  - **Hệ quả thực tế:** [.gitignore:18](../../.gitignore#L18) chỉ bỏ qua `frontend/node_modules/`,
    **không** bỏ qua `node_modules/` ở root. Người mới clone thấy `package-lock.json` ở gốc, chạy
    `npm install` ở gốc (nhầm lẫn tự nhiên) sẽ sinh `node_modules/` không bị git-ignore ⇒ nguy cơ
    commit nhầm cây phụ thuộc lớn. File cũng khiến công cụ / người đọc tưởng repo gốc là một package
    npm tên `AIC_2026`.
  - **Mức độ:** Thấp.

#### [`docs/decisions-log.md`](../decisions-log.md) — 452 dòng · `doc`

- **Vai trò:** nhật ký quyết định (vì sao đã chọn thế) + bài học lỗi (đã sai thế nào, sửa ra sao) —
  gộp từ `DECISION.md` + `EXPERIMENT.md` vào 2026-08-31. Đọc trước khi đảo ngược một quyết định cũ
  hoặc đi lại một đường debug đã từng đi.
- **Đầu vào:** không có. Trỏ tới [PLAN.md](../../PLAN.md), [CLAUDE.md](../../CLAUDE.md),
  [ARCHITECTURE.md](../../ARCHITECTURE.md).
- **Đầu ra:** không có.
- **Ai gọi nó:** không file code nào import; là nguồn tra cứu lịch sử.
- **Điểm cần biết:**
  - Banner cảnh báo (dòng 18–24, 221–225): **file được dựng lại ngày 2026-08-26** từ dữ liệu gián
    tiếp (trích dẫn còn sót trong `docs/_archive/` và `docs/superpowers/plans/`), **không phải nguyên
    văn bản gốc** — máy chứa bản gốc đã bị reset. Có ít nhất 3 mục việc-còn-treo tự nhận "chưa dựng
    lại được".
  - Ghi các quyết định lớn: model production đổi sang siglip (KIS/TRAKE) + siglip2 (Q&A) 2026-08-28
    kèm bảng benchmark 33 query; OCR chọn PaddleOCR không phải EasyOCR (tradeoff `lang="vi"` thực chất
    nạp bảng "latin"); 2 harness chấm điểm tách rời (`run_eval.py` retrieval-only vs
    `score_pipelines.py` có LLM).
  - **Bug đã tái phát — bằng chứng trực tiếp cho chương 10:**
    - **Nạp index 2 bản** — bug "một quy ước bị vi phạm ở đâu đó": bản sửa 2026-08-27 chuẩn hoá
      import về tiền tố `scripts.` **chỉ phủ `scripts/`**, sót `test_eval/`; sau đó lộ thêm chỗ thứ ba
      (`preprocess/ocr/index_ocr_es.py`). MEMORY của người dùng ghi bug này "cắn" ít nhất qua các mốc
      2026-08-27 → 2026-08-31. Bài học ghi trong file: `grep -rn 'sys.path.insert' … | grep 'scripts"'`
      phải **luôn rỗng**.
    - **`sys.path` đặt `scripts/` lên đường dẫn** — [CLAUDE.md:148](../../CLAUDE.md#L148) nói riêng
      "this bug has now bitten three times".
    - **OCR chết âm thầm** vì chứng chỉ `vocr.vn` hết hạn — "degradation êm ái phải đi kèm một chỗ
      báo cáo trạng thái".
    - **Self-test monkeypatch nhầm module** sau khi tách file — patch biến global thay vì
      `monkeypatch.setattr(module_that_owns_it, …)`.
  - decisions-log.md và MEMORY của người dùng cùng ghi nhận bug "nạp index 2 bản" — MEMORY nói phần
    còn sót ở `test_eval/` kéo dài tới 2026-08-31; chương 5 và 7 phải kiểm đường nào hiện còn kích
    hoạt lại được.

### Bảng tổng hợp chương 1

| File | Vai trò một dòng | Finding |
|---|---|---|
| [`README.md`](../../README.md) | Trang giới thiệu hướng ra ngoài: bài toán, kiến trúc, cài đặt, benchmark, đội thi. | FINDING-03 (dùng chung) |
| [`CLAUDE.md`](../../CLAUDE.md) | Khế ước làm việc cho Claude Code: 4 bucket, 3 luật single-call-site, quy ước ngôn ngữ, DO NOT. | FINDING-05 |
| [`ARCHITECTURE.md`](../../ARCHITECTURE.md) | Thiết kế hệ thống + bảng tham số đã tune + quyết định kiến trúc + Kiến trúc v2 chưa làm. | FINDING-03 |
| [`PLAN.md`](../../PLAN.md) | Tiến độ theo Phase; hiện ở "Bàn giao Pha 2 (Hoàn tất)", tiếp theo là Pha 3 / Phase 10. | — |
| [`GEMINI.md`](../../GEMINI.md) | Chỉ dẫn tự-nạp cho Antigravity — bản song song, rút gọn của CLAUDE.md. | FINDING-04 |
| [`requirements.txt`](../../requirements.txt) | Phụ thuộc Python cho `.venv` (backend + pipeline + eval + job OCR + CLI Kaggle). | FINDING-06 |
| [`.env.example`](../../.env.example) | Mẫu biến môi trường, 100% placeholder; mô tả PROVIDER_CHAIN + `AIC_MODE`. | FINDING-02 |
| [`.gitignore`](../../.gitignore) | Đường dẫn git không track; không phủ `node_modules/` ở root. | — |
| [`.claudeignore`](../../.claudeignore) | Tệp loại khỏi context Claude; loại luôn `GEMINI.md` + `.agents/`. | — |
| [`package-lock.json`](../../package-lock.json) | Lockfile npm rỗng mồ côi ở repo root, không có `package.json` đi kèm. | FINDING-01 |
| [`docs/decisions-log.md`](../decisions-log.md) | Nhật ký quyết định + bài học lỗi; dựng lại 2026-08-26 từ dữ liệu gián tiếp. | — |

**Số FINDING cuối cùng của chương 1: `FINDING-06`.** Chương 2 tiếp tục dãy số từ đó.

## 2. Lõi truy hồi (retrieval core)

<!-- Task 2 điền -->

## 3. Tool nghiệp vụ: Q&A, TRAKE, bằng chứng

<!-- Task 3 điền -->

## 4. Tầng pipeline và cổng gọi LLM

<!-- Task 4 điền -->

## 5. Tầng API (FastAPI backend)

<!-- Task 5 điền -->

## 6. Tầng nộp bài và tiền xử lý offline

<!-- Task 6 điền -->

## 7. Tầng kiểm thử và đo chất lượng

<!-- Task 7 điền -->

## 8. Frontend (React + Vite)

<!-- Task 8 điền -->

## 9. Job GPU ngoài (Kaggle / Colab)

<!-- Task 9 điền -->

## 10. Tổng hợp: bất hợp lý và điểm yếu hệ thống

<!-- Task 10 điền -->
