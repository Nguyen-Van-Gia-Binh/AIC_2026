"""
[RETIRED 2026-08-28] scripts/index.py — Đã retire khỏi production path.

File này từng build index cho clip_vitb32 (clip-features-32/*.npy, 512 chiều).
Sau khi benchmark 33 query xác nhận siglip/siglip2 vượt clip_vitb32 ở mọi task
(Final ALL: siglip=0.549, siglip2=0.551 vs 0.290), clip-features-32 đã bị xoá
(xem docs/superpowers/plans/2026-08-28-retire-clip-promote-siglip.md).

production path hiện tại:
  - scripts/agent/tools/retrieve.py  <- dùng multi_index.py + features_siglip/*.npy (KIS/TRAKE)
  - scripts/agent/tools/retrieve.py  <- dùng multi_index.py + features_siglip2/*.npy (QA)

File này GIỮ NGUYÊN (không xoá) để:
  1. Không phá bất kỳ import nào còn sót trong codebase.
  2. Ghi lại context lịch sử quyết định retire.
  3. Phòng trường hợp cần tham chiếu lại logic build_index() trong tương lai.

KHÔNG gọi build_index() từ production code nữa.
"""

from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted"
# clip-features-32: nếu file .npy nằm trong thư mục con cùng tên (do giải nén zip tạo thêm 1 cấp)
_CF_BASE = DATA_DIR / "clip-features-32"
FEATURES_DIR = (
    _CF_BASE / "clip-features-32"
    if not any(_CF_BASE.glob("*.npy")) and (_CF_BASE / "clip-features-32").is_dir()
    else _CF_BASE
)
MAPKF_DIR = DATA_DIR / "map-keyframes"      # trỏ đến junction → map-keyframes-aic25-b1/map-keyframes
KEYFRAMES_DIR = DATA_DIR / "keyframes"



def build_index() -> tuple[np.ndarray, pd.DataFrame]:  # [RETIRED] Không được gọi từ production nữa — xem docstring module.
    """Quét toàn bộ npy + csv có sẵn, ghép thành 1 ma trận embedding + 1 bảng metadata.

    Trả về:
      matrix: (N, 512) float32, mỗi dòng đã L2-normalize -> cosine similarity = dot product
      meta:   DataFrame N dòng, cột: video_id, n, pts_time, frame_idx, jpg_path (hoặc None)
              cùng thứ tự với matrix (dòng i của meta khớp dòng i của matrix)
    """
    npy_files = sorted(FEATURES_DIR.glob("*.npy"))
    if not npy_files:
        raise FileNotFoundError(f"Không thấy file .npy nào trong {FEATURES_DIR}")

    vec_chunks = []
    meta_rows = []

    for npy_path in npy_files:
        video_id = npy_path.stem
        csv_path = MAPKF_DIR / f"{video_id}.csv"
        if not csv_path.exists():
            print(f"[WARN] thiếu map-keyframes cho {video_id}, bỏ qua")
            continue

        feats = np.load(npy_path).astype(np.float32)
        df = pd.read_csv(csv_path)

        n_rows = min(len(df), len(feats))
        if len(df) != len(feats):
            print(f"[WARN] {video_id}: số dòng csv ({len(df)}) != số vector npy ({len(feats)}), "
                  f"cắt còn {n_rows}")

        # đảm bảo norm = 1 dù dữ liệu gốc có sai lệch nhỏ do float16
        chunk = feats[:n_rows]
        norms = np.linalg.norm(chunk, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        chunk = chunk / norms
        vec_chunks.append(chunk)

        # Dữ liệu thật (10 batch L21–L30, xác nhận 2026-08-20) lồng thêm 1 cấp thư mục batch:
        # data/extracted/keyframes/{batch}/{video_id}/{n}.jpg — không phải .../{video_id}/{n}.jpg
        # như giả định ban đầu. Thử đường dẫn lồng batch trước, fallback về đường dẫn phẳng cũ
        # (phòng trường hợp máy khác/lần tải khác vẫn còn cấu trúc cũ).
        batch = video_id.split("_")[0]
        kf_dir_nested = KEYFRAMES_DIR / batch / video_id
        kf_dir_flat = KEYFRAMES_DIR / video_id
        kf_dir = kf_dir_nested if kf_dir_nested.is_dir() else kf_dir_flat
        for i in range(n_rows):
            row = df.iloc[i]
            n = int(row["n"])
            jpg_path = kf_dir / f"{n:03d}.jpg"
            meta_rows.append({
                "video_id": video_id,
                "n": n,
                "pts_time": float(row["pts_time"]),
                "frame_idx": int(row["frame_idx"]),
                "jpg_path": str(jpg_path) if jpg_path.exists() else None,
            })

    matrix = np.concatenate(vec_chunks, axis=0)
    meta = pd.DataFrame(meta_rows)
    assert len(meta) == matrix.shape[0], "meta và matrix lệch số dòng"
    return matrix, meta


if __name__ == "__main__":
    m, meta = build_index()
    n_with_jpg = meta["jpg_path"].notna().sum()
    print(f"Tổng số keyframe trong index: {len(meta)}")
    print(f"Số video: {meta['video_id'].nunique()}")
    print(f"Số keyframe đã có ảnh jpg thật (để hiển thị): {n_with_jpg}")
    print(f"Kích thước ma trận embedding: {m.shape}, dtype={m.dtype}")
