"""
widen_gt_windows.py — Noi khoang [gt_frame_start, gt_frame_end] cho cac entry dang single-frame
(start == end) trong eval_ground_truth.json, suy tu keyframe lan can trong
data/extracted/map-keyframes/{video_id}.csv.

Ly do: he thong chi tra ve duoc frame_id CUA KEYFRAME (khong phai frame video bat ky), nen
gt_frame_start == gt_frame_end lam dieu kien "frame in [s,e]" chat hon dinh nghia [s,e] cua BTC
(docs/Thong tin vong So tuyen AIC2026.md §2.1) — 1 model tra ve keyframe lien ke (lech dung 1 buoc
lay mau) bi 0 diem oan, lam diem eval nhieu va mat kha nang phan biet model. Noi ra +-1 keyframe la
gioi han duoi hop ly; NGUOI VAN NEN DO TAY LAI bang mat sau khi chay (xem EVAL_GUIDE.md).

Tai dung logic doc map-keyframes cua lookup_frame.py (frame_id = frame_idx + 1). CHI sua entry dang
start == end — entry da co khoang that giu nguyen. In bang before -> after de doi chieu.

Usage:
    .venv\\Scripts\\python.exe tests\\Eval\\widen_gt_windows.py
    .venv\\Scripts\\python.exe tests\\Eval\\widen_gt_windows.py --dry-run   # chi in, khong ghi file
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # tests/eval/ -> repo root
_MAPKF_DIR = _REPO_ROOT / "data" / "extracted" / "map-keyframes"
_EVAL_SET = _THIS_DIR / "eval_ground_truth.json"

_MAP_CACHE: dict[str, pd.DataFrame] = {}


def _load_map(video_id: str) -> pd.DataFrame:
    if video_id not in _MAP_CACHE:
        csv_path = _MAPKF_DIR / f"{video_id}.csv"
        if not csv_path.exists():
            raise SystemExit(
                f"[widen_gt] Khong thay {csv_path} — da giai nen data/ chua? "
                f"(can data/extracted/map-keyframes/{video_id}.csv de noi khoang)"
            )
        df = pd.read_csv(csv_path)
        df["frame_id"] = df["frame_idx"] + 1
        _MAP_CACHE[video_id] = df
    return _MAP_CACHE[video_id]


def _widen_one(video_id: str, frame_val: int) -> tuple[int, int]:
    """Tra ve (new_start, new_end) = frame_id cua keyframe truoc/sau keyframe gan frame_val nhat."""
    df = _load_map(video_id)
    exact = df.index[df["frame_id"] == frame_val].tolist()
    idx = exact[0] if exact else int((df["frame_id"] - frame_val).abs().idxmin())
    lo = max(0, idx - 1)
    hi = min(len(df) - 1, idx + 1)
    return int(df.iloc[lo]["frame_id"]), int(df.iloc[hi]["frame_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Chi in bang, khong ghi lai file")
    parser.add_argument("--eval-set", type=Path, default=_EVAL_SET)
    args = parser.parse_args()

    data = json.loads(args.eval_set.read_text(encoding="utf-8"))
    changes: list[tuple[str, int, int, int, int]] = []  # (label, old_s, old_e, new_s, new_e)

    for q in data:
        qid = q.get("query_id", "?")
        vid = q.get("gt_video_id")
        qtype = q.get("type")

        if qtype in ("KIS", "QA"):
            s, e = q.get("gt_frame_start"), q.get("gt_frame_end")
            if s is not None and s == e:
                ns, ne = _widen_one(vid, int(s))
                if (ns, ne) != (s, e):
                    q["gt_frame_start"], q["gt_frame_end"] = ns, ne
                    changes.append((qid, s, e, ns, ne))

        elif qtype == "TRAKE":
            for i, ev in enumerate(q.get("events", [])):
                s, e = ev.get("gt_frame_start"), ev.get("gt_frame_end")
                if s is not None and s == e:
                    ns, ne = _widen_one(vid, int(s))
                    if (ns, ne) != (s, e):
                        ev["gt_frame_start"], ev["gt_frame_end"] = ns, ne
                        changes.append((f"{qid} events[{i}]", s, e, ns, ne))

    print(f"[widen_gt] {args.eval_set.name}: {len(changes)} khoang single-frame duoc noi\n")
    print(f"  {'entry':<28} {'old [s,e]':>14}   ->  {'new [s,e]':>14}")
    for label, os_, oe, ns, ne in changes:
        print(f"  {label:<28} {f'[{os_}, {oe}]':>14}   ->  {f'[{ns}, {ne}]':>14}")

    if not changes:
        print("  (khong co gi de noi — moi entry da co khoang that)")
        return

    if args.dry_run:
        print("\n[widen_gt] --dry-run: KHONG ghi file.")
        return

    args.eval_set.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n[widen_gt] Da ghi {args.eval_set}. NHO DO TAY LAI bang mat (xem EVAL_GUIDE.md).")


if __name__ == "__main__":
    main()
