# Chuẩn hoá repo AIC2026 — Pha 1 (bảo toàn hành vi)

> Ngày: 2026-08-31 · Trạng thái: đã duyệt thiết kế, chờ implementation plan
> Phạm vi: cấu trúc thư mục, đặt tên module, tách file, tầng tài liệu, lưới test.
> **KHÔNG đổi hành vi hệ thống.** Mọi sửa lỗi thuật toán thuộc Pha 2.

## 1. Vấn đề

Repo đã lớn hơn khung tổ chức ban đầu của nó. Ba triệu chứng đo được:

1. **Tài liệu trỏ vào file không tồn tại.** `scripts/index.py` đã chuyển vào `docs/_archive/`
   nhưng còn 7+ chỗ tham chiếu, trong đó `retrieve.py:77` trỏ tới *số dòng* của nó.
   `scripts/app.py` đã retire nhưng 5 file vẫn mô tả nó như tầng UI hiện hành, kể cả sơ đồ
   luồng dữ liệu ở `ARCHITECTURE.md` §1.
2. **Hợp đồng thư mục trong CLAUDE.md đã bị phá.** File ghi "bốn bucket, đừng thêm top-level
   folder", thực tế `scripts/` có thêm `preprocess/` (14 file) và `experiments/` không được
   nhắc ở đâu.
3. **Tài liệu phân kỳ khỏi code nhanh hơn tốc độ sửa.** Hệ quả cụ thể: `retrieve.py` docstring
   dòng 10 chép benchmark của `siglip2` còn dòng 15 khai mặc định là `siglip`, mâu thuẫn ngay
   trong một file mà không ai phát hiện. 7 file `.md` ở root cùng mô tả một hệ thống nghĩa là
   mỗi sự thật phải sửa ở 4 chỗ.

Cộng thêm hai món nợ kỹ thuật liên quan:

4. **Không có lưới test chạy được.** ~400 dòng self-test nằm trong khối `__main__` của 12 file,
   không chạy được bằng một lệnh, không biết file nào fail cho tới khi mở từng cái.
   `test_rrf_fusion.py` và `test_qa_answer_contract.py` đã viết theo kiểu pytest nhưng `pytest`
   không có trong `requirements.txt` và không cài trong `.venv` — hai file đó chưa từng chạy.
5. **Bug double-load trong `EXPERIMENT.md` chưa sửa hết.** `test_smoke_tools.py:19` và
   `test_smoke_pipelines.py:19` vẫn đặt `scripts/` lên `sys.path` rồi `from agent.tools.retrieve
   import ...`, nạp module dưới tên thứ hai → SigLIP + index nạp hai bản. Việc sửa ở đợt trước
   chỉ phủ `scripts/`, không phủ `test_eval/`.

## 2. Nguyên tắc dẫn đường

- **Mỗi sự thật sống ở đúng một chỗ.** Áp cho cả code (một điểm chuyển đổi `frame_id`) lẫn tài
  liệu (một file mô tả kiến trúc).
- **Tên phải nói đúng nội dung.** Không giữ tên sai vì "nhiều nơi đã import".
- **Ranh giới thư mục theo *thời điểm chạy*, không theo chủ đề.** Runtime (lúc truy vấn) vs
  offline (chạy một lần, đắp vào `data/`) là ranh giới thật của repo này.
- **Không shim, không alias tương thích ngược.** Mọi call site đều nằm trong repo; để lại
  alias chính là cách sinh ra hai tên cho một thứ, tức là tái tạo đúng vấn đề đang sửa.
- **Bảo toàn hành vi phải chứng minh được, không phải cam kết miệng.**

## 3. Cấu trúc thư mục đích

```
AIC2026/
├── README.md            cổng vào · setup · lệnh chạy hàng ngày
├── CLAUDE.md            quy ước code · DO NOT · bản đồ thư mục
├── ARCHITECTURE.md      luồng dữ liệu · module · thuật toán · tham số
├── PLAN.md              việc còn lại theo pha
├── GEMINI.md            (của Antigravity — KHÔNG đụng)
├── requirements.txt     + pytest
├── scripts/
│   ├── agent/           config.py · pipeline_kis|qa|trake.py
│   │   └── tools/       (§4)
│   ├── api/             main.py · schemas.py · state.py · routers/
│   ├── submit/          build_submission.py · validate_submission.py
│   └── offline/         ◄ preprocess/ + experiments/
│       ├── captions/    build_caption_manifest · merge_captions · run_caption_shard_local
│       ├── ocr/         index_ocr_es · merge_ocr · run_ocr_shard_local
│       │                + es_index.py · vlm_ocr_caption.py (◄ từ agent/tools/)
│       ├── shards/      7 script bundle/push/download/setup
│       └── analysis/    analyze_frame_similarity.py (◄ từ experiments/)
├── tests/               ◄ test_eval/
│   ├── conftest.py      đặt repo root lên sys.path — MỘT chỗ duy nhất
│   ├── unit/            tất định, không cần data/ hay API key
│   ├── eval/            run_eval · multi_index · lookup_frame · widen_gt_windows
│   │                    + eval_ground_truth.json · EVAL_GUIDE.md
│   ├── e2e/             score_pipelines · test_phase{3,4,5,6}_* · test_smoke_*
│   │                    + e2e_baseline.json
│   └── data/            sample_queries.json · sotuyen1_bo_de_thi.csv · thunghiem_bo_de_thi.csv
├── frontend/  kaggle_jobs/  colab_jobs/  submissions/   (không đụng)
└── docs/                (§6)
```

### 3.1 Vì sao `preprocess/` + `experiments/` → `offline/`

Ranh giới thật không phải "tiền xử lý vs thí nghiệm" mà là **chạy lúc truy vấn** vs **chạy một
lần rồi đắp kết quả vào `data/`**. Một tên nói đúng điều đó cho phép CLAUDE.md ghi lại hợp đồng
bốn bucket có thật — `agent` / `api` / `submit` / `offline` — thay vì một hợp đồng đã bị phá.

### 3.2 Vì sao `es_index.py` + `vlm_ocr_caption.py` rời `agent/tools/`

Đã grep toàn repo: cả hai chỉ được `offline/ocr/index_ocr_es.py` import, không nằm trên bất kỳ
đường truy vấn nào. Để chúng trong `tools/` khiến người đọc tưởng Elasticsearch là một phần của
pipeline runtime.

## 4. Tách file lớn

```
tools/answer_qa.py 674 ─┬─ qa_prompts.py    8 prompt template
                        ├─ qa_classify.py   is_visual_count_question · _needs_text_reading
                        │                   · _asks_displayed_number · các regex đi kèm
                        ├─ qa_normalize.py  canonicalize_answer · is_non_answer
                        │                   · _normalize_answer · extract_visual_count
                        └─ answer_qa.py     3 tầng trả lời + crosscheck (~250)

tools/retrieve.py  544 ─┬─ index_store.py   MỚI — §4.1
                        ├─ retrieve.py      fast_retrieve · _for_video · _qa · _multi (~200)
                        ├─ hybrid.py        hybrid_retrieve · fast_retrieve_multi_model
                        │                   · SPARSE_TOP_K
                        └─ frames.py        get_neighbor_frames · get_all_frames
                                            · get_keyframe_path

pipeline_trake.py  490 ─┬─ tools/trake_align.py  _find_best_increasing_chain
                        │                        · _rule_plausibility
                        └─ pipeline_trake.py     orchestration 3 giai đoạn (~300)
```

### 4.1 `index_store.py` — điểm duy nhất không phải "di chuyển thuần"

Singleton hiện là biến global của module (`_MATRIX`, `_META`, `_ENCODE_FN`, `_QA_*`,
`_KEY_INDEX`). `hybrid.py` và `frames.py` đều cần đọc chúng. Nếu để hai module đó import biến
private của `retrieve.py` thì tách xong còn bẩn hơn trước.

`index_store.py` sở hữu **state + phép dựng hit dict**:

| API | Vai trò |
|---|---|
| `get_index(qa: bool)` | `(matrix, meta, encode_fn)` — nạp lười, một lần/process |
| `preload()` | nạp sẵn cả hai không gian embedding (API gọi lúc khởi động) |
| `row_to_hit(meta, row_idx, score)` | dựng hit dict chuẩn — **điểm duy nhất** cộng `frame_idx + 1` |
| `key_index(qa: bool)` | `{(video_id, n): row_idx}` cho nhánh BM25 |
| `load_model(tag)` | nạp một model tag bất kỳ (cho multi-model RRF), gồm cả `_add_jpg_paths()` |

**Lợi ích phụ đáng kể:** luật "`frame_id = frame_idx + 1` chỉ ở một chỗ" trong CLAUDE.md hiện
**đã không còn đúng** — phép cộng đó đang nằm rải ở `fast_retrieve`, `fast_retrieve_for_video`,
`fast_retrieve_qa`, `_row_to_hit`, `get_neighbor_frames`, `get_all_frames` (6 chỗ). Sau khi gom
vào `row_to_hit()`, luật đúng trở lại theo đúng nghĩa đen, và CLAUDE.md sẽ trỏ vào
`index_store.py`.

### 4.2 Đổi tên

| Cũ | Mới | Lý do |
|---|---|---|
| `tools/ocr_lookup.py` | `tools/objects_lookup.py` | Nó đọc Objects JSON (Faster R-CNN), **không làm OCR**. 4 call site. Tên hiện tại khiến người đọc tưởng đã đọc được chữ trên khung hình. |
| `rank.py` (chỉ có trong tài liệu) | `rerank.py` | Tài liệu gọi một tên, file thật tên khác. |

### 4.3 Ngôn ngữ comment

Hiện trộn: `pipeline_kis.py` tiếng Việt **có dấu**, `rerank.py`/`fusion.py`/`pipeline_qa.py`
**không dấu**, `answer_qa.py` trộn cả hai trong cùng một file. Thống nhất về **có dấu** cho toàn
bộ `scripts/agent/`, `scripts/api/`, `scripts/submit/`.

Làm **sau** mọi bước tách/di chuyển file, để không phải sửa cùng một dòng hai lần. Không đụng
vào: tên biến/hàm, và **nội dung prompt LLM trong `qa_prompts.py`** (tiếng Anh — sửa một ký tự
là đổi hành vi mô hình).

## 5. Import và sys.path

**Quy tắc dứt khoát:** giữ khối `sys.path.insert` ở file **có khối `__main__` chạy trực tiếp**;
bỏ ở file **chỉ được import**. Đây là ranh giới duy nhất — không phải "thư viện vs pipeline".

- **Giữ:** `pipeline_kis|qa|trake.py`, `retrieve.py`, `objects_lookup.py`, `rewrite.py`,
  `sparse_index.py`, `answer_qa.py`, `ocr_read.py`, `config.py` (đều có CLI demo/công cụ chạy
  bằng `python scripts/agent/tools/X.py`), `tests/eval/*`, `tests/e2e/*`, `offline/**`.
- **Bỏ:** `rerank.py`, `fusion.py`, `temporal_nms.py`, `query_expand.py`, `asr_lookup.py`,
  `index_store.py`, `hybrid.py`, `frames.py`, `trake_align.py`, `qa_*.py`, `api/**`,
  `submit/**` — chỉ được import, không bao giờ chạy trực tiếp.

> Bỏ nhầm ở file có `__main__` sẽ làm lệnh `python scripts/agent/tools/sparse_index.py --build`
> gãy với `ModuleNotFoundError` — đúng loại lỗi đã xảy ra ở commit `f569a62`.
- **`tests/conftest.py`** đặt repo root lên `sys.path` cho toàn bộ pytest — một chỗ, thay cho
  khối lặp ở từng file test.
- **Sửa `test_smoke_tools.py` + `test_smoke_pipelines.py`**: bỏ `scripts/` khỏi `sys.path`,
  đổi `from agent...` → `from scripts.agent...`. Đây là phần còn sót của bug đã ghi trong
  `EXPERIMENT.md`; sau khi sửa, hai smoke test nạp một bản index thay vì hai.

## 6. Tầng tài liệu

Root còn **4 file** (+ `GEMINI.md` không đụng). `DECISION.md` + `EXPERIMENT.md` gộp thành
`docs/decisions-log.md`: cùng thể loại nội dung ("vì sao đã chọn thế" / "đã sai thế nào"), cùng
tần suất đọc (chỉ khi truy nguyên), nên tách hai file chỉ tạo thêm một chỗ để trôi.

```
docs/
├── decisions-log.md    ◄ DECISION.md + EXPERIMENT.md
├── rules/              Thong tin vong So tuyen · Bo De Kiem Thu va Phan Tich Bay
├── training/           ◄ Training/
├── reports/            eval_baseline_comparison · eval_e2e_scores · eval_siglip2_comparison
├── presentation/       presentation_aic2026.html · team_presentation_guide.md · diagrams/
├── superpowers/        specs/ + plans/ — GIỮ NGUYÊN (skill tự ghi vào đường dẫn này)
├── paper/  slide/      (giữ)
└── _archive/           (giữ, không thêm gì từ scripts/)
```

### 6.1 Nội dung phải viết lại, không chỉ đổi đường dẫn

- Xoá mọi tham chiếu tới `scripts/index.py` và `scripts/app.py` (7+ chỗ trong code comment và
  tài liệu), gồm cả sơ đồ §1 của `ARCHITECTURE.md` đang vẽ Gradio ở giữa luồng dữ liệu.
- Gỡ mâu thuẫn `siglip`/`siglip2` trong docstring `retrieve.py` — ghi đúng **giá trị mặc định
  thật trong code**, và đánh dấu rõ đây là điểm nghi vấn để Pha 2 xử lý.
- Ghi tham số hiện hành kèm **thang đo của model nào** đã hiệu chỉnh ra nó. Cụ thể
  `MARGIN_THRESHOLD = 0.012` hiệu chỉnh trên cosine của `clip_vitb32` đã retire; Pha 1 **không
  đổi giá trị** (đổi = đổi hành vi) nhưng comment phải nói đúng sự thật đó thay vì mô tả một
  model không còn tồn tại.
- CLAUDE.md ghi lại hợp đồng thư mục đúng thực tế (4 bucket gồm `offline/`), quy ước test mới,
  và trỏ luật `frame_id` vào `index_store.py`.

### 6.2 Xoá hẳn (không archive)

Đều là rác sinh ra, đã nằm trong `.gitignore`, không có giá trị lịch sử:
`graphify-out/` (3.5 MB), `providers_import.csv|json`, `.venv-broken/`, mọi `__pycache__/`.
`.venv-broken/` cần thêm vào `.gitignore`.

Không có module chết trong `scripts/` để archive — đã kiểm tra: `translate_raw.py` được
`api/routers/kis.py` dùng, `es_index.py`/`vlm_ocr_caption.py` được batch job dùng.

## 7. Lưới test

### 7.1 Quy tắc phân loại khối `__main__`

- **Self-test** (có `assert`, chạy được không cần `data/` và không cần API key) → chuyển sang
  `tests/unit/`, giữ nguyên từng câu assert đã viết.
- **CLI demo/công cụ** (in kết quả, cần `data/` hoặc gọi LLM thật) → **giữ nguyên tại chỗ**.

| File | Khối `__main__` | Xử lý |
|---|---|---|
| `fusion.py` | self-test | → `tests/unit/test_fusion.py` |
| `temporal_nms.py` | self-test | → `tests/unit/test_temporal_nms.py` |
| `query_expand.py` | self-test | → `tests/unit/test_query_expand.py` |
| `rerank.py` | self-test (155 dòng) | → `tests/unit/test_rerank.py` |
| `answer_qa.py` | `_run_self_tests()` | → `tests/unit/test_answer_qa.py` |
| `pipeline_qa.py` | `_run_self_tests()` | → `tests/unit/test_pipeline_qa.py` |
| `pipeline_trake.py` | `_run_self_tests()` | → `tests/unit/test_trake_align.py` |
| `ocr_read.py` | self-test | → `tests/unit/test_ocr_read.py` |
| `asr_lookup.py` | `_run_self_tests()` | → `tests/unit/test_asr_lookup.py` |
| `sparse_index.py` | `--self-test` trong CLI | tách `_self_test()` → pytest, **giữ** CLI `--build`/`--query` |
| `rewrite.py` | CLI demo (gọi LLM thật) | giữ nguyên |
| `objects_lookup.py` (tên mới) | CLI demo (cần `data/`) | giữ nguyên |
| `retrieve.py`, `pipeline_kis.py`, `config.py` | CLI demo | giữ nguyên |

`test_rrf_fusion.py` + `test_qa_answer_contract.py` (đã là pytest, không cần data/API) chuyển
từ `test_eval/Test/` sang `tests/unit/`.

### 7.2 Thêm `pytest`

Vào `requirements.txt`. Không thêm plugin nào khác (không `pytest-cov`, không `pytest-xdist`) —
ngân sách thời gian trước giải eo hẹp, và bộ test này chạy dưới một phút.

## 8. Nghiệm thu — cách chứng minh không đổi hành vi

Đây là phần khiến Pha 1 có nghĩa. Làm **trước** khi đụng file nào:

### 8.0 Vì sao `run_eval.py` một mình KHÔNG đủ

`run_eval.py` chạy trên `multi_index.py`, mà module đó **cố ý không import** `retrieve.py` (ghi rõ
trong docstring của nó). Nghĩa là nó không chạm `retrieve.py`, `rerank.py`, hay bất kỳ pipeline
nào — dùng nó làm tiêu chí cứng cho một đợt refactor mà việc chính là *tách `retrieve.py` và
`answer_qa.py`* thì gần như không chứng minh được gì.

**Mốc chuẩn thật là golden snapshot của đường KIS production.** `run_kis()` không gọi LLM
(`expand_aspects` là template tất định, `rerank_by_ocr` là PaddleOCR cục bộ) nên nó **tất định** —
chạy hai lần ra đúng một kết quả. Một lượt `run_kis()` phủ: `index_store` → `retrieve` → `hybrid`
→ `sparse_index` → `fusion` → `rerank` → `temporal_nms` → `ocr_read`. Đó chính xác là tập module
bị đụng nhiều nhất trong Pha 1.

`tests/e2e/golden_kis_snapshot.py` (thêm mới, thành lưới regression lâu dài):
chạy `run_kis(text_en, top_k=100)` cho 18 câu KIS của `eval_ground_truth.json`, ghi danh sách
`video_id:frame_id` **theo đúng thứ tự** + một mã băm. So sánh trước/sau phải khớp **từng dòng**.

Ba nhánh còn lại và cách phủ:

| Đường | Tất định? | Cách phủ trong Pha 1 |
|---|---|---|
| KIS production | có | golden snapshot (tiêu chí cứng) |
| Q&A retrieval | có | golden snapshot nhánh `qa=True` (bỏ bước answer) |
| Q&A answer, TRAKE | không (gọi LLM) | `pytest tests/unit` — phần logic thuần đã có sẵn assert |
| `fusion`/`temporal_nms`/`query_expand` | có | `run_eval.py --all-features` (chúng dùng chung) |

1. **Chốt mốc.** Chạy `tests/e2e/golden_kis_snapshot.py` (tiêu chí cứng) và
   `run_eval.py --models siglip --all-features`. Chạy `scripts/api/_smoke_test.py`. Lưu lại tất cả.
2. **Commit theo nhóm nhỏ, không trộn:** (a) dọn rác + `.gitignore`, (b) move thư mục,
   (c) rename module, (d) tách file, (e) sys.path + smoke test, (f) pytest, (g) tài liệu.
3. **Nghiệm thu:**
   - **Golden snapshot KIS khớp từng dòng** với mốc — tiêu chí cứng. Nó tất định, nên mọi sai
     lệch dù một dòng đều là bug vừa tạo ra, không phải nhiễu.
   - `run_eval.py --models siglip --all-features` ra số khớp tuyệt đối.
   - `pytest tests/unit` xanh, và **số lượng assert không giảm** so với các khối `__main__` cũ.
   - `scripts/api/_smoke_test.py` xanh.
   - Grep chứng minh không còn tham chiếu tới `scripts/index.py`, `scripts/app.py`,
     `ocr_lookup`, `test_eval/`, `rank.py`.
   - Mỗi module import được độc lập (`python -c "import scripts.agent.tools.X"`).
4. **Không chạy `score_pipelines.py` trong Pha 1** — tốn API và dao động giữa các lần chạy nên
   không dùng làm bằng chứng "không đổi hành vi" được. Để Pha 2.

## 9. Ngoài phạm vi

`frontend/`, `kaggle_jobs/`, `colab_jobs/`, `GEMINI.md` + `.agents/`, và **mọi thay đổi hành
vi** — kể cả 4 lỗi đã biết (mặc định model Q&A, `top_k_video` TRAKE, fallback strict monotonic,
cách chấm điểm ứng viên đào sâu ở bet mode). Chúng thuộc Pha 2, thực hiện sau khi Pha 1 đã
chứng minh xong bằng `run_eval.py`.
