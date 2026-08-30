"""
sparse_index.py — BM25 sparse index tren Objects JSON (Faster R-CNN/OpenImages) + caption offline
(+ OCR offline neu co), phuc vu nhanh Hybrid Retrieval (Dense + Sparse -> RRF).

Vi sao can: SigLIP/SigLIP2 rat manh ve ngu nghia thi giac nhung KHONG doc duoc chu/so va de bo sot
khi query neu ten object cu the ("giraffe", "traffic sign", "bicycle"). BM25 tren tap tu khoa object
+ caption bu dung khoang trong do. Diem 2 he thong KHONG cong truc tiep (thang do khac han: cosine
[-1,1] vs BM25 [0,+inf)) — dung hop bang RRF, xem scripts/agent/tools/fusion.py.

QUY UOC frame_id: module nay CHI luu (video_id, n) — n la so thu tu keyframe trong map-keyframes.
KHONG tu tinh frame_id = frame_idx + 1 (quy dinh CLAUDE.md: chi lam o retrieve.py). Noi goi
(retrieve.py) tu map (video_id, n) -> dong meta dense de lay frame_idx/frame_id/pts_time.

Cache tren dia (BAT BUOC phai build truoc, ~262K file JSON — khong the build lazy luc chay app):
    .venv\\Scripts\\python.exe scripts\\agent\\tools\\sparse_index.py --build
  -> data/extracted/bm25_index/{tf_matrix.npz, docs.npz, vocab.json, stats.json}

Neu CHUA build cache: search_sparse() in canh bao 1 lan roi tra ve [] — pipeline tu dong chay
dense-only (khong crash, khong regression). Day la ngoai le co y cua quy uoc "fail loud" trong
CLAUDE.md: thieu sparse index chi lam mat 1 tin hieu phu, khong phai loi du lieu chi mang.

Usage:
    from scripts.agent.tools.sparse_index import search_sparse
    hits = search_sparse("a red double decker bus", top_k=500)
    # -> [{"video_id": "L21_V001", "n": 12, "score": 8.31}, ...] da sap xep giam dan
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

# Nguong confidence object — dung CHUNG gia tri voi objects_lookup.DEFAULT_SCORE_THRESHOLD de 2 duong
# doc objects (BM25 offline vs tra cuu truc tiep) khong "thay" 2 tap object khac nhau cho cung 1 frame.
OBJECT_SCORE_THRESHOLD = 0.3

# Tham so BM25 chuan (Robertson/Sparck Jones) — k1 dieu tiet do bao hoa term frequency, b dieu tiet
# chuan hoa theo do dai document. Giu mac dinh pho bien; document o day rat ngan (~5-15 token) nen
# BM25 chu yeu hoat dong nhu IDF-weighted matching.
BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Tu qua pho bien trong query tieng Anh — bo di de BM25 khong cham diem vi "a/the/of". Danh sach ngan,
# co y khong dung stopword list day du cua thu vien ngoai (khong them dependency — xem CLAUDE.md).
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
    """Tach token thong nhat cho ca document (objects/caption/OCR) va query — lowercase, bo stopword,
    bo token 1 ky tu (nhieu OCR rac)."""
    if not text:
        return []
    return [
        t for t in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(t) > 1 and t not in _STOPWORDS
    ]


# --- Build -------------------------------------------------------------------

def _read_objects_text(video_dir: Path) -> dict:
    """Doc toan bo objects JSON cua 1 video -> {n: "ten object ..."} (da loc theo nguong, giu unique)."""
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
    """Worker (chay trong process con luc build): tra ve [(video_id, n, tokens), ...] cho 1 video."""
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
    """Quet toan bo objects/caption/OCR offline -> ghi cache BM25 vao CACHE_DIR.

    Chay 1 lan (hoac khi du lieu offline doi, vd batch job OCR chay xong). ~262K file JSON nen
    mac dinh chay da tien trinh (workers = so CPU - 1).
    """
    from scipy import sparse

    if (CACHE_DIR / "tf_matrix.npz").exists() and not force:
        print(f"[sparse_index] Cache da ton tai o {CACHE_DIR} — dung --force de build lai.")
        return
    if not OBJECTS_DIR.is_dir():
        raise FileNotFoundError(
            f"[sparse_index] Khong thay thu muc objects: {OBJECTS_DIR} — giai nen du lieu BTC vao "
            f"data/extracted/ truoc khi build BM25 index."
        )

    video_ids = sorted(d for d in os.listdir(OBJECTS_DIR) if (OBJECTS_DIR / d).is_dir())
    print(f"[sparse_index] Build BM25 tren {len(video_ids)} video (objects + caption + OCR offline)...")
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
            "[sparse_index] Khong doc duoc document nao — kiem tra data/extracted/objects/ co du lieu that."
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
    """Nap cache BM25 (1 lan/process). Tra ve False neu chua build cache — goi ham se chay dense-only."""
    global _MATRIX_CSC, _DOC_LEN, _AVG_DL, _IDF, _DOC_VIDEO, _DOC_N, _VOCAB, _LOAD_FAILED
    if _MATRIX_CSC is not None:
        return True
    if _LOAD_FAILED:
        return False
    if not (CACHE_DIR / "tf_matrix.npz").exists():
        print(f"[sparse_index] CANH BAO: chua co BM25 cache ({CACHE_DIR}) — chay dense-only. "
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
        df = np.diff(csc.indptr).astype(np.float32)  # so document chua tung term
        _IDF = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        _MATRIX_CSC = csc
        print(f"[sparse_index] BM25 ready — {n_docs} document / {len(_VOCAB)} term "
              f"(avg_dl={_AVG_DL:.1f})")
        return True
    except Exception as error:
        print(f"[sparse_index] CANH BAO: khong nap duoc BM25 cache ({type(error).__name__}: {error}) "
              f"— chay dense-only.")
        _LOAD_FAILED = True
        return False


def search_sparse(query_text: str, top_k: int = 500) -> list:
    """
    Tim top_k keyframe khop query bang BM25 tren objects/caption/OCR offline.

    Returns:
        list[dict] {video_id, n, score} sap xep giam dan theo BM25 score. Tra ve [] neu chua build
        cache hoac query khong con token nao trong vocab (khong phai loi — dense van chay binh thuong).
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
    """True neu cache BM25 da build va nap duoc — dung de log/bao cao trang thai, khong bat buoc goi."""
    return _ensure_loaded()


def _self_test() -> None:
    """Test tokenize + cong thuc BM25 tren index gia (khong dung cache that, khong doc data/)."""
    global _MATRIX_CSC, _DOC_LEN, _AVG_DL, _IDF, _DOC_VIDEO, _DOC_N, _VOCAB
    assert tokenize("A red Double-Decker BUS") == ["red", "double", "decker", "bus"]
    assert tokenize("") == []
    assert tokenize("a of the in") == []
    print("[sparse_index] Self-test tokenize: OK")

    from scipy import sparse as _sp
    _VOCAB = {"bus": 0, "person": 1}
    _MATRIX_CSC = _sp.csc_matrix(np.array([[1, 1], [0, 1], [0, 1]], dtype=np.float32))
    _DOC_LEN = np.array([2, 1, 1], dtype=np.float32)
    _AVG_DL = 4.0 / 3.0
    df_t = np.array([1, 3], dtype=np.float32)
    _IDF = np.log(1.0 + (3 - df_t + 0.5) / (df_t + 0.5)).astype(np.float32)
    _DOC_VIDEO = np.array(["V1", "V2", "V3"])
    _DOC_N = np.array([1, 2, 3], dtype=np.int32)

    out = search_sparse("bus person", top_k=3)
    assert out[0]["video_id"] == "V1", f"Doc chua term hiem 'bus' phai dung dau: {out}"
    assert len(out) == 3, f"Ca 3 doc deu chua 'person' -> phai co diem: {out}"
    assert search_sparse("giraffe") == [], "Term ngoai vocab -> rong"
    print(f"[sparse_index] Self-test BM25: OK ({[(o['video_id'], round(o['score'], 3)) for o in out]})")
    print("[sparse_index] Tat ca self-test PASS")


# --- CLI: build + self-test --------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", action="store_true", help="Build (hoac rebuild voi --force) cache BM25")
    parser.add_argument("--force", action="store_true", help="Ghi de cache da co")
    parser.add_argument("--workers", type=int, default=0, help="So process khi build (0 = CPU-1)")
    parser.add_argument("--query", type=str, default="", help="Thu tim 1 query tren cache da build")
    parser.add_argument("--self-test", action="store_true", help="Test tokenize/BM25 tren du lieu gia")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        sys.exit(0)
    if args.build:
        build_index(workers=args.workers, force=args.force)
    if args.query:
        hits = search_sparse(args.query, top_k=10)
        print(f"[sparse_index] Query {args.query!r}: {len(hits)} hit")
        for h in hits[:10]:
            print(f"  {h['video_id']}  n={h['n']}  bm25={h['score']:.3f}")
    if not args.build and not args.query:
        parser.print_help()
