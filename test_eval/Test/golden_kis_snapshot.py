"""
golden_kis_snapshot.py — Ảnh chụp tất định của TOÀN BỘ đường KIS production.

Vì sao cần: `run_eval.py` chạy trên `multi_index.py` — module đó CỐ Ý không import `retrieve.py`,
nên nó không hề chạm `retrieve.py` / `rerank.py` / pipeline nào. Nó không phát hiện được regression
do refactor tầng production.

`run_kis()` thì KHÔNG gọi LLM (`expand_aspects` là template tất định, `rerank_by_ocr` là PaddleOCR
chạy cục bộ) nên nó tất định — chạy hai lần ra đúng một kết quả. Một lượt gọi phủ:
    index_store -> retrieve -> hybrid -> sparse_index -> fusion -> rerank -> temporal_nms -> ocr_read

Cách dùng:
    # Chốt mốc TRƯỚC khi sửa:
    .venv\\Scripts\\python.exe test_eval\\Test\\golden_kis_snapshot.py --save

    # Sau khi sửa — so từng dòng, thoát code 1 nếu lệch:
    .venv\\Scripts\\python.exe test_eval\\Test\\golden_kis_snapshot.py --check

KHÔNG cần API key. Cần data/extracted/ (index + keyframe) như mọi thứ khác trong repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_EVAL_SET = _ROOT / "test_eval" / "Eval" / "eval_ground_truth.json"
_SNAPSHOT = Path(__file__).resolve().parent / "golden_kis_snapshot.json"

TOP_K = 100


def _load_kis_queries() -> list[dict]:
    """18 câu KIS của bộ eval, giữ nguyên thứ tự trong file để ảnh chụp ổn định."""
    data = json.loads(_EVAL_SET.read_text(encoding="utf-8"))
    return [q for q in data if str(q.get("type", "")).upper() == "KIS"]


def _run(queries: list[dict]) -> dict:
    """Chạy run_kis() cho từng câu, trả về {query_id: [<video_id>:<frame_id>, ...]} theo đúng thứ tự."""
    from scripts.agent.pipeline_kis import run_kis

    out: dict[str, list[str]] = {}
    for i, q in enumerate(queries, 1):
        qid = str(q["query_id"])
        text = q.get("text_en") or q.get("text_vi") or ""
        print(f"\n[golden] ({i}/{len(queries)}) {qid}: {text[:70]!r}", flush=True)
        hits = run_kis(text, top_k=TOP_K)
        out[qid] = [f"{h['video_id']}:{h['frame_id']}" for h in hits]
        print(f"[golden]   -> {len(out[qid])} dòng, đầu tiên = {out[qid][0] if out[qid] else '(rỗng)'}")
    return out


def _digest(results: dict) -> str:
    """Mã băm của toàn bộ ảnh chụp — để so nhanh bằng mắt giữa 2 lần chạy."""
    blob = json.dumps(results, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _report_diff(old: dict, new: dict) -> int:
    """In ra khác biệt từng câu. Trả về số câu lệch."""
    n_bad = 0
    for qid in sorted(set(old) | set(new)):
        a, b = old.get(qid), new.get(qid)
        if a == b:
            continue
        n_bad += 1
        if a is None or b is None:
            print(f"[golden] {qid}: CHỈ có ở {'mốc cũ' if b is None else 'lần chạy mới'}")
            continue
        if len(a) != len(b):
            print(f"[golden] {qid}: số dòng {len(a)} -> {len(b)}")
        for rank, (x, y) in enumerate(zip(a, b), 1):
            if x != y:
                print(f"[golden] {qid}: lệch từ hạng {rank}: {x!r} -> {y!r}")
                break
    return n_bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", action="store_true", help="Chạy và GHI ĐÈ ảnh chụp mốc")
    group.add_argument("--check", action="store_true", help="Chạy và so với ảnh chụp mốc")
    args = parser.parse_args()

    queries = _load_kis_queries()
    print(f"[golden] {len(queries)} câu KIS từ {_EVAL_SET.name}, top_k={TOP_K}")
    results = _run(queries)
    digest = _digest(results)

    if args.save:
        _SNAPSHOT.write_text(
            json.dumps({"top_k": TOP_K, "digest": digest, "results": results},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"\n[golden] Đã ghi mốc: {_SNAPSHOT.name}  digest={digest}  ({len(results)} câu)")
        return 0

    if not _SNAPSHOT.exists():
        print(f"[golden] LỖI: chưa có mốc {_SNAPSHOT.name} — chạy --save trước.")
        return 2

    saved = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    print(f"\n[golden] mốc digest={saved.get('digest')}  |  lần này digest={digest}")
    if saved.get("results") == results:
        print(f"[golden] KHỚP TUYỆT ĐỐI trên {len(results)} câu — hành vi KIS không đổi.")
        return 0

    n_bad = _report_diff(saved.get("results", {}), results)
    print(f"\n[golden] LỆCH ở {n_bad}/{len(results)} câu — hành vi KIS ĐÃ ĐỔI.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
