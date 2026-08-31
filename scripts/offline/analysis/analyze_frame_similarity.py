"""
analyze_frame_similarity.py — Đo phân phối similarity giữa các keyframe liên tiếp (embedding
SigLIP2) để chọn ngưỡng τ cho chiến lược chọn frame theo "độ khác biệt" thay vì FRAME_STRIDE cố
định (xem trao đổi về scripts/index_ocr_es.py / kaggle_jobs/05_qwen_vl_ocr_caption/).

Bối cảnh: keyframe hiện được trích theo mốc thời gian đều đặn (không theo cảnh) — nhiều frame liên
tiếp trong cùng 1 shot gần như giống hệt nhau về nội dung. data/extracted/features_siglip2/ đã có
sẵn embedding SigLIP2 (768-dim, đã L2-normalize) cho TOÀN BỘ 177.321 keyframe (không cần GPU/chạy
gì mới — dùng lại đúng dữ liệu này). Script này CHƯA chọn frame thật — chỉ đo phân phối + ước lượng
số giờ GPU cần cho vài ngưỡng τ ứng viên, dựa trên số đo thật 2.64s/frame (Vintern-1B-v3.5 trên T4,
SMOKE_TEST 2026-08-23 — đã thay Qwen2.5-VL sau khi tách Phase 1 OCR / Phase 2 caption, xem PLAN.md),
để chọn τ có căn cứ trước khi viết script sinh manifest thật
(scripts/build_ocr_frame_manifest.py — CHƯA viết, viết sau khi chọn được τ).

Thuật toán chọn frame (mô phỏng ở đây để ước lượng, sẽ dùng thật ở bước sinh manifest): với mỗi
video, duyệt frame theo thứ tự n tăng dần, giữ 1 frame nếu:
  (a) cosine similarity giữa frame này và frame ĐÃ GIỮ GẦN NHẤT (không phải frame ngay trước đó)
      < τ, HOẶC
  (b) thời gian (pts_time) từ frame ĐÃ GIỮ GẦN NHẤT >= MAX_GAP_SEC.
So với frame ĐÃ GIỮ GẦN NHẤT (không phải frame liền trước) để bắt được cả trường hợp nội dung trôi
dần qua nhiều frame nhỏ (mỗi bước đều trên ngưỡng nhưng cộng dồn lại đã khác hẳn) — so sánh 2 frame
liền kề sẽ bỏ sót kiểu trôi dần này.

CẢNH BÁO: SigLIP2 (hay CLIP nói chung) đo "cảnh có giống nhau không" ở mức ngữ nghĩa tổng thể —
KHÔNG đảm bảo bắt được thay đổi chữ nhỏ trong khung hình gần như tĩnh (vd đồng hồ đếm số, phụ đề đổi
dòng, nền cảnh y hệt). Chiến lược này phù hợp để giảm dư thừa cho mục tiêu CAPTION; cho riêng OCR
vẫn nên cân nhắc thêm bước lọc riêng (đã trao đổi trước đó) — không coi đây là giải pháp toàn diện
cho OCR.

Usage:
    .venv\\Scripts\\python.exe scripts\\experiments\\analyze_frame_similarity.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = _ROOT / "data" / "extracted"
FEATURES_DIR = DATA_DIR / "features_siglip2" / "features_siglip2"
MAPKF_DIR = DATA_DIR / "map-keyframes"

SEC_PER_FRAME_CAPTION = 2.64       # Vintern-1B-v3.5 trên GPU T4, đo thật SMOKE_TEST 2026-08-23
                                     # (job 07 — thay cho Qwen2.5-VL 11.01s/frame trước đó, không
                                     # dùng nữa cho caption sau khi tách Phase 1/2, xem PLAN.md)
TOTAL_FRAMES_FULL_CORPUS = 177_321  # xem CLAUDE.md
GPU_HOURS_PER_WEEK = 30.0           # quota thật tài khoản thanhnghiphan (kaggle quota, 2026-08-23)

CANDIDATE_THRESHOLDS = [0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
CANDIDATE_MAX_GAP_SEC = [15.0, 30.0, 60.0, 120.0]  # gap-fallback THẬT chi phối kết quả rất mạnh (xem
                                                     # chẩn đoán 2026-08-23: keyframe gốc BTC đã cách
                                                     # nhau median ~4-6s, nên MAX_GAP_SEC=10s cũ gần
                                                     # như luôn trigger fallback, không để similarity
                                                     # lọc — cần quét rộng hơn để thấy tổ hợp đạt ngân
                                                     # sách mục tiêu (~8.800 frame/tuần cho 27h)
SAMPLE_VIDEOS_PER_BATCH = 3    # lấy N video đầu mỗi batch (L21..L30) làm mẫu đại diện, deterministic


def _sample_video_ids() -> list[str]:
    """Chọn mẫu video trải đều các batch (deterministic — N video đầu mỗi batch theo tên, không
    random) để phân phối similarity đo được không lệch về 1 batch cụ thể."""
    npy_files = sorted(FEATURES_DIR.glob("*.npy"))
    by_batch: dict[str, list[str]] = {}
    for p in npy_files:
        video_id = p.stem
        batch = video_id.split("_")[0]
        by_batch.setdefault(batch, []).append(video_id)
    sample = []
    for batch in sorted(by_batch):
        sample.extend(sorted(by_batch[batch])[:SAMPLE_VIDEOS_PER_BATCH])
    return sample


def _load_video(video_id: str) -> tuple[np.ndarray, np.ndarray]:
    emb = np.load(FEATURES_DIR / f"{video_id}.npy").astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = emb / norms  # re-normalize phòng sai số float16, cùng quy ước index_store.py
    df = pd.read_csv(MAPKF_DIR / f"{video_id}.csv")
    if len(df) != emb.shape[0]:
        raise RuntimeError(f"{video_id}: số dòng map-keyframes ({len(df)}) != số vector embedding "
                            f"({emb.shape[0]})")
    return emb, df["pts_time"].to_numpy()


def _select_frames(emb: np.ndarray, pts_time: np.ndarray, tau: float, max_gap_sec: float) -> int:
    """Mô phỏng thuật toán chọn frame ở docstring đầu file. Trả về SỐ LƯỢNG frame được giữ
    (không cần list index thật vì script này chỉ ước lượng, chưa sinh manifest)."""
    n_kept = 1  # luôn giữ frame đầu tiên
    last_kept_idx = 0
    for i in range(1, len(emb)):
        sim = float(np.dot(emb[i], emb[last_kept_idx]))
        gap = pts_time[i] - pts_time[last_kept_idx]
        if sim < tau or gap >= max_gap_sec:
            n_kept += 1
            last_kept_idx = i
    return n_kept


def main():
    video_ids = _sample_video_ids()
    n_batches = len(set(v.split("_")[0] for v in video_ids))
    print(f"[analyze] Mẫu: {len(video_ids)} video trải đều {n_batches} batch")

    all_consec_sims = []
    per_video = {}
    for vid in video_ids:
        emb, pts_time = _load_video(vid)
        sims = np.sum(emb[1:] * emb[:-1], axis=1)  # cosine similarity frame liền kề (đã normalize)
        all_consec_sims.append(sims)
        per_video[vid] = (emb, pts_time)

    all_sims = np.concatenate(all_consec_sims)
    print(f"\n[analyze] Phân phối similarity frame-liền-kề THẬT ({len(all_sims)} cặp, "
          f"{len(video_ids)} video mẫu):")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"  p{p:>2}: {np.percentile(all_sims, p):.4f}")
    print(f"  min/mean/max: {all_sims.min():.4f} / {all_sims.mean():.4f} / {all_sims.max():.4f}")

    total_sample_frames = sum(len(emb) for emb, _ in per_video.values())
    print(f"\n[analyze] Ma trận ƯỚC GIỜ GPU theo τ × MAX_GAP_SEC (dựa trên số đo THẬT "
          f"{SEC_PER_FRAME_CAPTION}s/frame — quota {GPU_HOURS_PER_WEEK}h/tuần, mục tiêu ~1 tuần "
          f"nghĩa là cần cột/hàng nào cho ra dưới ~28h):")
    col_header = "  ".join(f"gap={g:>5.0f}s" for g in CANDIDATE_MAX_GAP_SEC)
    print(f"  {'tau':>6}  {col_header}")
    for tau in CANDIDATE_THRESHOLDS:
        cells = []
        for gap in CANDIDATE_MAX_GAP_SEC:
            n_kept_sample = sum(
                _select_frames(emb, pts_time, tau, gap) for emb, pts_time in per_video.values()
            )
            keep_ratio = n_kept_sample / total_sample_frames
            est_full = keep_ratio * TOTAL_FRAMES_FULL_CORPUS
            est_hours = est_full * SEC_PER_FRAME_CAPTION / 3600
            cells.append(f"{est_hours:>9.1f}h")
        print(f"  {tau:>6.2f}  {'  '.join(cells)}")

    print(f"\n[analyze] Tổng frame mẫu: {total_sample_frames} (từ {len(video_ids)} video). Số ước "
          f"lượng là NGOẠI SUY từ mẫu, không phải chạy full — chỉ dùng để CHỌN (τ, MAX_GAP_SEC) có "
          f"căn cứ, chưa phải kết quả cuối. Ngân sách ~27-29h ứng với ~1 tuần quota còn lại.")


if __name__ == "__main__":
    main()
