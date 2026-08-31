"""
fetch_vietocr_assets.py — Đảm bảo weights và config của VietOCR có sẵn offline trong data/models/vietocr/.

Tránh lỗi kết nối mạng (hoặc SSL expired của vocr.vn) khi runtime gọi VietOCR.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_MODELS = _ROOT / "data" / "models" / "vietocr"
_DATA_EXTRACTED = _ROOT / "data" / "extracted"

_DEFAULT_CONFIG = {
    "vocab": (
        "aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆ"
        "fFgGhHiIìÌỉỈĩĨíÍịỊjJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrR"
        "sStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyYỳỲỷỶỹỸýÝỵỴzZ0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
    ),
    "device": "cpu",
    "seq_modeling": "transformer",
    "transformer": {
        "d_model": 256,
        "nhead": 8,
        "num_encoder_layers": 6,
        "num_decoder_layers": 6,
        "dim_feedforward": 2048,
        "max_seq_length": 1024,
        "pos_dropout": 0.1,
        "trans_dropout": 0.1,
    },
    "optimizer": {
        "max_lr": 0.0003,
        "pct_start": 0.1,
    },
    "trainer": {
        "batch_size": 32,
        "print_every": 200,
        "valid_every": 4000,
        "iters": 100000,
        "export": "./weights/transformerocr.pth",
        "checkpoint": "./checkpoint/transformerocr_checkpoint.pth",
        "log": "./train.log",
        "metrics": None,
    },
    "dataset": {
        "name": "data",
        "data_root": "./img/",
        "train_annotation": "annotation_train.txt",
        "valid_annotation": "annotation_val_small.txt",
        "image_height": 32,
        "image_min_width": 32,
        "image_max_width": 512,
    },
    "dataloader": {
        "num_workers": 3,
        "pin_memory": True,
    },
    "aug": {
        "image_aug": True,
        "masked_language_model": True,
    },
    "predictor": {
        "beamsearch": False,
    },
    "quiet": False,
    "backbone": "vgg19_bn",
    "cnn": {
        "pretrained": False,
        "ss": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "ks": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "hidden": 256,
    },
}


def ensure_vietocr_assets() -> Path:
    """Tạo thư mục data/models/vietocr/ và bảo đảm có weights + config.yml."""
    _DATA_MODELS.mkdir(parents=True, exist_ok=True)
    target_pth = _DATA_MODELS / "vgg_transformer.pth"
    target_yml = _DATA_MODELS / "config.yml"

    # 1. Weights
    if not target_pth.exists():
        extracted_pth = _DATA_EXTRACTED / "vgg_transformer.pth"
        if extracted_pth.exists():
            print(f"[fetch_vietocr] Sao chép weights từ {extracted_pth} -> {target_pth}")
            shutil.copy2(extracted_pth, target_pth)
        else:
            print(f"[fetch_vietocr] CẢNH BÁO: Không tìm thấy weights tại {extracted_pth} hay {target_pth}")

    # 2. Config YAML
    config_dict = dict(_DEFAULT_CONFIG)
    config_dict["weights"] = str(target_pth)
    with open(target_yml, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
    print(f"[fetch_vietocr] Đã tạo config offline: {target_yml}")

    return target_pth


if __name__ == "__main__":
    pth = ensure_vietocr_assets()
    print(f"[fetch_vietocr] Hoàn tất setup VietOCR offline. Weight: {pth}")
