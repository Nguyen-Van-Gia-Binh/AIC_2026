"""
Công cụ tra cứu frame_id từ timestamp — hỗ trợ NGƯỜI ghi ground truth cho bộ eval Phase 6.

Không đụng gì tới scripts/agent/tools/index_store.py (pipeline sản xuất) — chỉ
đọc thẳng data/extracted/map-keyframes/{video_id}.csv, độc lập hoàn toàn. Xem PLAN.md Phase 6 và
tests/eval/EVAL_GUIDE.md để biết quy trình ghi ground truth đầy đủ.

Cách dùng:
  # 1 timestamp -> in ra keyframe gần nhất + vài keyframe lân cận để tự chọn khoảng [s, e]
  .venv\\Scripts\\python.exe tests\\Eval\\lookup_frame.py L21_V001 83.5

  # 1 khoảng thời gian [start, end] giây -> in luôn khoảng frame_id [s, e] gợi ý
  .venv\\Scripts\\python.exe tests\\Eval\\lookup_frame.py L21_V001 83.5 --end 86.0

  # đổi số keyframe lân cận in ra (mặc định 2 mỗi phía)
  .venv\\Scripts\\python.exe tests\\Eval\\lookup_frame.py L21_V001 83.5 --window 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "extracted"
_MAPKF_DIR = _DATA_DIR / "map-keyframes"
_KEYFRAMES_DIR = _DATA_DIR / "keyframes"


def _load_map(video_id: str) -> pd.DataFrame:
    csv_path = _MAPKF_DIR / f"{video_id}.csv"
    if not csv_path.exists():
        available = sorted(p.stem for p in _MAPKF_DIR.glob(f"{video_id[:3]}*.csv"))[:10]
        hint = f" Vài video_id cùng batch có sẵn: {', '.join(available)}" if available else ""
        raise SystemExit(f"[lookup_frame] Không thấy {csv_path}.{hint}")
    df = pd.read_csv(csv_path)
    df["frame_id"] = df["frame_idx"] + 1
    return df


def _jpg_hint(video_id: str, n: int) -> str:
    # Cấu trúc thật: data/extracted/keyframes/{batch}/{video_id}/{n}.jpg (xem fix cùng ngày trong
    # scripts/agent/tools/index_store.py — trước đó cả 2 chỗ đều giả định nhầm .../{video_id}/{n}.jpg, không lồng batch).
    batch = video_id.split("_")[0]
    jpg_path = _KEYFRAMES_DIR / batch / video_id / f"{n:03d}.jpg"
    return str(jpg_path) if jpg_path.exists() else "(chưa có ảnh jpg cục bộ)"


def _print_row(row: pd.Series, video_id: str, label: str = "") -> None:
    tag = f" [{label}]" if label else ""
    print(
        f"  n={int(row['n']):>4}  frame_id={int(row['frame_id']):>6}  "
        f"t={row['pts_time']:>8.2f}s{tag}  ảnh: {_jpg_hint(video_id, int(row['n']))}"
    )


def lookup_single(video_id: str, t: float, window: int) -> None:
    df = _load_map(video_id)
    idx_nearest = (df["pts_time"] - t).abs().idxmin()
    lo = max(0, idx_nearest - window)
    hi = min(len(df) - 1, idx_nearest + window)

    print(f"\nvideo_id={video_id}  timestamp mục tiêu={t:.2f}s  (tổng {len(df)} keyframe)")
    print(f"Keyframe gần nhất + {window} lân cận mỗi phía:")
    for i in range(lo, hi + 1):
        label = "GẦN NHẤT" if i == idx_nearest else ""
        _print_row(df.iloc[i], video_id, label)

    prev_id = int(df.iloc[max(0, idx_nearest - 1)]["frame_id"])
    next_id = int(df.iloc[min(len(df) - 1, idx_nearest + 1)]["frame_id"])
    nearest_id = int(df.iloc[idx_nearest]["frame_id"])
    print(
        f"\nGợi ý nhanh (rộng, nên tự xem ảnh/video để thu hẹp lại):\n"
        f"  gt_frame_start={prev_id}  gt_frame_end={next_id}  "
        f"(hoặc dùng đúng gt_frame_start=gt_frame_end={nearest_id} nếu khoảnh khắc rất ngắn)"
    )


def lookup_range(video_id: str, t_start: float, t_end: float) -> None:
    if t_end < t_start:
        t_start, t_end = t_end, t_start
    df = _load_map(video_id)
    mask = (df["pts_time"] >= t_start) & (df["pts_time"] <= t_end)
    sub = df[mask]

    print(f"\nvideo_id={video_id}  khoảng mục tiêu=[{t_start:.2f}s, {t_end:.2f}s]")
    if sub.empty:
        print("  Không có keyframe nào rơi đúng trong khoảng này — dùng chế độ 1 timestamp "
              "(bỏ --end) để tìm keyframe gần nhất thay thế.")
        return

    print(f"  {len(sub)} keyframe rơi trong khoảng:")
    for _, row in sub.iterrows():
        _print_row(row, video_id)

    s = int(sub.iloc[0]["frame_id"])
    e = int(sub.iloc[-1]["frame_id"])
    print(f"\nGợi ý: gt_frame_start={s}  gt_frame_end={e}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video_id", help="Ví dụ: L21_V001 (không có .mp4)")
    parser.add_argument("start", type=float, help="Timestamp giây (hoặc mốc đầu nếu dùng --end)")
    parser.add_argument("--end", type=float, default=None, help="Mốc cuối (giây) nếu muốn tra cả khoảng")
    parser.add_argument("--window", type=int, default=2, help="Số keyframe lân cận mỗi phía (mặc định 2)")
    args = parser.parse_args()

    if args.end is not None:
        lookup_range(args.video_id, args.start, args.end)
    else:
        lookup_single(args.video_id, args.start, args.window)


if __name__ == "__main__":
    main()
