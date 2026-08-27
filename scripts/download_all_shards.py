"""
scripts/download_all_shards.py — Tải kết quả các Shard từ tài khoản thanhnghiphan về local.

Usage:
  .venv\\Scripts\\python.exe scripts\\download_all_shards.py
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data" / "extracted"
KAGGLE_EXE = ROOT / ".venv" / "Scripts" / "kaggle.exe"
if not KAGGLE_EXE.exists():
    KAGGLE_EXE = Path("kaggle")

SHARDS = [
    {"shard": 0, "slug": "aic2026-caption-07-vintern1b-shard0", "out": "caption_shard0"},
    {"shard": 1, "slug": "aic2026-caption-07-vintern1b-shard1", "out": "caption_shard1"},
    {"shard": 2, "slug": "aic2026-caption-07-vintern1b-shard2", "out": "caption_shard2"},
]


def main():
    load_dotenv(ENV_PATH)
    user = os.environ.get("KAGGLE_ACC0_USERNAME", "thanhnghiphan").strip()
    key = os.environ.get("KAGGLE_ACC0_KEY", "").strip()

    print("=" * 70)
    print(f"📥 TẢI KẾT QUẢ CÁC SHARD TỪ TÀI KHOẢN @{user} VỀ LOCAL")
    print("=" * 70)

    env = dict(os.environ)
    if user and key:
        env["KAGGLE_USERNAME"] = user
        env["KAGGLE_KEY"] = key

    for s in SHARDS:
        kernel_id = f"{user}/{s['slug']}"
        out_dir = DATA_DIR / s["out"]
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"🔹 Đang kiểm tra & tải Shard {s['shard']} ({kernel_id}) về {out_dir} ...")
        cmd = [str(KAGGLE_EXE), "kernels", "output", kernel_id, "-p", str(out_dir)]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ Tải thành công Shard {s['shard']}!")
        else:
            print(f"⚠️ Shard {s['shard']} chưa có output hoặc chưa xong: {res.stderr.strip() or res.stdout.strip()}")

    print("=" * 70)
    print("💡 Sau khi tải đủ các shard, chạy: .venv\\Scripts\\python.exe scripts\\merge_captions.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
