"""
index_store.py — Sở hữu ma trận embedding + metadata + text encoder (singleton toàn tiến trình).

Tách khỏi retrieve.py 2026-08-31: trước đây state nằm ở biến global của retrieve.py, nhưng
hybrid.py và frames.py đều cần đọc chúng — để chúng import biến private của module khác thì tách
xong còn bẩn hơn trước. Ở đây state có đúng một chủ, ba module kia là consumer thuần.

Hai không gian embedding độc lập, nạp lười, mỗi cái đúng một lần trong một tiến trình:
    KIS / TRAKE → tag từ AIC_RETRIEVE_MODEL (mặc định "siglip")
    Q&A         → tag từ AIC_QA_MODEL       (mặc định "siglip2")
Tag hợp lệ: xem MODEL_REGISTRY trong scripts/agent/tools/multi_index.py.

QUAN TRỌNG — row_to_hit() là ĐIỂM DUY NHẤT trong toàn repo quy đổi frame_id = frame_idx + 1.

Usage:
    from scripts.agent.tools import index_store
    matrix, meta, encode_fn = index_store.get_index(qa=False)
    hit = index_store.row_to_hit(meta, row_idx, score)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

# Console Windows mặc định dùng code page cp1252, không encode được ký tự có dấu -> UnicodeEncodeError
# ngay lúc import module này. Ép stdout sang UTF-8 tại đây thay vì đòi người dùng tự set
# PYTHONIOENCODING=utf-8. Bọc try/except vì 1 số môi trường (stdout đã bị redirect/pipe trong test)
# không hỗ trợ reconfigure().
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _SCRIPTS_DIR.parent

# ─── Singleton KIS/TRAKE ─────────────────────────────────────────────────────
# Đọc 1 lần lúc import module, không đổi giữa chừng trong 1 process.
_MODEL_TAG = os.environ.get("AIC_RETRIEVE_MODEL", "").strip() or "siglip"

_MATRIX: Optional[np.ndarray] = None
_META = None
_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None

# ─── Singleton Q&A ───────────────────────────────────────────────────────────
# siglip2, KHÔNG phải siglip. Bake-off 33 câu (2026-08-28): QA Final siglip2 = 0,440 so với
# siglip = 0,120 — chênh 3,7 lần. Mặc định này từng bị lật về "siglip" ở commit ab0ab32 (nhánh
# song song, merge vào SAU khi baseline được chốt) và sống 3 ngày không ai thấy, vì không có phép
# đo nào phủ Q&A: golden snapshot chỉ phủ KIS, còn run_eval.py không đi qua pipeline Q&A thật.
# Đo lại 2026-08-31 xác nhận: QA Final tụt 0,200 -> 0,040 đúng vì dòng này. Xem PLAN.md P2.1.
_QA_MODEL_TAG = os.environ.get("AIC_QA_MODEL", "").strip() or "siglip2"

_QA_MATRIX: Optional[np.ndarray] = None
_QA_META = None
_QA_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None

# Chỉ mục (video_id, n) -> vị trí dòng trong _META / _QA_META, dùng để map kết quả BM25 (chỉ có
# video_id + n) về dòng meta dense đầy đủ. Tính lazy 1 lần/model.
_KEY_INDEX: Optional[dict] = None
_QA_KEY_INDEX: Optional[dict] = None


def _add_jpg_paths(meta: pd.DataFrame) -> pd.DataFrame:
    """Bổ sung cột jpg_path cho meta trả về từ multi_index.get_index() (không có sẵn cột này —
    multi_index.py chỉ phục vụ so điểm retrieval, không cần ảnh preview).

    Tái dùng ĐÚNG logic build_index() ở index_store._add_jpg_paths() (thử đường dẫn lồng batch
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
    from scripts.agent.tools.multi_index import get_index, get_encoder, MODEL_REGISTRY
    if tag not in MODEL_REGISTRY:
        raise ValueError(
            f"[retrieve] Tag '{tag}' không hợp lệ — có sẵn: {list(MODEL_REGISTRY.keys())}"
        )
    matrix, meta = get_index(tag)
    meta = _add_jpg_paths(meta)
    n_kf = len(meta)
    n_vid = meta["video_id"].nunique()
    print(f"[retrieve] '{tag}': index ready — {n_kf} keyframe / {n_vid} video")
    from functools import lru_cache

    raw_encoder = get_encoder(tag)

    @lru_cache(maxsize=512)
    def _cached_encode(text: str) -> np.ndarray:
        return raw_encoder([text])[0].astype(np.float32)

    encode_fn: Callable[[str], np.ndarray] = _cached_encode
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
    KIS/TRAKE dùng siglip, Q&A dùng siglip2. app.py gọi hàm này lúc khởi động để UI sẵn sàng
    truy xuất ngay từ lần search đầu, thay vì người dùng đầu tiên phải chờ load model.
    """
    _ensure_loaded()
    _ensure_qa_loaded()

def _row_to_hit(meta: pd.DataFrame, idx: int, score: float) -> dict:
    """Dựng 1 hit dict chuẩn từ 1 dòng meta — định dạng dùng chung cho mọi hàm retrieve."""
    row = meta.iloc[idx]
    frame_idx = int(row["frame_idx"])
    return {
        "video_id":  row["video_id"],
        "n":         int(row["n"]),
        "frame_idx": frame_idx,
        "frame_id":  frame_idx + 1,   # BTC đếm frame từ 1 — QUY ĐỔI CHỈ Ở ĐÂY (xem CLAUDE.md)
        "pts_time":  float(row["pts_time"]),
        "score":     float(score),
        "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
    }

def _get_key_index(qa: bool = False) -> dict:
    """{(video_id, n): vị trí dòng} cho model tương ứng — build 1 lần/process."""
    global _KEY_INDEX, _QA_KEY_INDEX
    if qa:
        _ensure_qa_loaded()
        if _QA_KEY_INDEX is None:
            _QA_KEY_INDEX = {
                (vid, int(n)): i
                for i, (vid, n) in enumerate(zip(_QA_META["video_id"], _QA_META["n"]))
            }
        return _QA_KEY_INDEX
    _ensure_loaded()
    if _KEY_INDEX is None:
        _KEY_INDEX = {
            (vid, int(n)): i for i, (vid, n) in enumerate(zip(_META["video_id"], _META["n"]))
        }
    return _KEY_INDEX

def _encode_mean(texts: list[str], qa: bool = False) -> np.ndarray:
    """Encode nhiều cách diễn đạt của CÙNG 1 truy vấn rồi lấy trung bình + chuẩn hoá L2 —
    q_final = Normalize((q_1 + ... + q_m) / m), BAN DAC TA §3.1 (Multi-Aspect Prompt Expansion).

    Chuẩn hoá lại là BẮT BUỘC: ma trận embedding đã chuẩn hoá sẵn, điểm số ở đây là
    dot product = cosine CHỈ KHI vector truy vấn cũng có norm 1 — trung bình 2 vector đơn vị không
    con norm 1.
    """
    encode_fn = _QA_ENCODE_FN if qa else _ENCODE_FN
    vecs = [encode_fn(t) for t in texts if t and t.strip()]
    if not vecs:
        raise ValueError("[index_store] encode_mean: không có text nào hợp lệ để encode")
    q_vec = np.mean(np.stack(vecs, axis=0), axis=0).astype(np.float32)
    norm = float(np.linalg.norm(q_vec))
    return q_vec / norm if norm > 0 else q_vec

# ─── API công khai ───────────────────────────────────────────────────────────

def get_index(qa: bool = False):
    """Trả về (matrix, meta, encode_fn) của không gian embedding tương ứng. Nạp lười, 1 lần/process."""
    if qa:
        _ensure_qa_loaded()
        return _QA_MATRIX, _QA_META, _QA_ENCODE_FN
    _ensure_loaded()
    return _MATRIX, _META, _ENCODE_FN


def key_index(qa: bool = False) -> dict:
    """{(video_id, n): vị trí dòng} — dùng để map kết quả BM25 về dòng meta dense."""
    return _get_key_index(qa=qa)


def row_to_hit(meta: pd.DataFrame, idx: int, score: float) -> dict:
    """Dựng hit dict chuẩn từ 1 dòng meta.

    ĐÂY LÀ ĐIỂM DUY NHẤT trong toàn repo quy đổi frame_id = frame_idx + 1 (BTC đếm frame từ 1,
    index đếm từ 0). Không cộng/trừ frame_id ở bất kỳ chỗ nào khác — xem CLAUDE.md.
    """
    return _row_to_hit(meta, idx, score)


def encode_mean(texts: list[str], qa: bool = False) -> np.ndarray:
    """Encode nhiều cách diễn đạt của CÙNG 1 truy vấn rồi lấy trung bình + chuẩn hoá L2."""
    return _encode_mean(texts, qa=qa)


def load_model(tag: str):
    """Nạp index + encoder cho 1 model tag bất kỳ (dùng cho multi-model RRF). Không cache."""
    return _load_model(tag)


def model_tags() -> tuple[str, str]:
    """(tag đang dùng cho KIS/TRAKE, tag đang dùng cho Q&A) — để log/chẩn đoán."""
    return _MODEL_TAG, _QA_MODEL_TAG
