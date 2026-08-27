"""
Công cụ truy xuất keyframe dùng chung cho cả 3 pipeline (KIS / Q&A / TRAKE).

Bọc index.py với singleton pattern: build_index() chỉ chạy 1 lần per process.

Chọn model embedding qua biến môi trường AIC_RETRIEVE_MODEL (mặc định / không set =
"clip_vitb32" — baseline duy nhất đã kiểm chứng, luồng này KHÔNG đổi, không route qua
test_eval/Eval/multi_index.py). Set thành "vitl14" / "siglip" / "dfn" để dùng thử model khác đã
encode sẵn (Kaggle jobs, xem PLAN.md Phase 6) qua test_eval/Eval/multi_index.py — chỉ dùng để
so sánh điểm ở Vòng thử nghiệm, KHÔNG đổi mặc định.

Usage:
    from scripts.agent.tools.retrieve import fast_retrieve
    results = fast_retrieve("a person walking on the street", top_k=100)

    # PowerShell — chọn model khác baseline cho 1 phiên chạy app.py:
    #   $env:AIC_RETRIEVE_MODEL = "dfn"; .venv\\Scripts\\python.exe scripts\\app.py
    # Revert về baseline (bỏ biến môi trường, hoặc set lại "clip_vitb32"):
    #   Remove-Item Env:\\AIC_RETRIEVE_MODEL; .venv\\Scripts\\python.exe scripts\\app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

# Console Windows mac dinh dung code page cp1252, khong encode duoc ky tu co dau (vd "Đ" trong log
# ben duoi) -> UnicodeEncodeError ngay luc import module nay. Ep stdout sang UTF-8 tai day (diem
# import duy nhat cua module nay) thay vi doi nguoi dung phai tu set PYTHONIOENCODING=utf-8 truoc khi
# chay (PLAN.md Phase 6). Boc try/except vi 1 so moi truong (vd stdout da bi redirect/pipe trong test)
# khong ho tro reconfigure().
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _SCRIPTS_DIR.parent
# Chuan hoa: MOI import noi bo dung tien to `scripts.` (xem EXPERIMENT.md — truoc day file nay nap
# theo 2 duong dan module khac nhau `agent.tools.retrieve` vs `scripts.agent.tools.retrieve`, thanh 2
# object rieng trong sys.modules -> index + CLIP model bi nap 2 lan). Chi can repo root tren sys.path.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.index import build_index  # noqa: E402

# Tag model đang dùng — đọc 1 lần lúc import module, không đổi giữa chừng trong 1 process.
_MODEL_TAG = os.environ.get("AIC_RETRIEVE_MODEL", "").strip() or "clip_vitb32"

_MATRIX: Optional[np.ndarray] = None
_META = None
_MODEL = None                                   # chỉ dùng cho baseline clip_vitb32 (giữ nguyên như cũ)
_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None  # encode(text) -> vector float32, dùng chung mọi model


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


def _ensure_loaded() -> None:
    global _MATRIX, _META, _MODEL, _ENCODE_FN
    if _MATRIX is not None:
        return

    print(f"[retrieve] ĐANG DÙNG MODEL: {_MODEL_TAG}")

    if _MODEL_TAG == "clip_vitb32":
        # Luồng mặc định — GIỮ NGUYÊN 100% như trước khi có AIC_RETRIEVE_MODEL. Model duy nhất đã
        # kiểm chứng, không route qua multi_index.py, không được phép có regression ở đây.
        print("[retrieve] Building index...", flush=True)
        _MATRIX, _META = build_index()
        n_kf = len(_META)
        n_vid = _META["video_id"].nunique()
        print(f"[retrieve] Index ready: {n_kf} keyframes / {n_vid} videos")
        print("[retrieve] Loading CLIP model...", flush=True)
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("clip-ViT-B-32")
        _ENCODE_FN = lambda text: _MODEL.encode([text], normalize_embeddings=True)[0].astype(np.float32)  # noqa: E731
        print("[retrieve] Ready.")
        return

    # Model khác baseline (vitl14 / siglip / dfn) — nạp qua test_eval/Eval/multi_index.py (đã viết
    # sẵn cho Phase 6), KHÔNG viết lại logic load model ở đây.
    _eval_dir = _SCRIPTS_DIR.parent / "test_eval" / "Eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from multi_index import get_index, get_encoder, MODEL_REGISTRY
    if _MODEL_TAG not in MODEL_REGISTRY:
        raise ValueError(
            f"[retrieve] AIC_RETRIEVE_MODEL='{_MODEL_TAG}' không hợp lệ — có sẵn: "
            f"{list(MODEL_REGISTRY.keys())}"
        )
    _MATRIX, _META = get_index(_MODEL_TAG)
    _META = _add_jpg_paths(_META)
    n_kf = len(_META)
    n_vid = _META["video_id"].nunique()
    print(f"[retrieve] Index ready: {n_kf} keyframes / {n_vid} videos")
    encoder = get_encoder(_MODEL_TAG)
    _ENCODE_FN = lambda text: encoder([text])[0].astype(np.float32)  # noqa: E731
    print("[retrieve] Ready.")


def preload() -> None:
    """Nap san index + model NGAY BAY GIO, khong doi lan goi fast_retrieve()/fast_retrieve_for_video()
    dau tien. Mac dinh module nay lazy-load (chi nap khi can, qua _ensure_loaded()) de cac script
    ngan/import phu khong ganh chi phi nap model neu khong dung toi. app.py goi ham nay luc khoi dong
    de UI san sang truy xuat ngay tu lan search dau, thay vi nguoi dung dau tien phai cho load model.
    """
    _ensure_loaded()


def fast_retrieve(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe gần nhất với query_text bằng CLIP cosine similarity.

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
    top_k = min(top_k, 1000)  # tran an toan, KHONG phai gia tri mac dinh — xem rerank.RETRIEVAL_POOL_SIZE
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
    print(f"\nTop {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        img = "  [img]" if h["jpg_path"] else ""
        print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  score={h['score']:.4f}{img}")
