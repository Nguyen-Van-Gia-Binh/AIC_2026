# Pha 2 — Sửa 8 lỗi hành vi (P2.1–P2.8)

> Trạng thái: đã duyệt 2026-08-31. Kế hoạch thực thi:
> [2026-08-31-phase2-behavior-fixes.md](../plans/2026-08-31-phase2-behavior-fixes.md)

## 1. Bối cảnh

Pha 1 (đã merge vào `main`) chuẩn hoá cấu trúc repo với ràng buộc **bảo toàn hành vi tuyệt đối** —
nghiệm thu bằng golden snapshot khớp từng dòng. Trong lúc làm Pha 1 đã phát hiện 8 lỗi **hành vi**,
cố ý không sửa để giữ ranh giới đó. PLAN.md ghi lại thành P2.1–P2.8.

Pha 2 sửa 8 lỗi đó. Mọi mục ở đây **cố ý đổi hành vi**, nên tiêu chí nghiệm thu của Pha 1
(golden digest phải khớp) **không còn áp dụng** — xem §3.

## 2. Hai đính chính so với PLAN.md

PLAN.md viết trước khi kiểm tra lại code. Hai chỗ sai, sửa ở đây:

**2.1 — Thước đo của P2.7 sai.** PLAN.md viết *"Quét lại bằng `tests/eval/run_eval.py`
(0 chi phí API)"*. `run_eval.py` **không import `rerank.py`** (kiểm tra 2026-08-31: chỉ xuất hiện
1 lần, trong một comment). Nó chạy trên `multi_index.py`, cố ý tách khỏi đường production. Nó
không đo được `MARGIN_THRESHOLD`, và cũng không đo được P2.4.

Thước đo đúng: **`tests/e2e/score_pipelines.py --types kis`**. Nó gọi `run_kis()` thật, đi qua
`rerank.py`, và KIS **không gọi LLM một lần nào** ⇒ miễn phí hoàn toàn.

Đây đúng loại nhầm lẫn đã mắc ở spec Pha 1 §8.0 và đã ghi vào decisions-log: *đừng giả định một
harness chạm tới module mình định đo — hãy grep.*

**2.2 — Phase 10.0 đã lỗi thời.** PLAN.md §10.0 gọi "chuyển sang torch bản CUDA" là mục **CHẶN
ĐỨNG**, mô tả venv đang có `torch 2.13.0+cpu`. Thực tế đo 2026-08-31:

```
torch 2.8.0+cu129 · torch.cuda.is_available() = True · get_device_capability() = (12, 0)
```

`(12, 0)` = sm_120 (Blackwell) — đúng thứ RTX 5050 Laptop cần. Blocker đã được gỡ.
Nhưng `tests/eval/multi_index.py` **không có một dòng nào về `device`** ⇒ SigLIP vẫn encode trên
CPU. Không thuộc phạm vi Pha 2; ghi lại để cập nhật PLAN.md.

## 3. Nguyên tắc đo

### 3.1 Golden snapshot đổi vai

| | Pha 1 | Pha 2 |
|---|---|---|
| Digest | **phải khớp** | **cố ý đổi** — phải ghi lại digest trước/sau kèm lý do |
| Bổ sung | — | Final Score của loại bị ảnh hưởng **không được tụt** |

Ngoại lệ: **P2.8 thuần cấu trúc**, digest **phải khớp**. Nếu đổi thì đó là lỗi, không phải tính năng.

### 3.2 Thước đo theo loại

| Loại | Lệnh | Gọi LLM? | Chi phí |
|---|---|---|---|
| KIS | `score_pipelines.py --types kis` | Không | 0 |
| Q&A | `score_pipelines.py --types qa` | Có (5 câu) | nhỏ |
| TRAKE | `score_pipelines.py --types trake` | Có, chỉ khi margin ≤ 0,02 (10 câu) | nhỏ |

**Mọi số đo dùng để so sánh phải chạy ở `AIC_MODE=test`** — cùng một model thì mới so được với
nhau. `AIC_MODE=local` chỉ dùng cho smoke test và vòng lặp sửa code, **không bao giờ** dùng để lấy
số so sánh (xem §4).

### 3.3 Nhật ký đo

`docs/reports/phase2_measurement_log.md` — mỗi mục một khối:

```
## P2.x — <tên>
commit:        <sha>
golden digest: <trước> -> <sau>
Final:         KIS a.aaa -> b.bbb | QA c.ccc -> d.ddd | TRAKE e.eee -> f.fff
n câu:         KIS 23 | QA 5 | TRAKE 10
AIC_MODE:      test
kết luận:      giữ / revert
```

Mốc so sánh xuất phát: `tests/e2e/e2e_baseline.json` (2026-08-28) —
`ALL 0,488 · KIS 0,667 · QA 0,200 · TRAKE 0,312`. Baseline này chốt trên **33 câu**; ground truth
nay đã là **38 câu**, nên việc đầu tiên của Pha 2 là chốt lại baseline trên 38 câu (§6, việc 0).

### 3.4 Vì sao mỗi mục một commit

Mỗi mục sửa xong thì đo ngay rồi commit riêng. Điểm tụt thì revert đúng một commit, không phải
bisect. Đây là lý do không gộp nhiều mục vào một lần đo.

## 4. `AIC_MODE=local` — LLM chạy trên máy

Thêm chế độ thứ ba vào `config.py`.

| `AIC_MODE` | Nhà cung cấp | Dùng khi | Chi phí |
|---|---|---|---|
| `local` (mới) | LM Studio, `http://localhost:1234/v1` | smoke test, vòng lặp sửa code | 0 |
| `test` | Gemini trực tiếp → OpenRouter | **đo lấy số so sánh** | rẻ |
| `contest` | OpenRouter (`OPENROUTER_MODEL_CONTEST`) | bài nộp thật | đắt |

Đi qua tiền tố `lm_studio/` của LiteLLM ⇒ **không phá luật single-call-site, không thêm phụ thuộc**.
Chỉ mở rộng `PROVIDER_CHAIN` trong `config.py`.

**Ràng buộc quan trọng, phải viết vào CLAUDE.md:** VRAM máy đích là **8 GB** (RTX 5050 Laptop,
8151 MiB), và SigLIP (1,7 GB) thường nằm cùng process. Một VLM 7B ở Q4 kém hơn hẳn model thi ở việc
đọc cảnh. **Số đo từ `AIC_MODE=local` không dự báo được điểm thi thật** — dùng nó để tối ưu tham số
là tự lừa mình. Model đề xuất: `Qwen2.5-VL-7B-Instruct` GGUF Q4_K_M (~4,7 GB + ~1,4 GB projector),
lo được cả văn bản lẫn ảnh.

## 5. Ground truth — quyết định về schema và cách ghi

### 5.1 Hai schema đang đánh nhau

`origin/main` đã có `eval_ground_truth_v2_template.json` với schema mà `run_eval.py` **từ chối đọc**:

| v2 template | `run_eval.py` đòi | Hậu quả |
|---|---|---|
| `{"entries": [...]}` | mảng JSON top-level | `SystemExit` ngay |
| `query_text` | `text_en` | thiếu field → thoát |
| `gt_frame` | `gt_frame_start` + `gt_frame_end` | thiếu field → thoát |
| `events[].gt_frame` | `events[].gt_frame_start/end` | thiếu field → thoát |

Cả 5 câu trong template đó hiện **không chạy được câu nào**.

**Quyết định:** giữ v2 làm format người ghi (tiện hơn thật), thêm bước chuyển đổi
`tests/eval/normalize_gt.py` sinh ra file v1 cho harness. `run_eval.py` / `score_pipelines.py`
**không đổi một dòng nào**.

### 5.2 Không tự nới khoảng

`widen_gt_windows.py` nới ra keyframe lân cận **theo cơ học** — nó không biết khoảnh khắc thật kết
thúc ở đâu. Nới rộng làm điểm dễ ăn hơn ⇒ mọi model đều trông giỏi ⇒ mất khả năng phân biệt. Chính
`EVAL_GUIDE.md` đã cảnh báo đúng điều này, và PLAN.md Phase 7 ghi *"Cần dò tay lại — vài khoảng còn
rộng do keyframe thưa."*

**Quyết định:** `normalize_gt.py` mặc định sinh `[gt_frame, gt_frame]` — **một keyframe duy nhất,
chặt nhất**. Chỉ khi người ghi tự tay nhập thêm `gt_frame_end` (vì thật sự có nhiều keyframe liền kề
cùng thể hiện khoảnh khắc) thì khoảng mới rộng ra. Script không đoán.

Hệ quả kỹ thuật cần ghi vào hướng dẫn: hệ thống **chỉ trả về được `frame_id` của keyframe**. Nên
phải đánh dấu **keyframe nào thể hiện khoảnh khắc**, không phải một mốc thời gian tuỳ ý — nếu khoảng
ghi ra không chứa keyframe nào thì câu đó vĩnh viễn 0 điểm dù retrieval hoàn hảo. `lookup_frame.py`
làm đúng việc tra này.

### 5.3 `text_en` là biến đối chứng đông cứng, không phải "câu truy vấn"

SigLIP mạnh trên tiếng Anh, nên câu tiếng Anh phải tồn tại. Câu hỏi thật là *dịch lúc đo hay đóng
băng sẵn*. Dịch bằng LLM lúc đo ⇒ mỗi lần chạy một câu khác ⇒ điểm nhảy vì lý do không liên quan tới
thứ đang đo. Một thước đo tự co giãn thì không đo được gì.

**Phải ghi rõ giới hạn kèm theo:** `tests/e2e/score_pipelines.py:89` gọi
`run_kis(q["text_en"], top_k=100)` — KIS **luôn** được chấm trên tiếng Anh đã dịch sẵn, không bao
giờ trên tiếng Việt. Nghĩa là con số KIS đang đo một bài **dễ hơn** bài thi thật.

Điều này chấp nhận được vì đúng với quy trình thật (theo ARCHITECTURE.md, KIS dịch ở tầng UI và
người dùng duyệt câu rewrite bằng mắt trước khi chạy) — nhưng nó là **giả định**, phải viết ra chứ
không để ngầm hiểu. `text_vi` là sự thật; `text_en` là đối chứng; số KIS giả định người dùng đã
duyệt câu dịch.

### 5.4 Cỡ mẫu

Sai số chuẩn của R@k (tỷ lệ, ở mức khó nhất p ≈ 0,5): n=10 → ±16 điểm %; n=20 → ±11; n=30 → ±9;
n=80 → ±5,6.

| | Hiện có | Đề thi sẵn | Tự viết thêm | Đích |
|---|---|---|---|---|
| KIS | 23 | +57 | 0 | **80** |
| Q&A | 5 | +16 | +9 | **30** |
| TRAKE | 10 | +6 | +14 | **30** |
| | 38 | +79 | +23 | **140** |

Nguồn đề thi: `tests/data/thunghiem_bo_de_thi.csv` (24), `tests/data/sotuyen1_bo_de_thi.csv` (25),
`data/extracted/Bo_De_Thi_Dot2/` (30).

**79 câu đề thi là phân phối thật của BTC — đó là giá trị không thay thế được của chúng. Không bịa
thêm câu "cho đa dạng"**, vì làm vậy kéo bộ đo lệch khỏi phân phối thật. Chỗ cần đa dạng là nhãn
`difficulty_tags` (để soi breakdown) và 23 câu tự viết cho QA/TRAKE — hai loại mà đề thi cho quá ít.

Kể cả ở 140 câu, sai số mỗi loại vẫn ~±5–9 điểm %. Vì vậy §7 giữ nguyên: P2.4 và P2.7 **in bảng
số**, không tự chốt tham số.

## 6. Tám mục sửa

Thứ tự cố định. Mỗi mục: sửa → đo → ghi nhật ký → commit.

### Việc 0 — hạ tầng (không đổi hành vi)

`AIC_MODE=local`; `docs/reports/phase2_measurement_log.md`; chốt lại baseline trên 38 câu; chốt lại
golden snapshot trên `main` sau merge.

### P2.8 — production đang import từ `tests/`

`scripts/agent/tools/index_store.py:94` chạy `from multi_index import ...`, nạp module từ
`tests/eval/`. Code chạy thật phụ thuộc code test. Chuyển `multi_index.py` sang
`scripts/agent/tools/`, để `tests/eval/run_eval.py` import ngược lại.
**Digest phải KHỚP** — đây là mục duy nhất như vậy.

### P2.1 — `_QA_MODEL_TAG` mặc định sai

`index_store.py:52` đặt Q&A = `siglip`; docstring `pipeline_qa.py`, ARCHITECTURE.md và bake-off đều
nói `siglip2`. Bake-off 33 câu: **QA Final siglip2 = 0,440 vs siglip = 0,120**. Lọt vào ở commit
`ab0ab32`, nhiều khả năng tai nạn merge. `data/extracted/features_siglip2/` đã có sẵn.
Chênh lệch lớn nhất còn lại trong hệ thống.

### P2.2 — TRAKE `top_k_video=20` khoá cứng R@50 = R@100 = R@20

`pipeline_trake.py:120`. `results` ≤ 20 dòng ⇒ 2 trong 5 hạng của Final bị khoá ở giá trị hạng 20.
Mở lên 100 **không tốn một lượt LLM nào**: giai đoạn 2 chỉ là nhân ma trận trong 1 video + DP
O(N·K²); cổng LLM vẫn chỉ mở cho top-3. Món rẻ nhất trong danh sách.

### P2.3 — `strict_monotonic` loại thẳng video

`pipeline_trake.py:201` `chain is None` → `continue`, video biến mất. Nhưng keyframe cách nhau
~2,5–3 s, còn chuỗi động tác nhanh (giậm nhảy → qua xà → tiếp đất) có thể gói trong <3 s ⇒ hai mốc
rơi vào **cùng một keyframe** ⇒ video đúng bị loại vì lấy mẫu thưa, không phải vì sai.
`find_best_increasing_chain()` đã có sẵn `strict=False`; rơi về đó thay vì bỏ video, và đánh dấu
chuỗi đó là hạ tiêu chuẩn để xếp sau các chuỗi tăng nghiêm ngặt.

### P2.6 — Q&A chỉ trích answer riêng cho 3 cụm đầu

`pipeline_qa.py:44` `MAX_ANSWER_CLUSTERS = 3` ⇒ ~97/100 dòng mang `best_answer` của video **khác**.
Với luật "sai answer = 0 điểm dòng đó", R@20/R@50/R@100 của Q&A bị khoá vào 3 video đầu — khớp đúng
với QA e2e **phẳng 0,200 ở mọi k**.

Hướng rẻ: thêm tham số `max_tier` cho `answer_from_hits()`. Cụm trong top-3 giữ nguyên (Tầng 1 +
Tầng 2 Vision + crosscheck). Cụm từ thứ 4 trở đi chạy `max_tier=1` — chỉ Objects JSON, đúng **một**
lượt gọi LLM văn bản, không Vision, không OCR.

### P2.5 — OCR chết hoàn toàn

Hai đường đều đứt:

1. **Trực tiếp**: `ocr_read.py:92` gọi `Cfg.load_config_from_name("vgg_transformer")`, hàm này tải
   YAML từ `https://vocr.vn/...` mỗi lần khởi động. Chứng chỉ SSL của host **đã hết hạn** (tái hiện
   2026-08-31: `SSLError ... certificate has expired`). YAML đó lại trỏ tới file trọng số cùng host.
2. **Cache offline**: `data/extracted/ocr_text_paddleocr/` **không tồn tại**.

Hệ quả: OCR Direct Overwrite không bao giờ kích hoạt, gợi ý OCR không bao giờ vào prompt Vision,
`rerank_by_ocr` chỉ còn khớp caption.

Tắt **âm thầm** vì cả khối nạp engine nằm trong `try/except Exception` (`ocr_read.py:96`) → in một
dòng cảnh báo → đặt `_ENGINE_LOAD_FAILED = True` → mọi lời gọi sau trả về rỗng. Fail-soft đúng về
nguyên tắc (OCR chỉ là tín hiệu phụ) nhưng khiến OCR chết nhiều ngày không ai biết.

**Cách sửa:** ghim tài sản về máy, đọc từ đĩa. Người dùng đã tải sẵn
`data/extracted/base.yml` và `data/extracted/vgg_transformer.pth` (151 MB); còn thiếu
`vgg-transformer.yml`. Đổi sang `Cfg.load_config_from_file()` + trỏ `config["weights"]` vào file
cục bộ. Hết phụ thuộc `vocr.vn`.

**Kèm theo, bắt buộc:** một lệnh kiểm tra báo đỏ rõ ràng khi thiếu tài sản. Việc tắt âm thầm tự nó
là một lỗi riêng và phải được sửa dù chọn hướng nào.

*Ghi chú về ranh giới:* CLAUDE.md cấm *"precompute OCR/VLM cho toàn bộ 177K keyframe"*. Ý thật của
luật là **không chạy hàng loạt trên đường truy vấn / trên máy dev** — không phải cấm shard chạy trên
Kaggle (`colab_jobs/06_paddleocr_vietocr_shard*/`, `scripts/offline/ocr/run_ocr_shard_local.py` viết
ra chính để làm việc đó). Chữ trong CLAUDE.md hiện đọc ra nghĩa rộng hơn ý; sửa lại cho khớp.

## 7. Hai mục hoãn tới khi ground truth đủ lớn

Cả hai là **chỉnh tham số**, không phải sửa lỗi logic. Trên 38 câu, sai số lấy mẫu (±9 điểm %) lớn
hơn mức cải thiện định đo. Chốt tham số ở cỡ mẫu đó là tinh chỉnh vào nhiễu.

**Quy tắc chung cho cả hai: script CHỈ IN BẢNG SỐ, người đọc tự quyết** — theo đúng tiền lệ
`tests/e2e/test_phase6_margin_sweep.py` (*"CHI IN BANG SO LIEU — khong tu chon nguong tot nhat"*).

### P2.4 — `_bet_mode` chấm điểm ứng viên đào sâu khiến chúng không bao giờ lọt top-100

`rerank.py:260`: `d[score_key] = W_DENSE / (RRF_K + base_rank + i)` ≈ 0,0013369, thấp hơn **mọi**
ứng viên trong pool 500 (ứng viên tệ nhất ≈ 0,0013393). Với `pool=500 > top_k=100` chúng không bao
giờ xuất hiện — trong khi vẫn tốn một lượt encode + nhân ma trận mỗi query. Ý tưởng đặt cược đúng;
cách gán điểm làm nó chết lâm sàng.

### P2.7 — `MARGIN_THRESHOLD = 0,012` hiệu chỉnh trên thang đo của model đã retire

`rerank.py:33`. Comment tự khai là hiệu chỉnh trên cosine CLIP (~0,28–0,31), nhưng CLIP đã retire và
cosine SigLIP thực tế ~0,05–0,15. Đo 2026-08-31 cho thấy margin điển hình 0,0039–0,0528 ⇒ ngưỡng
tuyệt đối 0,012 khiến chế độ ĐẶT CƯỢC bật ở phần lớn truy vấn.

Cả hai quét bằng harness mới `tests/eval/sweep_rerank.py`, dùng lại bộ chấm KIS của
`score_pipelines.py` ⇒ **0 chi phí API**.

## 8. Ngoài phạm vi

- Mở rộng ground truth lên 140 câu — việc tay của người dùng, chạy song song. Pha 2 giao **công cụ**
  và **hướng dẫn**, không tự gán nhãn (AI không xem được video; nhãn do AI đoán là nhãn vòng tròn).
- `multi_index.py` chạy SigLIP trên CPU dù CUDA sẵn sàng (§2.2) — ghi vào PLAN.md, không sửa ở đây.
- Toàn bộ Phase 10 (refine_frame, model_registry, vlm_rerank, ensemble backbone, khử hubness).
- 9 file `CLAUDE.md` theo thư mục đang chưa commit — chờ người dùng xác nhận.

## 9. Nghiệm thu Pha 2

1. `pytest tests/unit` xanh sau **mỗi** mục.
2. `docs/reports/phase2_measurement_log.md` có đủ một khối cho mỗi mục đã làm, kèm digest trước/sau.
3. P2.8 giữ digest **khớp tuyệt đối**; các mục còn lại có digest mới đã ghi lại.
4. Không loại nào có Final Score thấp hơn baseline 38 câu.
5. `_smoke_test.py` chạy qua với `AIC_MODE=local` (chứng minh đường local hoạt động).
6. `EVAL_GUIDE.md` + `normalize_gt.py` đủ để người dùng bắt đầu gán nhãn mà không cần hỏi lại.
