"""
scripts/check_shards_status.py — Kiểm tra trạng thái chạy của các Shard trên tài khoản Kaggle thanhnghiphan.

Usage:
  .venv\\Scripts\\python.exe scripts\\check_shards_status.py
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
KAGGLE_EXE = ROOT / ".venv" / "Scripts" / "kaggle.exe"
if not KAGGLE_EXE.exists():
    KAGGLE_EXE = Path("kaggle")

SHARDS = [
    {"shard": 0, "slug": "aic2026-caption-07-vintern1b-shard0"},
    {"shard": 1, "slug": "aic2026-caption-07-vintern1b-shard1"},
    {"shard": 2, "slug": "aic2026-caption-07-vintern1b-shard2"},
]


def main():
    load_dotenv(ENV_PATH)
    user = os.environ.get("KAGGLE_ACC0_USERNAME", "thanhnghiphan").strip()
    key = os.environ.get("KAGGLE_ACC0_KEY", "").strip()

    print("=" * 70)
    print(f"📊 KIỂM TRA TIẾN ĐỘ CÁC SHARD TRÊN KAGGLE (@{user})")
    print("=" * 70)

    env = dict(os.environ)
    if user and key:
        env["KAGGLE_USERNAME"] = user
        env["KAGGLE_KEY"] = key

    for s in SHARDS:
        kernel_id = f"{user}/{s['slug']}"
        cmd = [str(KAGGLE_EXE), "kernels", "status", kernel_id]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        status_text = res.stdout.strip() or res.stderr.strip()
        if "KernelWorkerStatus" in status_text:
            print(f"🔸 Shard {s['shard']}: {status_text}")
        elif "Cannot access" in status_text or "404" in status_text or "denied" in status_text:
            print(f"🔸 Shard {s['shard']}: Chưa được tạo / chưa push lên Kaggle")
        else:
            print(f"🔸 Shard {s['shard']}: {status_text}")

    print("=" * 70)


if __name__ == "__main__":
    main()
