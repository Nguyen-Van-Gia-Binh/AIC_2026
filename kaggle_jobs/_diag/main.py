"""Kernel chẩn đoán tạm thời — KHÔNG phải job encode. Chỉ in cấu trúc /kaggle/input để xác
định vì sao list_videos() trong 4 job encode báo FileNotFoundError. Xoá sau khi debug xong."""

from pathlib import Path

root = Path("/kaggle/input")
print(f"[diag] /kaggle/input tồn tại: {root.exists()}")
if root.exists():
    entries = sorted(root.iterdir())
    print(f"[diag] số entry trực tiếp trong /kaggle/input: {len(entries)}")
    for e in entries:
        print(f"[diag]  - {e} (dir={e.is_dir()})")
        if e.is_dir():
            try:
                children = sorted(e.iterdir())
            except Exception as exc:
                print(f"[diag]      !! lỗi khi list: {exc}")
                continue
            print(f"[diag]    -> {len(children)} entry con, 10 đầu tiên:")
            for c in children[:10]:
                print(f"[diag]       * {c}")
            # thử đào sâu thêm nhiều cấp nếu có (đủ sâu để thấy tới keyframes/{batch}/{video_id}/*.jpg)
            def walk(p: Path, depth: int, max_depth: int = 5):
                if depth > max_depth:
                    return
                try:
                    kids = sorted(p.iterdir())
                except Exception as exc:
                    print(f"[diag]{'  ' * depth}!! lỗi list {p}: {exc}")
                    return
                print(f"[diag]{'  ' * depth}{p} -> {len(kids)} entry, đầu tiên: {kids[:5]}")
                for k in kids[:2]:
                    if k.is_dir():
                        walk(k, depth + 1, max_depth)

            for c in children[:2]:
                if c.is_dir():
                    walk(c, 1)

# tìm keyframes/ ở bất kỳ độ sâu nào dưới /kaggle/input (bất kể quy ước mount cũ hay mới)
matches = list(root.rglob("keyframes"))
print(f"[diag] tìm 'keyframes' bằng rglob: {matches}")

# test xem GPU có thực sự chạy được phép tính CUDA hay chỉ .to('cuda') không lỗi nhưng compute lỗi
try:
    import torch
    print(f"[diag] torch={torch.__version__} cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"[diag] GPU name: {torch.cuda.get_device_name(0)}")
        print(f"[diag] GPU capability: {torch.cuda.get_device_capability(0)}")
        a = torch.randn(256, 256, device="cuda")
        b = torch.randn(256, 256, device="cuda")
        c_ = a @ b
        torch.cuda.synchronize()
        print(f"[diag] CUDA matmul OK, kết quả mean={c_.mean().item():.4f}")
    else:
        print("[diag] KHÔNG có CUDA -> chạy CPU")
except Exception as exc:
    print(f"[diag] !!! CUDA matmul LỖI: {type(exc).__name__}: {exc}")

print("[diag] xong")
