# AIC2026 — Project Plan

> Cách đọc file này: mỗi Phase là một cột mốc lớn. Trong phiên làm việc mới, đọc
> Phase nào đang 🔄/⏳ và mục Blockers trước, đó là việc cần làm tiếp theo.
> Chi tiết "làm thế nào" không ghi ở đây — xem [ARCHITECTURE.md](ARCHITECTURE.md)
> và code. File này chỉ nối thêm / tick checkbox qua từng phiên, không viết lại.

## Lịch sử

**Lần 1 (Phase 1–4, xong ~19/8/2026)** — chi tiết đầy đủ ở
[docs/_archive/PLAN_Lan1.md](docs/_archive/PLAN_Lan1.md). Dựng nền tảng: retrieval CLIP
`clip-ViT-B-32` + 3 pipeline KIS/QA/TRAKE tuyến tính, agent LLM layer, Gradio UI 4 tab, submission
CSV/ZIP builder + validator, 1 đợt hardening theo code review. Nộp đợt 1: **5.6/10** — nguyên nhân
chính không phải embedding yếu mà là **cạn quota Gemini free-tier** giữa lúc thi.

**Lần 2 (Phase 1–6 round 2, 22/8→04/09/2026)** — chi tiết đầy đủ ở
[docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md). Team 4 người, 5 cải tiến chạy song song
sau bài học đợt 1:
- **Phase 1** `AIC_MODE=test|contest` — chọn model LLM theo chế độ, rẻ lúc dev/mạnh lúc nộp thật.
- **Phase 2** Rewrite thêm rule xử lý phủ định ("không có X" → mô tả dương tính cho CLIP).
- **Phase 3** Risk-aware ranking (`rerank.py`) — "đặt cược" khi 1 video nổi bật rõ, "trải rủi ro"
  khi không; benchmark cuối R@100 tăng 0.522→0.565 trên 23 câu KIS+QA, không regression.
- **Phase 4** TRAKE: DP tìm chuỗi mốc tăng dần điểm cao nhất + cross-check tầng 3 bằng object
  detect khi 2 video top sát điểm.
- **Phase 5** OCR on-demand (PaddleOCR) cho Q&A cần đọc chữ/số, chỉ chạy khi câu hỏi cần và chỉ
  trên vài ảnh candidate tốt nhất.
- **Phase 6** Checkpoint benchmark (bộ eval mở rộng lên 33 câu: 18 KIS + 5 QA + 10 TRAKE) — xác
  nhận không regression toàn bộ Phase 3–5. **Còn 2 việc chưa xong khi archive** (carry-forward
  xuống dưới): Dry-run contest mode, Freeze 03/09.
- Đồng thời đổi kiến trúc LLM: bỏ multi-provider fallback (Gemini/Groq/NVIDIA) của lần 1, chuyển
  sang **1 provider OpenRouter duy nhất** (`OPENROUTER_API_KEY`/`OPENROUTER_MODEL`/
  `OPENROUTER_MODEL_CONTEST`).

**Cập nhật 2026-08-26 — [DECISION.md](DECISION.md)/[EXPERIMENT.md](EXPERIMENT.md) đã dựng lại:**
2 file này chưa từng thật sự lên GitHub — bị chặn bởi `.gitignore` từ đầu (đã gỡ khỏi `.gitignore`),
và máy chứa bản gốc đã bị reset trước khi kịp phát hiện. Đã tổng hợp lại nội dung có thể suy ra được
từ các trích dẫn còn sót trong `docs/_archive/PLAN_Lan2.md`/`ARCHITECTURE.md`/
`docs/superpowers/plans/` — **không phải nguyên văn bản gốc**, cả 2 file đều ghi rõ banner + mục TODO
cho phần chưa dựng lại được. Link trong 2 file archive giờ trỏ đúng, không còn chết.

## Việc carry-forward từ Lần 2 (chưa xong khi archive 2026-08-26)

- [ ] **Dry-run contest mode** — chạy trọn cả 3 pipeline (KIS/QA/TRAKE) với `AIC_MODE=contest`,
  xác nhận model mạnh hơn (`OPENROUTER_MODEL_CONTEST`) thật sự được dùng và hệ thống không chậm/lỗi
  bất thường trước khi nộp. Runbook đầy đủ ở cuối Phase 6 trong
  [docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md).
- [ ] **Freeze 03/09** — mốc quy trình của round 2 (không merge thay đổi mới, chỉ sửa lỗi chặn) —
  xác nhận lại còn áp dụng hay đã lùi lịch trước khi coi round 2 thật sự đóng.

## Phase 7: (chưa đặt tên — chờ scope)

_Chưa có mục tiêu cụ thể cho đợt cải tiến tiếp theo — điền vào đây khi có._

---

## Blockers / Risks

- **Single LLM provider (OpenRouter)** — lần 2 đã bỏ multi-provider fallback (Gemini/Groq/NVIDIA)
  của lần 1 để đơn giản hoá, đổi lại mất lớp dự phòng khi rate-limit đúng lúc thi (chính là nguyên
  nhân mất điểm ở đợt 1). Cân nhắc lại trước round 3 nếu còn phụ thuộc 1 provider duy nhất.
- **Rotation key chưa nhớ trạng thái quota giữa các lần khởi động** (bài học đợt 1) — chưa Phase
  nào ở lần 2 xử lý việc này.
- **`DECISION.md`/`EXPERIMENT.md` vừa dựng lại (2026-08-26) từ dữ liệu gián tiếp, không phải bản
  gốc** — máy cũ chứa bản thật đã bị reset. Xem mục TODO cuối mỗi file cho phần chưa dựng lại được;
  bổ sung dần khi nhớ ra hoặc gặp bài học/quyết định mới — đừng để mất máy lần nữa mới ghi lại.
- **2 việc Dry-run/Freeze của lần 2 chưa xác nhận đã xong** — xem mục carry-forward ở trên.
