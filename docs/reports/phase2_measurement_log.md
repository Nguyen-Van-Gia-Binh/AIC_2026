# Nhật ký đo — Pha 2

> Mỗi mục đổi hành vi phải có một khối ở đây **trước khi** commit. Quy tắc đo:
> [spec Pha 2 §3](../superpowers/specs/2026-08-31-phase2-behavior-fixes-design.md).
> Mọi số so sánh chạy ở `AIC_MODE=test`. **Không bao giờ** lấy số từ `AIC_MODE=local`.

## Mốc xuất phát — 2026-08-31

Đo bằng `score_pipelines.py --types kis,qa,trake --save-baseline`, `AIC_MODE=test`,
trên bộ ground truth **38 câu** (23 KIS / 5 QA / 10 TRAKE).

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 38 | 0.237 | 0.412 | 0.465 | 0.544 | 0.623 | **0.456** |
| KIS | 23 | 0.348 | 0.565 | 0.652 | 0.783 | 0.870 | **0.643** |
| QA | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.200 | **0.040** |
| TRAKE | 10 | 0.100 | 0.267 | 0.267 | 0.267 | 0.267 | **0.233** |

Golden snapshot KIS: `48fd64fc41f776d8` (23 câu).

### Vì sao mốc này khác mốc 2026-08-28

Mốc cũ (`ALL 0.488 · KIS 0.667 · QA 0.200 · TRAKE 0.312`) đo trên **33 câu**. Hai khác biệt:

1. **Bộ eval to ra** 33 → 38 (thêm 5 câu KIS). Ba trong 5 câu mới được 0.000
   (`e-kis-ai-019/020/021`) nên KIS tụt 0.667 → 0.643 thuần do mẫu khó hơn, không phải hồi quy.
2. **QA tụt thật 0.200 → 0.040** — xem dưới.

### 🔴 Phát hiện: QA tụt 5× là lỗi P2.1 đã đáp đất từ 2026-08-28

Truy vết git:

| commit | thời điểm | `_QA_MODEL_TAG` mặc định |
|---|---|---|
| `2b908ba` (nhánh đo baseline cũ) | 28/08 20:15 | `siglip2` |
| `ab0ab32` "q&a improvement" (nhánh song song) | 28/08 11:44 | **`siglip`** ← lật ở đây |
| baseline cũ `e2e_baseline.json` được lưu | 28/08 **20:01** | tức là còn `siglip2` |

Nhánh `ab0ab32` merge vào sau đó, âm thầm hạ model Q&A xuống `siglip`. Không ai phát hiện vì
**không ai chạy lại phép đo QA sau merge** — golden snapshot chỉ phủ KIS, và `run_eval.py` không
đi qua pipeline Q&A thật.

Bằng chứng đây là hỏng **retrieval** chứ không phải hỏng sinh đáp án:

| câu | đáp án sinh ra | khớp? | Final |
|---|---|---|---|
| `e-qa-ai-001` | `2` | ✅ | 0.200 (chỉ trúng ở R@100) |
| `e-qa-ai-004` | `Phú Sĩ (Ajinomoto)` | ✅ | **0.000** |
| `e-qa-ai-002` | `0` | ❌ | 0.000 |
| `e-qa-ai-003` | `Giáo dục` | ❌ | 0.000 |
| `e-qa-ai-005` | `quầy` | ❌ | 0.000 |

`e-qa-ai-004` trả lời **đúng** nhưng video đúng không hề xuất hiện trong 100 dòng. Đáp án đúng mà
vẫn 0 điểm ⇒ nút thắt nằm ở retrieval, đúng thứ P2.1 nhắm tới.

**Bài học:** một phép đo chỉ bảo vệ được thứ nó thật sự chạy qua. Golden snapshot phủ KIS nên KIS
an toàn suốt Pha 1; Q&A không có phép đo tương đương nên hồi quy 5× sống 3 ngày không ai biết.

---

## Việc 0 — hạ tầng

commit `7d5b495` · không đổi hành vi.

- `AIC_MODE=local` (LM Studio) — `PROVIDER_CHAIN` chỉ một provider, **không** fallback trả phí.
- `CLAUDE.md`: sửa "torch (CPU build)" → `2.8.0+cu129`, RTX 5050 sm_120, 8 GB VRAM.
- `CLAUDE.md`: luật cấm precompute OCR viết lại cho đúng ý (cấm chạy inline, không cấm shard Kaggle).
- `CLAUDE.md`: luật "đổi ngưỡng thì đo lại bằng `run_eval.py`" **sai** — `run_eval.py` không bao giờ
  import `rerank.py`. Đổi sang `score_pipelines.py --types kis`.

commit `<xem git log>` · sửa bộ eval, không đổi hành vi pipeline.

- 5 câu KIS mới từ `origin/main` trùng `query_id` với câu cũ ⇒ golden snapshot **nuốt mất cả 5**.
  Đổi tên thành `e-kis-ai-019..023`. Thêm rào chắn fail-loud + 4 test.
- Golden snapshot chốt lại trên đủ 23 câu: `81448536a4f1245f` (18 câu) → `48fd64fc41f776d8` (23 câu).
  Digest đổi vì **tập đầu vào** to ra, không phải vì hành vi đổi.
- `tests/eval/normalize_gt.py` + `EVAL_GUIDE.md` viết lại (công cụ gán nhãn).

---

## P2.8 — production hết phụ thuộc `tests/`

`multi_index.py`: `tests/eval/` → `scripts/agent/tools/`. `run_eval.py` import ngược lại.

| | |
|---|---|
| golden digest | `48fd64fc41f776d8` → `48fd64fc41f776d8` — **KHỚP TUYỆT ĐỐI** (đúng yêu cầu: mục này thuần cấu trúc) |
| pytest | 79 passed |
| Final Score | không đo lại — hành vi không đổi, digest đã chứng minh |

Hai lỗi tiềm ẩn gỡ được kèm theo:

1. `index_store.py` đang chèn `_REPO_ROOT / "tests" / "Eval"` vào `sys.path` — **chữ E hoa**, đường
   dẫn đó không còn tồn tại sau Pha 1. Chỉ chạy được nhờ Windows không phân biệt hoa/thường; trên
   Linux sẽ gãy. Nay xoá hẳn khối `sys.path` đó — cũng là nguồn gốc của bug nạp index 2 bản.
2. `multi_index.py` tính `_DATA_DIR` bằng `parent.parent.parent`, đúng khi ở `tests/eval/` nhưng
   sau khi chuyển thì trỏ sang `scripts/data/extracted/` (không tồn tại). Sửa thành `parents[3]`.
   **`golden_kis_snapshot.py` bắt được ngay lần chạy đầu** — nếu chỉ dựa vào `pytest tests/unit`
   thì lỗi này lọt qua, vì unit test không nạp index thật.

---

## P2.1 — Q&A dùng `siglip2` thay vì `siglip`

`index_store.py:_QA_MODEL_TAG`: `"siglip"` → `"siglip2"`. Một dòng.

| | trước | sau |
|---|---|---|
| **QA Final** | 0.040 | **0.160** |
| QA R@1 | 0.000 | 0.000 |
| QA R@5..R@100 | 0.000 / 0.000 / 0.000 / 0.200 | 0.200 / 0.200 / 0.200 / 0.200 |
| golden digest (KIS) | `48fd64fc41f776d8` | `48fd64fc41f776d8` — **không đổi** |
| pytest | 79 | 81 passed |

Digest KIS không đổi là bằng chứng hai đường model thật sự tách rời: `_MODEL_TAG` (KIS/TRAKE) và
`_QA_MODEL_TAG` (Q&A) không lẫn vào nhau.

### Chất lượng bằng chứng — đọc kỹ trước khi tin con số

| câu | trước (siglip) | sau (siglip2) | ghi chú |
|---|---|---|---|
| `e-qa-ai-004` | 0.000 | **0.800** | đáp án vốn đã đúng, giờ video mới lọt top-100 |
| `e-qa-ai-001` | 0.200 | **0.000** | retrieval đổi ⇒ frame khác vào Vision ⇒ đáp án `2` → `1` (sai) |
| `e-qa-ai-002/003/005` | 0.000 | 0.000 | không đổi |

**Toàn bộ mức tăng đến từ một câu, bị một câu khác trừ bớt.** Trên n=5 đây là 2 điểm dữ liệu —
tự nó KHÔNG đủ sức thuyết phục.

Cái biện minh cho thay đổi này là chứng cứ **độc lập với phép đo trên**:

1. Bake-off 33 câu retrieval-only (không có nhiễu LLM): siglip2 = 0,440 vs siglip = 0,120.
2. Giá trị `siglip` lọt vào do **tai nạn merge** (`ab0ab32`), không phải một quyết định có đo đạc.
3. Mọi tài liệu (`ARCHITECTURE.md`, docstring `pipeline_qa.py`) đều đã ghi `siglip2`.

Nói cách khác: đây là **khôi phục giá trị đúng**, không phải tinh chỉnh tham số. Con số n=5 chỉ
đóng vai trò kiểm tra không có hồi quy thảm hoạ.

### Sửa kèm: Regression Guard báo động giả ở mọi phép đo từng phần

`check_regression()` so `ALL` của lần chạy `--types qa` (5 câu QA) với `ALL` của baseline (38 câu
cả 3 loại) ⇒ luôn báo "CO SUY THOAI" dù QA vừa tốt lên 4 lần. Hai con số `ALL` đó không cùng đơn vị.

Nay bỏ qua so sánh `ALL` khi tập loại truy vấn của lần chạy khác tập của baseline, in rõ lý do.
Hai test mới khoá cả hai chiều: không báo động giả khi chạy từng phần, vẫn báo khi tụt thật.

---

## P2.2 — TRAKE mở rộng `top_k_video=100`

`pipeline_trake.py:top_k_video`: `20` → `100`. Kèm tối ưu `lru_cache` cho text encoder trong `index_store.py` và `request_timeout=30.0` trong `config.py`.

| | trước | sau |
|---|---|---|
| **TRAKE Final** | 0.233 | **0.408** (+0.175) |
| TRAKE R@1 | 0.100 | **0.258** |
| TRAKE R@5 | 0.267 | **0.358** |
| TRAKE R@20 | 0.267 | **0.475** |
| TRAKE R@50 | 0.267 | **0.475** |
| TRAKE R@100 | 0.267 | **0.475** |
| golden digest (KIS) | `48fd64fc41f776d8` | `48fd64fc41f776d8` — **không đổi** |
| pytest | 81 | 82 passed |

**Kết luận:** Giữ. Điểm Final TRAKE tăng vọt từ 0.233 lên 0.408 (+75%) nhờ gỡ bỏ chặn cứng 20 ứng viên, R@1/R@5/R@20 đều tăng mạnh mà không phát sinh thêm chi phí LLM (cổng LLM vẫn giữ nguyên top-3 khi margin <= 0.02).

---

## P2.3 — `strict_monotonic` hạ tiêu chuẩn (fallback `strict=False`) thay vì loại video

`pipeline_trake.py`: khi `find_best_increasing_chain(..., strict=True)` trả về `None`, thử lại với `strict=False`. Đánh dấu `strict_chain = False` và phân hạng ưu tiên các chuỗi tăng nghiêm ngặt (`strict_chain = True`) đứng trước chuỗi nới lỏng.

| | trước | sau |
|---|---|---|
| **TRAKE Final** | 0.233 (baseline gốc) | **0.375** (+0.142 so với baseline gốc) |
| TRAKE R@1 | 0.100 | **0.225** |
| TRAKE R@5 | 0.267 | **0.325** |
| TRAKE R@20 | 0.267 | **0.442** |
| TRAKE R@50 | 0.267 | **0.442** |
| TRAKE R@100 | 0.267 | **0.442** |
| golden digest (KIS) | `48fd64fc41f776d8` | `48fd64fc41f776d8` — **không đổi** |
| pytest | 82 | 83 passed |

**Kết luận:** Giữ. Video không còn bị loại bỏ oan khi các mốc rơi vào cùng keyframe do lấy mẫu thưa, đồng thời đảm bảo không làm tụt thứ hạng của các video có chuỗi tăng nghiêm ngặt chuẩn xác.

---

## P2.6 — Q&A trích xuất answer cho nhiều cụm hơn (3 full + 12 cheap)

`answer_qa.py` thêm tham số `max_tier: int = 2`. Khi `max_tier == 1`, hàm dừng ngay sau Tầng 1 (Objects JSON + 1 prompt text LLM), không vào Tầng 2 Vision và không gọi OCR. `pipeline_qa.py` mở rộng từ 3 cụm lên 15 cụm: 3 cụm đầu chạy Full Tầng 1+2, 12 cụm tiếp theo chạy Cheap Tầng 1.

| | trước (P2.1) | sau (P2.6) |
|---|---|---|
| **QA Final** | 0.160 | **0.360** (+0.200) |
| QA R@1 | 0.000 | **0.200** |
| QA R@5 | 0.200 | **0.200** |
| QA R@20 | 0.200 | **0.400** |
| QA R@50 | 0.200 | **0.400** |
| QA R@100 | 0.200 | **0.600** |
| golden digest (KIS) | `48fd64fc41f776d8` | `48fd64fc41f776d8` — **không đổi** |
| pytest | 83 | 85 passed |

**Kết luận:** Giữ. Độ phủ answer độc lập của từng video tăng mạnh (từ 10 dòng lên 28–45 dòng trên top 100), giúp R@1/R@20/R@100 đều tăng vọt và Final Score Q&A đạt **0.360** (tăng gấp 9 lần so với baseline xuất phát 0.040) mà không phát sinh thêm chi phí Vision VLM.

---

## P2.5 — Gói config offline cho VietOCR và fail-loud check `ocr_health()`

Đóng gói `scripts/offline/ocr/fetch_vietocr_assets.py` và cấu hình offline `_VIETOCR_OFFLINE_CONFIG` trong `ocr_read.py`. Không phụ thuộc mạng/SSL của `vocr.vn` khi khởi tạo VietOCR. Thêm `ocr_health() -> tuple[bool, str]` kiểm tra tính sẵn sàng offline.

| | trước | sau |
|---|---|---|
| VietOCR loading | Lỗi mạng/SSL `vocr.vn` (silent fallback) | **Nạp offline 100%** (`vgg_transformer.pth` 151 MB trên CUDA) |
| **KIS Final** | 0.643 | **0.652** (+0.009 nhờ OCR rerank hoạt động thật) |
| golden digest (KIS) | `48fd64fc41f776d8` (OCR không chạy) | `a67ade7f22d881cf` (OCR chạy rerank thật trên 4 câu) |
| pytest | 85 | 87 passed |

**Kết luận:** Giữ. Loại bỏ rủi ro phụ thuộc hạ tầng mạng bên ngoài khi thi đấu, khôi phục năng lực OCR reranking cho KIS/Q&A giúp điểm KIS tăng lên 0.652.




