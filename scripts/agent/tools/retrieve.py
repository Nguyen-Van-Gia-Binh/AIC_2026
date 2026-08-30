"""
Công cụ truy xuất keyframe dùng chung cho cả 3 pipeline (KIS / Q&A / TRAKE).

Bọc multi_index.py với per-task singleton pattern — 2 model load độc lập:
    - KIS / TRAKE → siglip  (google/siglip-so400m-patch14-384, features_siglip/)
    - Q&A         → siglip  (google/siglip-so400m-patch14-384, features_siglip/)

Lý do chọn: benchmark 33 query (2026-08-28):
  siglip : KIS=0.744, TRAKE=0.412, ALL=0.549
  siglip2: QA-retrieval=0.440, ALL=0.551
  clip_vitb32 (baseline cũ, đã xoá): ALL=0.290

Escape-hatch (dùng khi thử nghiệm, không phải production):
    AIC_RETRIEVE_MODEL=<tag>  override model cho KIS/TRAKE  (mặc định "siglip")
    AIC_QA_MODEL=<tag>        override model cho Q&A        (mặc định "siglip")
  Tag hợp lệ: xem MODEL_REGISTRY trong tests/eval/multi_index.py

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

# ─── Singleton KIS/TRAKE (mặc định: siglip) ──────────────────────────────────
# Đọc 1 lần lúc import module, không đổi giữa chừng trong 1 process.
_MODEL_TAG = os.environ.get("AIC_RETRIEVE_MODEL", "").strip() or "siglip"

_MATRIX: Optional[np.ndarray] = None
_META = None
_ENCODE_FN: Optional[Callable[[str], np.ndarray]] = None

# ─── Singleton Q&A (mặc định: siglip) ───────────────────────────────────────
_QA_MODEL_TAG = os.environ.get("AIC_QA_MODEL", "").strip() or "siglip"

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
    _eval_dir = _REPO_ROOT / "tests" / "Eval"
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
    """Nạp model Q&A (siglip) nếu chưa nạp."""
    global _QA_MATRIX, _QA_META, _QA_ENCODE_FN
    if _QA_MATRIX is not None:
        return
    print(f"[retrieve] Nạp model Q&A: {_QA_MODEL_TAG}")
    _QA_MATRIX, _QA_META, _QA_ENCODE_FN = _load_model(_QA_MODEL_TAG)


def preload() -> None:
    """Nạp sẵn index + model cho CẢ HAI task ngay bây giờ (không đợi lần gọi đầu tiên).
    KIS/TRAKE và Q&A dùng siglip. app.py gọi hàm này lúc khởi động để UI sẵn sàng
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
    Tìm top_k keyframe bằng model siglip — dùng cho pipeline Q&A.

    Dùng không gian embedding siglip,
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


# ─── Hybrid Retrieval: Dense (SigLIP) + Sparse (BM25) dung hop bang RRF ──────
# BAN DAC TA §2. Dense va Sparse chay doc lap tren CUNG tap keyframe, ket qua dung hop bang
# Reciprocal Rank Fusion (chi dung THU HANG — xem scripts/agent/tools/fusion.py ve ly do khong cong
# thang 2 thang diem). Sparse chua build cache -> tu dong chay dense-only, khong crash.

# Chi muc (video_id, n) -> vi tri dong trong _META / _QA_META, dung de map ket qua BM25 (chi co
# video_id + n) ve dong meta dense day du. Tinh lazy 1 lan/model.
_KEY_INDEX: Optional[dict] = None
_QA_KEY_INDEX: Optional[dict] = None

# So ung vien BM25 dua vao dung hop RRF. CO Y nho hon nhieu so voi pool dense (500): BM25 o day chay
# tren tap tu khoa RAT THO (ten object tu Faster R-CNN + caption, ~5.5K term, doc dai ~10 token) nen
# chi dang tin o phan DINH danh sach — cang xuong sau cang nhieu frame chi trung 1-2 tu chung chung
# ("person", "car"). Do that tren 18 cau KIS (tests, 2026-08-28): dua ca 500 ung vien BM25 vao
# lam Final tut 0.667 -> 0.656; gioi han o dinh giu duoc phan dong gop that ma khong keo rac len.
SPARSE_TOP_K = 50


def _row_to_hit(meta: pd.DataFrame, idx: int, score: float) -> dict:
    """Dung 1 hit dict chuan tu 1 dong meta — dinh dang giong het fast_retrieve()."""
    row = meta.iloc[idx]
    frame_idx = int(row["frame_idx"])
    return {
        "video_id":  row["video_id"],
        "n":         int(row["n"]),
        "frame_idx": frame_idx,
        "frame_id":  frame_idx + 1,   # BTC dem frame tu 1 — quy doi CHI o day (xem CLAUDE.md)
        "pts_time":  float(row["pts_time"]),
        "score":     float(score),
        "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
    }


def _get_key_index(qa: bool = False) -> dict:
    """{(video_id, n): vi tri dong} cho model tuong ung — build 1 lan/process."""
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
    """Encode nhieu cach dien dat cua CUNG 1 truy van roi lay trung binh + chuan hoa L2 —
    q_final = Normalize((q_1 + ... + q_m) / m), BAN DAC TA §3.1 (Multi-Aspect Prompt Expansion).

    Chuan hoa lai la BAT BUOC: ma tran embedding da chuan hoa san (xem index.py), diem so o day la
    dot product = cosine CHI KHI vector truy van cung co norm 1 — trung binh 2 vector don vi khong
    con norm 1.
    """
    encode_fn = _QA_ENCODE_FN if qa else _ENCODE_FN
    vecs = [encode_fn(t) for t in texts if t and t.strip()]
    if not vecs:
        raise ValueError("[retrieve] _encode_mean: khong co text nao hop le de encode")
    q_vec = np.mean(np.stack(vecs, axis=0), axis=0).astype(np.float32)
    norm = float(np.linalg.norm(q_vec))
    return q_vec / norm if norm > 0 else q_vec


def fast_retrieve_multi(texts: list[str], top_k: int = 100, qa: bool = False) -> list[dict]:
    """Nhu fast_retrieve() nhung nhan NHIEU cach dien dat cua cung 1 truy van (Multi-Aspect Prompt
    Expansion — xem scripts/agent/tools/query_expand.py). texts do dai 1 => y het fast_retrieve()."""
    if qa:
        _ensure_qa_loaded()
        matrix, meta = _QA_MATRIX, _QA_META
    else:
        _ensure_loaded()
        matrix, meta = _MATRIX, _META
    top_k = min(top_k, 1000)
    scores = matrix @ _encode_mean(texts, qa=qa)
    top_idx = np.argsort(-scores)[:top_k]
    return [_row_to_hit(meta, int(i), float(scores[i])) for i in top_idx]


def hybrid_retrieve(
    query_text: str,
    top_k: int = 500,
    aspects: list[str] | None = None,
    use_sparse: bool = True,
    qa: bool = False,
    sparse_top_k: int | None = None,
) -> list[dict]:
    """
    Truy xuat lai ghep Dense + Sparse, tra ve pool ung vien da dung hop bang RRF (BAN DAC TA §2).

    Args:
        query_text: Query (tieng Anh cho ket qua tot nhat). Dung cho ca BM25 va (neu khong truyen
                    aspects) cho nhanh dense.
        top_k:      Kich thuoc pool tra ve (mac dinh 500 = RETRIEVAL_POOL_SIZE).
        aspects:    Cac cach dien dat cua cung query cho nhanh dense (query_expand.expand_aspects()).
                    None => chi dung query_text.
        use_sparse: False => chay dense-only (dung de do truoc/sau khi bat hybrid).
        sparse_top_k: So ung vien BM25 dua vao dung hop (None = SPARSE_TOP_K). Nho hon top_k co chu
                    dich — xem SPARSE_TOP_K.
        qa:         True => dung khong gian embedding siglip2 cua Q&A thay vi siglip cua KIS/TRAKE.

    Returns:
        list[dict] cung dinh dang fast_retrieve(), SAP XEP GIAM DAN THEO 'rrf_score', trong do:
          score      — cosine similarity dense GOC (giu nguyen thang do cu cho cac buoc sau)
          rrf_score  — diem dung hop RRF (thu tu list bam theo diem nay)
          rank_dense / rank_sparse — thu hang trong tung he thong (None neu he thong do khong tra ve)
    """
    from scripts.agent.tools.fusion import reciprocal_rank_fusion, RRF_K, W_DENSE, W_SPARSE

    if qa:
        _ensure_qa_loaded()
        matrix, meta = _QA_MATRIX, _QA_META
    else:
        _ensure_loaded()
        matrix, meta = _MATRIX, _META

    texts = aspects if aspects else [query_text]
    dense_scores = matrix @ _encode_mean(texts, qa=qa)
    dense_rows = np.argsort(-dense_scores)[: min(top_k, len(dense_scores))]

    key_of_row = {}
    dense_keys = []
    for r in dense_rows:
        row = meta.iloc[int(r)]
        key = (row["video_id"], int(row["n"]))
        key_of_row[key] = int(r)
        dense_keys.append(key)

    sparse_keys: list = []
    if use_sparse:
        from scripts.agent.tools.sparse_index import search_sparse
        key_index = _get_key_index(qa=qa)
        n_sparse = SPARSE_TOP_K if sparse_top_k is None else sparse_top_k
        for h in search_sparse(query_text, top_k=n_sparse):
            key = (h["video_id"], int(h["n"]))
            row = key_index.get(key)
            if row is None:
                continue  # keyframe co objects/caption nhung khong co trong index dense -> bo qua
            key_of_row.setdefault(key, row)
            sparse_keys.append(key)

    if not sparse_keys:
        # Khong co tin hieu sparse (chua build cache / query khong co token khop) -> dense-only,
        # giu nguyen thu tu cosine de khong khac gi fast_retrieve().
        hits = [_row_to_hit(meta, key_of_row[k], float(dense_scores[key_of_row[k]])) for k in dense_keys]
        for rank, h in enumerate(hits, start=1):
            h["rrf_score"] = W_DENSE / (RRF_K + rank)
            h["rank_dense"], h["rank_sparse"] = rank, None
        return hits

    dense_rank = {k: i for i, k in enumerate(dense_keys, start=1)}
    sparse_rank = {k: i for i, k in enumerate(sparse_keys, start=1)}
    fused = reciprocal_rank_fusion(
        [(dense_keys, W_DENSE), (sparse_keys, W_SPARSE)], top_k=top_k
    )

    hits = []
    for key, rrf in fused:
        row = key_of_row[key]
        hit = _row_to_hit(meta, row, float(dense_scores[row]))
        hit["rrf_score"] = float(rrf)
        hit["rank_dense"] = dense_rank.get(key)
        hit["rank_sparse"] = sparse_rank.get(key)
        hits.append(hit)

    n_sparse_only = sum(1 for h in hits if h["rank_dense"] is None)
    print(f"[retrieve] hybrid: {len(dense_keys)} dense + {len(sparse_keys)} sparse -> {len(hits)} "
          f"ung vien sau RRF ({n_sparse_only} chi den tu BM25)")
    return hits


# ─── Multi-Model RRF: Tong hop ket qua tu nhieu model khac nhau ──────────────
# Dung cho nut "use_model_fusion" trong pipeline_kis — chay vitl14/siglip2/dfn song song roi
# hop nhat bang RRF (chi dung thu hang, khong cong thang diem vi khac thang do).
def fast_retrieve_multi_model(
    query_text: str,
    model_tags: tuple[str, ...] = ("vitl14", "siglip2", "dfn"),
    top_k: int = 500,
    rrf_k: int = 60,
) -> list[dict]:
    """Tim ung vien bang nhieu model roi gop o muc frame bang RRF.

    Khac voi hybrid_retrieve() (dense + sparse cung 1 model), ham nay chay doc lap nhieu model
    CLIP/SigLIP khac nhau va dung hop ket qua — phu hop cho nut 'use_model_fusion' trong
    pipeline_kis.run_kis(). Cac model phai da build index bang kaggle_jobs/.

    Args:
        query_text:   Query text (tieng Anh cho ket qua tot nhat).
        model_tags:   Tap model de thu nghiem — tag hop le xem MODEL_REGISTRY trong multi_index.py.
        top_k:        So ung vien tra ve sau fusion.
        rrf_k:        Hang so RRF (mac dinh 60, theo Cormack et al. 2009).

    Returns:
        list[dict] da sap xep giam dan theo diem RRF tong hop, cung dinh dang fast_retrieve().
    """
    from scripts.agent.tools.fusion import rrf_fuse_hits
    if not model_tags:
        return []

    stream_hits: list[list[dict]] = []
    per_model_top_k = min(max(top_k, 1), 1000)
    for tag in model_tags:
        matrix, meta, encode_fn = _load_model(tag)
        q_vec = encode_fn(query_text)
        scores = matrix @ q_vec
        top_idx = np.argsort(-scores)[:per_model_top_k]
        hits = []
        for idx in top_idx:
            row = meta.iloc[idx]
            frame_idx = int(row["frame_idx"])
            hits.append({
                "video_id": row["video_id"],
                "n":        int(row["n"]),
                "frame_idx": frame_idx,
                "frame_id": frame_idx + 1,
                "pts_time": float(row["pts_time"]),
                "score":    float(scores[idx]),
                "jpg_path": row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
            })
        stream_hits.append(hits)

    fused = rrf_fuse_hits(stream_hits, top_k=top_k, rrf_k=rrf_k)
    print(f"[retrieve] RRF {list(model_tags)}: {len(fused)} fused frame candidates")
    return fused

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
