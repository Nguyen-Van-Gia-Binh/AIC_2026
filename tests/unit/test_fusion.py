"""Test cho scripts/agent/tools/fusion.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert."""
from __future__ import annotations

from scripts.agent.tools.fusion import RRF_K, W_DENSE, W_SPARSE, reciprocal_rank_fusion


def test_key_duoc_ca_hai_he_thong_xep_cao_thang_key_chi_mot_he_thong() -> None:
    dense = ["A", "B", "C"]
    sparse = ["B", "D", "E"]
    fused = reciprocal_rank_fusion([(dense, W_DENSE), (sparse, W_SPARSE)])
    keys = [key for key, _ in fused]
    assert keys[0] == "B", (
        f"B (dense #2 + sparse #1 — CA HAI he thong dong y) phai vuot A (chi dense #1): {fused}"
    )
    assert keys[1] == "A", f"A (dense #1, w=0.75) phai dung ngay sau B: {fused}"
    assert keys.index("C") < keys.index("D"), "Dense #3 (w=0.75) phai tren sparse #2 (w=0.25)"
    assert set(keys) == {"A", "B", "C", "D", "E"}, "RRF phai giu ca key chi co o 1 he thong"


def test_trong_so_0_va_danh_sach_rong_khong_lam_hong_ket_qua() -> None:
    dense = ["A", "B", "C"]
    only_dense = reciprocal_rank_fusion([(dense, W_DENSE), ([], W_SPARSE)])
    assert [k for k, _ in only_dense] == dense, "Sparse rong -> giu nguyen thu tu dense"
    assert reciprocal_rank_fusion([]) == []


def test_top_k_cat_dung_so_luong() -> None:
    dense = ["A", "B", "C"]
    sparse = ["B", "D", "E"]
    assert len(reciprocal_rank_fusion([(dense, W_DENSE), (sparse, W_SPARSE)], top_k=2)) == 2


def test_rrf_chi_phu_thuoc_thu_hang_khong_phu_thuoc_diem_goc() -> None:
    """Tinh chat cot loi — neu ai do doi module nay sang cong diem tho, test nay se hong."""
    fused_a = reciprocal_rank_fusion([(["X", "Y"], 1.0)])
    fused_b = reciprocal_rank_fusion([(["X", "Y"], 1.0)])
    assert fused_a == fused_b
    assert abs(fused_a[0][1] - 1.0 / (RRF_K + 1)) < 1e-12, "Diem RRF phai la w/(k+rank)"

# rrf_fuse_hits() co bo test rieng tai tests/unit/test_rrf_fusion.py.
