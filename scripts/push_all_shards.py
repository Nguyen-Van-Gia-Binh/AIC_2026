"""
scripts/push_all_shards.py — Đẩy đồng loạt 3 Shard lên 3 tài khoản Kaggle từ cấu hình trong .env.

Usage:
  .venv\\Scripts\\python.exe scripts\\push_all_shards.py
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Thiết lập UTF-8 cho console Windows
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

SHARD_CONFIGS = [
    {
        "shard_idx": 0,
        "folder": ROOT / "kaggle_jobs" / "07_vintern_caption_shard0",
        "default_user": "thanhnghiphan",
        "env_user_key": "KAGGLE_ACC0_USERNAME",
        "env_pass_key": "KAGGLE_ACC0_KEY",
        "slug": "aic2026-caption-07-vintern1b-shard0",
    },
    {
        "shard_idx": 1,
        "folder": ROOT / "kaggle_jobs" / "07_vintern_caption_shard1",
        "default_user": "coduckzz",
        "env_user_key": "KAGGLE_ACC1_USERNAME",
        "env_pass_key": "KAGGLE_ACC1_KEY",
        "slug": "aic2026-caption-07-vintern1b-shard1",
    },
    {
        "shard_idx": 2,
        "folder": ROOT / "kaggle_jobs" / "07_vintern_caption_shard2",
        "default_user": "sonasuzz",
        "env_user_key": "KAGGLE_ACC2_USERNAME",
        "env_pass_key": "KAGGLE_ACC2_KEY",
        "slug": "aic2026-caption-07-vintern1b-shard2",
    },
]


def main():
    if not ENV_PATH.exists():
        print(f"❌ Không tìm thấy file .env tại: {ENV_PATH}")
        print("Vui lòng tạo file .env từ .env.example và điền API key của 3 tài khoản Kaggle.")
        sys.exit(1)

    load_dotenv(ENV_PATH)

    print("=" * 75)
    print("🚀 BẮT ĐẦU ĐẨY ĐỒNG LOẠT 3 SHARD LÊN 3 TÀI KHOẢN KAGGLE")
    print("=" * 75)

    for cfg in SHARD_CONFIGS:
        s_idx = cfg["shard_idx"]
        user = os.environ.get(cfg["env_user_key"], cfg["default_user"]).strip()
        key = os.environ.get(cfg["env_pass_key"], "").strip()

        print(f"\n🔹 [SHARD {s_idx}] Đang chuẩn bị đẩy lên tài khoản: @{user} ...")

        if not key:
            print(f"⚠️ CẢNH BÁO: Chưa tìm thấy {cfg['env_pass_key']} trong .env!")
            print(f"   Bỏ qua Shard {s_idx}. Hãy điền key vào .env và chạy lại.")
            continue

        env = dict(os.environ)
        env["KAGGLE_USERNAME"] = user
        env["KAGGLE_KEY"] = key

        cmd = [str(KAGGLE_EXE), "kernels", "push", "-p", str(cfg["folder"])]
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
            print(f"✅ [SHARD {s_idx}] Đẩy thành công!")
            print(f"   Log: {res.stdout.strip()}")
            print(f"   🔗 Link theo dõi: https://www.kaggle.com/code/{user}/{cfg['slug']}")
        except subprocess.CalledProcessError as e:
            print(f"❌ [SHARD {s_idx}] Đẩy thất bại!")
            print(f"   Lỗi: {e.stderr.strip() or e.stdout.strip()}")

    print("\n" + "=" * 75)
    print("💡 Để kiểm tra trạng thái các job, chạy: .venv\\Scripts\\python.exe scripts\\check_shards_status.py")
    print("💡 Để tải kết quả khi hoàn thành, chạy: .venv\\Scripts\\python.exe scripts\\download_all_shards.py")
    print("=" * 75)


if __name__ == "__main__":
    main()
