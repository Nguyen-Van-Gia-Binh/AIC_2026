"""
Công cụ truy xuất keyframe dùng chung cho cả 3 pipeline (KIS / Q&A / TRAKE).

Bọc multi_index.py với per-task singleton pattern — 2 model load độc lập:
  - KIS / TRAKE → siglip  (google/siglip-so400m-patch14-384, features_siglip/)
  - Q&A         → siglip2 (google/siglip2-so400m-patch14-384, features_siglip2/)

Lý do chọn: benchmark 33 query (2026-08-28):
  siglip : KIS=0.744, TRAKE=0.412, ALL=0.549
  siglip2: QA-retrieval=0.440, ALL=0.551
  clip_vitb32 (baseline cũ, đã xoá): ALL=0.290

Escape-hatch (dùng khi thử nghiệm, không phải production):
  AIC_RETRIEVE_MODEL=<tag>  override model cho KIS/TRAKE  (mặc định "siglip")
  AIC_QA_MODEL=<tag>        override model cho Q&A        (mặc định "siglip2")
  Tag hợp lệ: xem MODEL_REGISTRY trong test_eval/Eval/multi_index.py

Usage:
    from scripts.agent.tools.retrieve import fast_retrieve, fast_retrieve_qa
    # KIS / TRAKE:
    results = fast_retrieve("a cyclist on a mountain road", top_k=100)
    # Q&A:
    results = fast_retrieve_qa("a speaker in a white shirt in front of crowd", top_k=100)

PowerShell — thử model khác cho KIS/TRAKE:
    $env:AIC_RETRIEVE_MODEL = "dfn"; .venv\\Scripts\\python.exe scripts\\app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

# Console Windows mặc định dùng code page cp1252, không encode được ký tự có dấu (vd "Đ" trong log
# bên dưới) -> UnicodeEncodeError ngay lúc import module này. Ép stdout sang UTF-8 tại đây (điểm
# import duy nhất của module này) thay vì đòi người dùng phải tự set PYTHONIOENCODING=utf-8 trước khi
# chạy. Bọc try/except vì 1 số môi trường (vd stdout đã bị redirect/pipe trong test) không hỗ trợ
# reconfigure().
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _SCRIPTS_DIR.parent
# Chuẩn hoá: MỌI import nội bộ dùng tiền tố `scripts.` (xem EXPERIMENT.md — trước đây file này nạp
# theo 2 đường dẫn module khác nhau `agent.tools.retrieve` vs `scripts.agent.tools.retrieve`, thành 2
# object riêng trong sys.modules -> index + CLIP model bị nạp 2 lần). Chỉ cần repo root trên sys.path.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ─── Singleton KIS/TRAKE (mặc định: siglip) ─────────────────────────────────
# Đọc 1 lần lúc import module, không đổi giữa chừng trong 1 process.
_MODEL_TAG = os.environ.get("AIC_RETRIEVE_MODEL", "").strip() or "siglip"

_MATRIX: Optional[np.ndarray] = None
_META = None
_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None

# ─── Singleton Q&A (mặc định: siglip2) ──────────────────────────────────────
_QA_MODEL_TAG = os.environ.get("AIC_QA_MODEL", "").strip() or "siglip2"

_QA_MATRIX: Optional[np.ndarray] = None
_QA_META = None
_QA_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None


def _add_jpg_paths(meta: pd.DataFrame) -> pd.DataFrame:
    """Bổ sung cột jpg_path cho meta trả về từ multi_index.get_index() (không có sẵn cột này —
    multi_index.py chỉ phục vụ so điểm retrieval, không cần ảnh preview).

    Tái dùng ĐÚNG logic build_index() ở scripts/index.py dòng ~68-79 (thử đường dẫn lồng batch
    data/extracted/keyframes/{batch}/{video_id}/{n}.jpg trước, fallback đường dẫn phẳng cũ
    .../{video_id}/{n}.jpg). Đặt hàm dùng chung ở đây (không sửa index.py — file baseline production,
    không được đụng) để KIS/Q&A/TRAKE vẫn hiện được ảnh preview khi test model khác baseline.
    """
    keyframes_dir = _SCRIPTS_DIR.parent / "data" / "extracted" / "keyframes"
    jpg_paths: list[Optional[str]] = [None] * len(meta)
    for video_id, group in meta.groupby("video_id", sort=False):
        batch = video_id.split("_")[0]
        kf_dir_nested = keyframes_dir / batch / video_id
        kf_dir_flat = keyframes_dir / video_id
        kf_dir = kf_dir_nested if kf_dir_nested.is_dir() else kf_dir_flat
        for idx, row in group.iterrows():
            jpg_path = kf_dir / f"{int(row['n']):03d}.jpg"
            jpg_paths[idx] = str(jpg_path) if jpg_path.exists() else None
    meta = meta.copy()
    meta["jpg_path"] = jpg_paths
    return meta


def _load_model(tag: str) -> tuple[np.ndarray, object, Callable[[str], np.ndarray]]:
    """Nạp index + encoder cho 1 model tag qua multi_index.py.
    Trả về (matrix, meta_with_jpg_paths, encode_fn).
    """
    _eval_dir = _REPO_ROOT / "test_eval" / "Eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from multi_index import get_index, get_encoder, MODEL_REGISTRY  # noqa: E402
    if tag not in MODEL_REGISTRY:
        raise ValueError(
            f"[retrieve] Tag '{tag}' không hợp lệ — có sẵn: {list(MODEL_REGISTRY.keys())}"
        )
    matrix, meta = get_index(tag)
    meta = _add_jpg_paths(meta)
    n_kf = len(meta)
    n_vid = meta["video_id"].nunique()
    print(f"[retrieve] '{tag}': index ready — {n_kf} keyframe / {n_vid} video")
    encoder = get_encoder(tag)
    encode_fn: Callable[[str], np.ndarray] = (
        lambda text: encoder([text])[0].astype(np.float32)  # noqa: E731
    )
    return matrix, meta, encode_fn


def _ensure_loaded() -> None:
    """Nạp model KIS/TRAKE (siglip) nếu chưa nạp."""
    global _MATRIX, _META, _ENCODE_FN
    if _MATRIX is not None:
        return
    print(f"[retrieve] Nạp model KIS/TRAKE: {_MODEL_TAG}")
    _MATRIX, _META, _ENCODE_FN = _load_model(_MODEL_TAG)


def _ensure_qa_loaded() -> None:
    """Nạp model Q&A (siglip2) nếu chưa nạp."""
    global _QA_MATRIX, _QA_META, _QA_ENCODE_FN
    if _QA_MATRIX is not None:
        return
    print(f"[retrieve] Nạp model Q&A: {_QA_MODEL_TAG}")
    _QA_MATRIX, _QA_META, _QA_ENCODE_FN = _load_model(_QA_MODEL_TAG)


def preload() -> None:
    """Nạp sẵn index + model cho CẢ HAI task ngay bây giờ (không đợi lần gọi đầu tiên).
    KIS/TRAKE dùng siglip; Q&A dùng siglip2. app.py gọi hàm này lúc khởi động để UI sẵn sàng
    truy xuất ngay từ lần search đầu, thay vì người dùng đầu tiên phải chờ load model.
    """
    _ensure_loaded()
    _ensure_qa_loaded()


def fast_retrieve(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe gần nhất với query_text bằng siglip cosine similarity.
    Dùng cho pipeline KIS và TRAKE.

    Returns list of dict:
      video_id  (str):   "L21_V001" (không .mp4)
      n         (int):   keyframe sequence no trong map-keyframes (dùng cho ocr_lookup)
      frame_idx (int):   index gốc từ 0
      frame_id  (int):   frame_idx + 1  — dùng trong submission (BTC tính từ 1)
      pts_time  (float): timestamp giây
      score     (float): cosine similarity
      jpg_path  (str|None)
    """
    _ensure_loaded()
    top_k = min(top_k, 1000)  # trần an toàn, KHÔNG phải giá trị mặc định — xem rerank.RETRIEVAL_POOL_SIZE
    q_vec = _ENCODE_FN(query_text)
    scores = _MATRIX @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    results = []
    for idx in top_idx:
        row = _META.iloc[idx]
        frame_idx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "n":         int(row["n"]),        # keyframe sequence no (for ocr_lookup)
            "frame_idx": frame_idx,
            "frame_id":  frame_idx + 1,
            "pts_time":  float(row["pts_time"]),
            "score":     float(scores[idx]),
            "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
        })
    return results


def fast_retrieve_for_video(query_text: str, video_id: str, top_k: int = 20) -> list[dict]:
    """Như fast_retrieve nhưng chỉ tìm trong 1 video — dùng cho bước Alignment TRAKE."""
    _ensure_loaded()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    q_vec = _ENCODE_FN(query_text)
    local_matrix = _MATRIX[mask.values]
    local_meta   = _META[mask].reset_index(drop=True)
    scores  = local_matrix @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    results = []
    for idx in top_idx:
        row = local_meta.iloc[idx]
        frame_idx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "n":         int(row["n"]),        # keyframe sequence no (for ocr_lookup)
            "frame_idx": frame_idx,
            "frame_id":  frame_idx + 1,
            "pts_time":  float(row["pts_time"]),
            "score":     float(scores[idx]),
            "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
        })
    return results


def fast_retrieve_qa(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe bằng model siglip2 — dùng cho pipeline Q&A.

    Dùng không gian embedding siglip2 (tối ưu đa ngữ cảnh + OCR/VLM reasoning),
    khác với fast_retrieve() dùng siglip (tối ưu visual spotting cho KIS/TRAKE).

    Returns: cùng format với fast_retrieve() — list[dict] với các key:
      video_id (str), n (int), frame_idx (int), frame_id (int),
      pts_time (float), score (float), jpg_path (str|None)
    """
    _ensure_qa_loaded()
    top_k = min(top_k, 1000)
    q_vec = _QA_ENCODE_FN(query_text)
    scores = _QA_MATRIX @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    results = []
    for idx in top_idx:
        row = _QA_META.iloc[idx]
        frame_idx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "n":         int(row["n"]),
            "frame_idx": frame_idx,
            "frame_id":  frame_idx + 1,
            "pts_time":  float(row["pts_time"]),
            "score":     float(scores[idx]),
            "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
        })
    return results


def get_neighbor_frames(video_id: str, frame_idx: int, window: int = 5) -> list[dict]:
    """Tra ve toi da 2*window+1 keyframe LIEN TIEP (theo frame_idx) trong CUNG 1 video, xung quanh
    frame_idx duoc chi dinh — dung cho man chi tiet keyframe (dai frame lan can, mockup man 1c).
    Khong tinh score (khong phai ket qua truy van) — chi tra ve video_id/frame_id/frame_idx/pts_time.
    """
    _ensure_loaded()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    local_meta = _META[mask].sort_values("frame_idx").reset_index(drop=True)
    pos = local_meta.index[local_meta["frame_idx"] == frame_idx]
    if len(pos) == 0:
        return []
    center = int(pos[0])
    lo = max(0, center - window)
    hi = min(len(local_meta), center + window + 1)
    results = []
    for _, row in local_meta.iloc[lo:hi].iterrows():
        fidx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "frame_idx": fidx,
            "frame_id":  fidx + 1,   # BTC dem frame tu 1 — quy doi CHI o day (xem CLAUDE.md)
            "pts_time":  float(row["pts_time"]),
        })
    return results


def get_all_frames(video_id: str) -> list[dict]:
    """Tra ve TOAN BO keyframe cua 1 video (sap theo frame_idx tang dan) — dung cho dai luot
    keyframe day du o man chi tiet KIS (cuon ngang tu frame dau den frame cuoi, thay cho
    get_neighbor_frames chi lay +/- vai frame). Khong tinh score (khong phai ket qua truy van).
    Moi phan tu: {video_id, frame_idx, frame_id, pts_time}.
    """
    _ensure_loaded()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    local_meta = _META[mask].sort_values("frame_idx")
    results = []
    for _, row in local_meta.iterrows():
        fidx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "frame_idx": fidx,
            "frame_id":  fidx + 1,   # BTC dem frame tu 1 — quy doi CHI o day (xem CLAUDE.md)
            "pts_time":  float(row["pts_time"]),
        })
    return results


def get_keyframe_path(video_id: str, frame_idx: int) -> Optional[str]:
    """Tra ve duong dan file .jpg cua keyframe (video_id, frame_idx) — hoac None neu khong co dong
    tuong ung / anh chua giai nen. jpg_path da duoc tinh san luc build index (xem scripts/index.py),
    o day chi tra cuu lai. Dung cho router serve anh (scripts/api/routers/images.py)."""
    _ensure_loaded()
    mask = (_META["video_id"] == video_id) & (_META["frame_idx"] == frame_idx)
    if not mask.any():
        return None
    jpg_path = _META.loc[mask, "jpg_path"].iloc[0]
    if not isinstance(jpg_path, str) or not Path(jpg_path).exists():
        return None
    return jpg_path


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "a person walking on the street"
    print(f"\nQuery: {query!r}")
    hits = fast_retrieve(query, top_k=5)
    print(f"\nTop {len(hits)} results (KIS/TRAKE model = {_MODEL_TAG}):")
    for i, h in enumerate(hits, 1):
        img = "  [img]" if h["jpg_path"] else ""
        print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  score={h['score']:.4f}{img}")
