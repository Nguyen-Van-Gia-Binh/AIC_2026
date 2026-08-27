"""
scripts/build_caption_manifest.py — Lọc keyframe theo Semantic Similarity & Chia đều 3 Shard cho 3 tài khoản Kaggle.

Thuật toán lọc:
  1. Luôn giữ frame đầu tiên (n=1, index 0).
  2. Duyệt qua từng frame i:
     - sim = dot_product(emb[i], emb[last_kept])
     - gap = pts_time[i] - pts_time[last_kept]
     - Nếu sim < TAU (0.72) hoặc gap >= MAX_GAP_SEC (25.0s) -> Giữ frame i, cập nhật last_kept = i.

Phân bổ Shard:
  - Chia 873 video thành 3 shard (0, 1, 2) theo thuật toán Greedy Bin-Packing để tổng số frame và
    thời gian GPU ước tính giữa 3 tài khoản đạt mức cân bằng tối đa (~10h GPU/tài khoản).

Usage:
  .venv\\Scripts\\python.exe scripts\\build_caption_manifest.py
"""

from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

# Thiết lập UTF-8 cho terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Tự động tìm đường dẫn features_siglip2 và map-keyframes
CANDIDATE_FEAT_DIRS = [
    DATA_DIR / "features_siglip2 (1)" / "features_siglip2",
    DATA_DIR / "extracted" / "features_siglip2" / "features_siglip2",
    DATA_DIR / "features_siglip2",
]

CANDIDATE_MAP_DIRS = [
    DATA_DIR / "map-keyframes-aic25-b1" / "map-keyframes",
    DATA_DIR / "extracted" / "map-keyframes",
    DATA_DIR / "map-keyframes",
]

TAU = 0.72
MAX_GAP_SEC = 25.0
SEC_PER_FRAME = 2.64  # Đo thực tế Vintern-1B trên Tesla T4
NUM_SHARDS = 3


def find_dir(candidates: list[Path], name: str) -> Path:
    for c in candidates:
        if c.is_dir() and any(c.glob("*.npy" if "feat" in name else "*.csv")):
            return c
    for p in DATA_DIR.rglob("*.npy" if "feat" in name else "*.csv"):
        return p.parent
    raise FileNotFoundError(f"Không tìm thấy thư mục {name} dưới {DATA_DIR}")


def main():
    feat_dir = find_dir(CANDIDATE_FEAT_DIRS, "features_siglip2")
    map_dir = find_dir(CANDIDATE_MAP_DIRS, "map-keyframes")

    print(f"[Manifest] Dùng Features: {feat_dir}")
    print(f"[Manifest] Dùng Map-keyframes: {map_dir}")

    feat_files = sorted(feat_dir.glob("*.npy"))
    print(f"[Manifest] Tìm thấy {len(feat_files)} video .npy")

    video_stats = []
    video_selections = {}

    for npy_path in feat_files:
        vid_id = npy_path.stem
        csv_path = map_dir / f"{vid_id}.csv"
        if not csv_path.exists():
            print(f"[WARN] Thiếu map-keyframes cho {vid_id}, bỏ qua.")
            continue

        emb = np.load(npy_path).astype(np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        emb = emb / norms

        df = pd.read_csv(csv_path)
        if len(df) != len(emb):
            n_min = min(len(df), len(emb))
            df = df.iloc[:n_min]
            emb = emb[:n_min]

        pts_time = df["pts_time"].to_numpy()
        n_col = df["n"].to_numpy()

        kept_indices = [0]
        last_kept = 0
        for i in range(1, len(emb)):
            sim = float(np.dot(emb[i], emb[last_kept]))
            gap = float(pts_time[i] - pts_time[last_kept])
            if sim < TAU or gap >= MAX_GAP_SEC:
                kept_indices.append(i)
                last_kept = i

        selected_n = [int(n_col[idx]) for idx in kept_indices]
        selected_pts = [float(pts_time[idx]) for idx in kept_indices]

        video_selections[vid_id] = {
            "n": selected_n,
            "pts_time": selected_pts,
            "total_raw": len(emb),
            "total_kept": len(selected_n),
        }

        video_stats.append({
            "video_id": vid_id,
            "total_raw": len(emb),
            "total_kept": len(selected_n),
        })

    sorted_vids = sorted(video_stats, key=lambda x: x["total_kept"], reverse=True)

    shard_frames = [0] * NUM_SHARDS
    shard_videos = [[] for _ in range(NUM_SHARDS)]

    for item in sorted_vids:
        min_shard = int(np.argmin(shard_frames))
        shard_videos[min_shard].append(item["video_id"])
        shard_frames[min_shard] += item["total_kept"]

    total_raw = sum(x["total_raw"] for x in video_stats)
    total_kept = sum(shard_frames)

    print("\n" + "=" * 70)
    print(f"📊 TỔNG KẾT PHÂN CHIA MANIFEST ({len(video_stats)} VIDEO):")
    print(f"   - Tổng frame gốc: {total_raw:,} frames")
    print(f"   - Tổng frame sau lọc (tau={TAU}, gap={MAX_GAP_SEC}s): {total_kept:,} frames ({total_kept/total_raw*100:.1f}%)")
    print(f"   - Tổng giờ GPU T4 (2.64s/frame): {total_kept * SEC_PER_FRAME / 3600:.2f} giờ")
    print("=" * 70)

    out_dir = DATA_DIR / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for s_idx in range(NUM_SHARDS):
        vids = sorted(shard_videos[s_idx])
        s_frames = shard_frames[s_idx]
        est_hours = s_frames * SEC_PER_FRAME / 3600
        print(f"🔸 SHARD {s_idx}: {len(vids)} video | {s_frames:,} frames | ⏱️ ~{est_hours:.2f} giờ GPU")

        shard_data = {}
        for vid in vids:
            sel = video_selections[vid]
            shard_data[vid] = sel["n"]
            for n_val, pts_val in zip(sel["n"], sel["pts_time"]):
                all_rows.append({
                    "video_id": vid,
                    "n": n_val,
                    "pts_time": pts_val,
                    "shard": s_idx
                })

        shard_json_path = out_dir / f"manifest_shard_{s_idx}.json"
        with open(shard_json_path, "w", encoding="utf-8") as f:
            json.dump(shard_data, f, indent=2)

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(out_dir / "manifest_all_selected_frames.csv", index=False)

    for s_idx in range(NUM_SHARDS):
        vids_file = out_dir / f"video_list_shard_{s_idx}.txt"
        with open(vids_file, "w", encoding="utf-8") as f:
            for v in sorted(shard_videos[s_idx]):
                f.write(f"{v}\n")

    print("=" * 70)
    print(f"✅ Đã xuất các file manifest vào thư mục: {out_dir}")


if __name__ == "__main__":
    main()
