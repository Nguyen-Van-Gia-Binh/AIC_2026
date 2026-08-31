"""
sparse_index.py — BM25 sparse index trên Objects JSON (Faster R-CNN/OpenImages) + caption offline
(+ OCR offline nếu có), phục vụ nhánh Hybrid Retrieval (Dense + Sparse -> RRF).

Vì sao cần: SigLIP rất mạnh về ngữ nghĩa thị giác nhưng KHÔNG đọc được chữ/số và dễ bỏ sót
khi query nêu tên object cụ thể ("giraffe", "traffic sign", "bicycle"). BM25 trên tập từ khoá object
+ caption bù đúng khoảng trống đó. Điểm 2 hệ thống KHÔNG cộng trực tiếp (thang đo khác hẳn: cosine
[-1,1] vs BM25 [0,+inf)) — dung hợp bằng RRF, xem scripts/agent/tools/fusion.py.

QUY ƯỚC frame_id: module này CHỈ lưu (video_id, n) — n là số thứ tự keyframe trong map-keyframes.
KHÔNG tự tính frame_id = frame_idx + 1 (quy định CLAUDE.md: chỉ làm ở index_store.row_to_hit()).
Nơi gọi tự map (video_id, n) -> dòng meta dense để lấy frame_idx/frame_id/pts_time.

Cache trên đĩa (BẮT BUỘC phải build trước, ~262K file JSON — không thể build lazy lúc chạy app):
    .venv\\Scripts\\python.exe scripts\\agent\\tools\\sparse_index.py --build
  -> data/extracted/bm25_index/{tf_matrix.npz, docs.npz, vocab.json, stats.json}

Nếu CHƯA build cache: search_sparse() in cảnh báo 1 lần rồi trả về [] — pipeline tự động chạy
dense-only (không crash, không regression). Đây là ngoại lệ có ý của quy ước "fail loud" trong
CLAUDE.md: thiếu sparse index chỉ làm mất 1 tín hiệu phụ, không phải lỗi dữ liệu chí mạng.

Usage:
    from scripts.agent.tools.sparse_index import search_sparse
    hits = search_sparse("a red double decker bus", top_k=500)
    # -> [{"video_id": "L21_V001", "n": 12, "score": 8.31}, ...] đã sắp xếp giảm dần
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DATA_DIR = _ROOT / "data" / "extracted"
OBJECTS_DIR = (
    _DATA_DIR / "objects"
    if (_DATA_DIR / "objects").is_dir()
    else _DATA_DIR / "objects-aic25-b1" / "objects"
)
CAPTION_DIR = _DATA_DIR / "caption_vintern1b" / "caption_vintern1b"
OCR_DIR = _DATA_DIR / "ocr_text_paddleocr"
CACHE_DIR = _DATA_DIR / "bm25_index"

# Ngưỡng confidence object — dùng CHUNG giá trị với objects_lookup.DEFAULT_SCORE_THRESHOLD để 2 đường
# đọc objects (BM25 offline vs tra cứu trực tiếp) không "thấy" 2 tập object khác nhau cho cùng 1 frame.
OBJECT_SCORE_THRESHOLD = 0.3

# Tham so BM25 chuan (Robertson/Sparck Jones) — k1 dieu tiet do bao hoa term frequency, b dieu tiet
# chuẩn hoá theo độ dài document. Giữ mặc định phổ biến; document ở đây rất ngắn (~5-15 token) nên
# BM25 chủ yếu hoạt động như IDF-weighted matching.
BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Từ quá phổ biến trong query tiếng Anh — bỏ đi để BM25 không chấm điểm vì "a/the/of". Danh sách ngắn,
# có ý không dùng stopword list đầy đủ của thư viện ngoài (không thêm dependency — xem CLAUDE.md).
_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "with", "is", "are", "was", "were",
    "be", "being", "been", "for", "from", "by", "as", "that", "this", "these", "those", "it", "its",
    "there", "their", "his", "her", "he", "she", "they", "we", "you", "photo", "image", "video",
    "frame", "scene", "shows", "showing", "shot",
}

_MATRIX_CSC = None          # scipy.sparse.csc_matrix (docs x vocab) — tf tho
_DOC_LEN: Optional[np.ndarray] = None
_AVG_DL: float = 0.0
_IDF: Optional[np.ndarray] = None
_DOC_VIDEO: Optional[np.ndarray] = None
_DOC_N: Optional[np.ndarray] = None
_VOCAB: Optional[dict] = None
_LOAD_FAILED = False


def tokenize(text: str) -> list[str]:
    """Tách token thống nhất cho cả document (objects/caption/OCR) và query — lowercase, bỏ stopword,
    bỏ token 1 ký tự (nhiều OCR rác)."""
    if not text:
        return []
    return [
        t for t in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(t) > 1 and t not in _STOPWORDS
    ]


# --- Build -------------------------------------------------------------------

def _read_objects_text(video_dir: Path) -> dict:
    """Đọc toàn bộ objects JSON của 1 video -> {n: "tên object ..."} (đã lọc theo ngưỡng, giữ unique)."""
    out: dict = {}
    try:
        names = os.listdir(video_dir)
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            n = int(Path(name).stem)
        except ValueError:
            continue
        try:
            data = json.loads((video_dir / name).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entities = data.get("detection_class_entities", [])
        scores = data.get("detection_scores", [])
        seen: set = set()
        kept: list = []
        for entity, score in zip(entities, scores):
            try:
                if float(score) < OBJECT_SCORE_THRESHOLD:
                    continue
            except (TypeError, ValueError):
                continue
            if entity not in seen:
                seen.add(entity)
                kept.append(str(entity))
        out[n] = " ".join(kept)
    return out


def _read_jsonl_text(path: Path, field: str) -> dict:
    """Doc {video_id}.jsonl (caption/OCR offline) -> {n: text}. Thieu file -> {}."""
    out: dict = {}
    if not path.exists():
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    out[int(rec["n"])] = str(rec.get(field, "")).strip()
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
    except OSError:
        return {}
    return out


def _build_one_video(video_id: str) -> list:
    """Worker (chạy trong process con lúc build): trả về [(video_id, n, tokens), ...] cho 1 video."""
    objects_text = _read_objects_text(OBJECTS_DIR / video_id)
    caption_text = _read_jsonl_text(CAPTION_DIR / f"{video_id}.jsonl", "caption")
    ocr_text = _read_jsonl_text(OCR_DIR / f"{video_id}.jsonl", "ocr_text")

    all_n = set(objects_text) | set(caption_text) | set(ocr_text)
    rows: list = []
    for n in sorted(all_n):
        merged = " ".join(
            part for part in (objects_text.get(n, ""), caption_text.get(n, ""), ocr_text.get(n, ""))
            if part
        )
        tokens = tokenize(merged)
        if tokens:
            rows.append((video_id, n, tokens))
    return rows


def build_index(workers: int = 0, force: bool = False) -> None:
    """Quét toàn bộ objects/caption/OCR offline -> ghi cache BM25 vào CACHE_DIR.

    Chạy 1 lần (hoặc khi dữ liệu offline đổi, vd batch job OCR chạy xong). ~262K file JSON nên
    mặc định chạy đa tiến trình (workers = số CPU - 1).
    """
    from scipy import sparse

    if (CACHE_DIR / "tf_matrix.npz").exists() and not force:
        print(f"[sparse_index] Cache đã tồn tại ở {CACHE_DIR} — dùng --force để build lại.")
        return
    if not OBJECTS_DIR.is_dir():
        raise FileNotFoundError(
            f"[sparse_index] Không thấy thư mục objects: {OBJECTS_DIR} — giải nén dữ liệu BTC vào "
            f"data/extracted/ trước khi build BM25 index."
        )

    video_ids = sorted(d for d in os.listdir(OBJECTS_DIR) if (OBJECTS_DIR / d).is_dir())
    print(f"[sparse_index] Build BM25 trên {len(video_ids)} video (objects + caption + OCR offline)...")
    t0 = time.time()

    if workers <= 0:
        workers = max(1, (os.cpu_count() or 2) - 1)

    all_rows: list = []
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, rows in enumerate(pool.map(_build_one_video, video_ids, chunksize=4), start=1):
                all_rows.extend(rows)
                if i % 50 == 0:
                    print(f"[sparse_index]   {i}/{len(video_ids)} video, {len(all_rows)} keyframe "
                          f"({time.time() - t0:.0f}s)", flush=True)
    else:
        for i, vid in enumerate(video_ids, start=1):
            all_rows.extend(_build_one_video(vid))
            if i % 50 == 0:
                print(f"[sparse_index]   {i}/{len(video_ids)} video, {len(all_rows)} keyframe "
                      f"({time.time() - t0:.0f}s)", flush=True)

    if not all_rows:
        raise FileNotFoundError(
            "[sparse_index] Không đọc được document nào — kiểm tra data/extracted/objects/ có dữ liệu thật."
        )

    vocab: dict = {}
    indptr = [0]
    indices: list = []
    data_vals: list = []
    doc_video: list = []
    doc_n: list = []

    for video_id, n, tokens in all_rows:
        counts: dict = {}
        for tok in tokens:
            col = vocab.get(tok)
            if col is None:
                col = len(vocab)
                vocab[tok] = col
            counts[col] = counts.get(col, 0) + 1
        indices.extend(counts.keys())
        data_vals.extend(counts.values())
        indptr.append(len(indices))
        doc_video.append(video_id)
        doc_n.append(n)

    n_docs = len(doc_video)
    tf = sparse.csr_matrix(
        (np.asarray(data_vals, dtype=np.float32), np.asarray(indices, dtype=np.int32),
         np.asarray(indptr, dtype=np.int64)),
        shape=(n_docs, len(vocab)),
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(CACHE_DIR / "tf_matrix.npz", tf)
    np.savez_compressed(
        CACHE_DIR / "docs.npz",
        video_id=np.asarray(doc_video),
        n=np.asarray(doc_n, dtype=np.int32),
    )
    (CACHE_DIR / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")
    (CACHE_DIR / "stats.json").write_text(
        json.dumps({
            "n_docs": n_docs,
            "n_terms": len(vocab),
            "n_videos": len(video_ids),
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "has_ocr_offline": OCR_DIR.is_dir(),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[sparse_index] Xong: {n_docs} document, {len(vocab)} term, {tf.nnz} nnz "
          f"({time.time() - t0:.0f}s) -> {CACHE_DIR}")


# --- Load + search -----------------------------------------------------------

def _ensure_loaded() -> bool:
    """Nạp cache BM25 (1 lần/process). Trả về False nếu chưa build cache — gọi hàm sẽ chạy dense-only."""
    global _MATRIX_CSC, _DOC_LEN, _AVG_DL, _IDF, _DOC_VIDEO, _DOC_N, _VOCAB, _LOAD_FAILED
    if _MATRIX_CSC is not None:
        return True
    if _LOAD_FAILED:
        return False
    if not (CACHE_DIR / "tf_matrix.npz").exists():
        print(f"[sparse_index] CẢNH BÁO: chưa có BM25 cache ({CACHE_DIR}) — chạy dense-only. "
              f"Build bang: .venv\\Scripts\\python.exe scripts\\agent\\tools\\sparse_index.py --build")
        _LOAD_FAILED = True
        return False
    try:
        from scipy import sparse
        tf = sparse.load_npz(CACHE_DIR / "tf_matrix.npz").tocsr()
        docs = np.load(CACHE_DIR / "docs.npz", allow_pickle=True)
        _DOC_VIDEO = docs["video_id"]
        _DOC_N = docs["n"]
        _VOCAB = json.loads((CACHE_DIR / "vocab.json").read_text(encoding="utf-8"))

        _DOC_LEN = np.asarray(tf.sum(axis=1)).ravel().astype(np.float32)
        _AVG_DL = float(_DOC_LEN.mean()) if len(_DOC_LEN) else 1.0
        n_docs = tf.shape[0]
        csc = tf.tocsc()
        df = np.diff(csc.indptr).astype(np.float32)  # số document chứa từng term
        _IDF = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        _MATRIX_CSC = csc
        print(f"[sparse_index] BM25 ready — {n_docs} document / {len(_VOCAB)} term "
              f"(avg_dl={_AVG_DL:.1f})")
        return True
    except Exception as error:
        print(f"[sparse_index] CẢNH BÁO: không nạp được BM25 cache ({type(error).__name__}: {error}) "
              f"— chạy dense-only.")
        _LOAD_FAILED = True
        return False


def search_sparse(query_text: str, top_k: int = 500) -> list:
    """
    Tìm top_k keyframe khớp query bằng BM25 trên objects/caption/OCR offline.

    Returns:
        list[dict] {video_id, n, score} sắp xếp giảm dần theo BM25 score. Trả về [] nếu chưa build
        cache hoặc query không còn token nào trong vocab (không phải lỗi — dense vẫn chạy bình thường).
    """
    if not _ensure_loaded():
        return []
    tokens = tokenize(query_text)
    cols = {c for c in (_VOCAB.get(t) for t in tokens) if c is not None}
    if not cols:
        return []

    scores = np.zeros(_MATRIX_CSC.shape[0], dtype=np.float32)
    len_norm = BM25_K1 * (1.0 - BM25_B + BM25_B * _DOC_LEN / max(_AVG_DL, 1e-6))
    for col in cols:
        start, end = _MATRIX_CSC.indptr[col], _MATRIX_CSC.indptr[col + 1]
        if start == end:
            continue
        rows = _MATRIX_CSC.indices[start:end]
        tf = _MATRIX_CSC.data[start:end]
        scores[rows] += _IDF[col] * (tf * (BM25_K1 + 1.0)) / (tf + len_norm[rows])

    nonzero = np.nonzero(scores)[0]
    if nonzero.size == 0:
        return []
    k = min(top_k, nonzero.size)
    top_local = nonzero[np.argpartition(-scores[nonzero], k - 1)[:k]]
    top_local = top_local[np.argsort(-scores[top_local])]
    return [
        {"video_id": str(_DOC_VIDEO[i]), "n": int(_DOC_N[i]), "score": float(scores[i])}
        for i in top_local
    ]


def is_available() -> bool:
    """True nếu cache BM25 đã build và nạp được — dùng để log/báo cáo trạng thái, không bắt buộc gọi."""
    return _ensure_loaded()

# Bo test: tests/unit/test_sparse_index.py

# --- CLI: build index --------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", action="store_true", help="Build (hoặc rebuild với --force) cache BM25")
    parser.add_argument("--force", action="store_true", help="Ghi đè cache đã có")
    parser.add_argument("--workers", type=int, default=0, help="Số process khi build (0 = CPU-1)")
    parser.add_argument("--query", type=str, default="", help="Thử tìm 1 query trên cache đã build")
    args = parser.parse_args()

    if args.build:
        build_index(workers=args.workers, force=args.force)
    if args.query:
        hits = search_sparse(args.query, top_k=10)
        print(f"[sparse_index] Query {args.query!r}: {len(hits)} hit")
        for h in hits[:10]:
            print(f"  {h['video_id']}  n={h['n']}  bm25={h['score']:.3f}")
    if not args.build and not args.query:
        parser.print_help()
