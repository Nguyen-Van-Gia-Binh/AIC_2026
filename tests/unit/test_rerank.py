"""Test cho scripts/agent/tools/rerank.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert.

Khối cũ monkeypatch trực tiếp biến global của module retrieve; ở đây dùng fixture `monkeypatch`
của pytest để việc khôi phục không phụ thuộc vào try/finally viết tay.
"""
from __future__ import annotations

from collections import Counter

from scripts.agent.tools.rerank import (
    BET_VIDEO_SHARE, SPREAD_MAX_PER_VIDEO, apply_risk_aware_ranking,
)


def _fake_hit(video_id: str, i: int, score: float) -> dict:
    return {"video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
            "pts_time": 0.0, "score": score, "jpg_path": None}


def _hit_t(video_id: str, i: int, score: float, pts: float, rrf: float | None = None) -> dict:
    h = {"video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
         "pts_time": pts, "score": score, "jpg_path": None}
    if rrf is not None:
        h["rrf_score"] = rrf
    return h


def test_bet_mode_uu_tien_video_noi_bat() -> None:
    hits = ([_fake_hit("A", i, 0.9 - i * 0.001) for i in range(5)]
            + [_fake_hit(f"V{i}", i, 0.5 - i * 0.001) for i in range(20)])
    out = apply_risk_aware_ranking(hits, top_k=10)
    n_a = sum(1 for h in out if h["video_id"] == "A")
    assert n_a >= 5, f"Bet mode phai uu tien video A, chi thay {n_a}/10"


def test_spread_mode_hanh_vi_cu_ap_tran_cho_ca_danh_sach() -> None:
    hits = [_fake_hit(f"V{i // 5}", i, 0.5 - i * 0.0001) for i in range(100)]
    out = apply_risk_aware_ranking(hits, top_k=30, preserve_recall_tail=False)
    counts = Counter(h["video_id"] for h in out)
    assert max(counts.values()) <= SPREAD_MAX_PER_VIDEO, (
        f"Spread mode (hanh vi cu) vuot qua {SPREAD_MAX_PER_VIDEO} dong/video: {counts}"
    )


def test_spread_mode_moi_giu_tran_o_phan_dau_va_khong_mat_ung_vien() -> None:
    hits = [_fake_hit(f"V{i // 5}", i, 0.5 - i * 0.0001) for i in range(100)]
    out = apply_risk_aware_ranking(hits, top_k=30, head_n=10)
    counts_head = Counter(h["video_id"] for h in out[:10])
    assert max(counts_head.values()) <= SPREAD_MAX_PER_VIDEO, (
        f"Phan dau van phai giu tran {SPREAD_MAX_PER_VIDEO} dong/video: {counts_head}"
    )
    key = lambda L: {(h["video_id"], h["frame_idx"]) for h in L}   # noqa: E731
    mat = key(hits[:30]) - key(out)
    assert not mat, f"Mat {len(mat)} ung vien retrieval du con cho trong: {sorted(mat)[:5]}"


def test_hits_rong_khong_crash() -> None:
    assert apply_risk_aware_ranking([], top_k=10) == []


def test_bet_mode_khong_loai_nham_ung_vien_trung_frame_idx_voi_video_khac(monkeypatch) -> None:
    """frame_idx la index CUC BO tung video (khong globally unique) — dedup sai o ban truoc kiem tra
    ca pool nhieu video thay vi chi rieng hit cua video dat cuoc."""
    import scripts.agent.tools.retrieve as retrieve_module

    monkeypatch.setattr(retrieve_module, "fast_retrieve_for_video",
                        lambda query_text, video_id, top_k: [_fake_hit("A", 99, 0.85)])
    hits = ([_fake_hit("A", i, 0.9 - i * 0.001) for i in range(3)]
            + [_fake_hit("V0", 99, 0.5)]
            + [_fake_hit(f"V{i}", i, 0.4 - i * 0.001) for i in range(1, 20)])
    out = apply_risk_aware_ranking(hits, top_k=10, query_text="fake query")
    frame_idxs_a = {h["frame_idx"] for h in out if h["video_id"] == "A"}
    assert 99 in frame_idxs_a, (
        f"Ung vien dao sau (frame_idx=99) cua video A bi loai nham do trung voi video khac: {frame_idxs_a}"
    )


def test_spread_mode_cong_temporal_nms() -> None:
    hits = [_hit_t("A", i, 0.5 - i * 0.0001, pts=10.0 + i * 0.5) for i in range(5)]
    hits += [_hit_t(f"V{i}", i, 0.4995 - i * 0.0001, pts=float(i * 30)) for i in range(1, 20)]

    # Hanh vi CU: NMS gom 5 keyframe sat nhau cua A ve dung 1 dinh, 4 frame kia bi VUT HAN.
    out_cu = apply_risk_aware_ranking(hits, top_k=30, apply_nms=True, preserve_recall_tail=False)
    n_a_cu = sum(1 for h in out_cu if h["video_id"] == "A")
    assert n_a_cu == 1, f"NMS (hanh vi cu) phai gom 5 keyframe sat nhau cua A ve 1 dinh, con {n_a_cu}"

    # Hanh vi MOI: con cho trong -> giu lai frame bi NMS nen, nhung xep SAU moi video khac.
    out = apply_risk_aware_ranking(hits, top_k=30, apply_nms=True)
    vids = [h["video_id"] for h in out]
    vi_tri_a = [i for i, v in enumerate(vids) if v == "A"]
    assert vi_tri_a and vi_tri_a[0] < SPREAD_MAX_PER_VIDEO, (
        f"Dinh cua A phai nam gan dau danh sach, dang o {vi_tri_a[:1]}"
    )
    if len(vi_tri_a) > 1:
        vi_tri_khac_cuoi = max(i for i, v in enumerate(vids) if v != "A")
        assert vi_tri_a[1] > vi_tri_khac_cuoi, (
            "Frame A bi NMS nen phai xep SAU moi ung vien cua video khac, "
            f"dang o {vi_tri_a[1]} trong khi ung vien khac cuoi cung o {vi_tri_khac_cuoi}"
        )

    out_no_nms = apply_risk_aware_ranking(hits, top_k=30, apply_nms=False, preserve_recall_tail=False)
    assert sum(1 for h in out_no_nms if h["video_id"] == "A") == SPREAD_MAX_PER_VIDEO, (
        "Tat NMS + hanh vi cu phai giu SPREAD_MAX_PER_VIDEO dong dau moi video"
    )
    out_no_nms_moi = apply_risk_aware_ranking(hits, top_k=30, apply_nms=False)
    assert len(out_no_nms_moi) == len(hits), (
        f"Con cho trong ma van bo sot: giao {len(out_no_nms_moi)} dong / {len(hits)} ung vien"
    )


def test_bet_mode_cong_tran_bet_video_share() -> None:
    hits = [_hit_t("A", i, 0.9 - i * 0.0001, pts=float(i * 10)) for i in range(40)]
    hits += [_hit_t(f"V{i}", i, 0.5 - i * 0.0001, pts=float(i * 10)) for i in range(30)]
    out = apply_risk_aware_ranking(hits, top_k=20, apply_nms=True)
    n_a = sum(1 for h in out if h["video_id"] == "A")
    assert n_a == int(20 * BET_VIDEO_SHARE), (
        f"Video dat cuoc phai bi cap o {int(20 * BET_VIDEO_SHARE)} dong, duoc {n_a}"
    )
    assert len(out) == 20, f"Phai tra du top_k=20 dong, duoc {len(out)}"


def test_xep_hang_theo_rrf_score() -> None:
    """Video B cosine thap hon nhung RRF cao hon (ca BM25 dong y) phai dung tren A."""
    hits = [_hit_t("A", 0, score=0.90, pts=0.0, rrf=0.0100),
            _hit_t("B", 0, score=0.10, pts=0.0, rrf=0.0160)]
    out_rrf = apply_risk_aware_ranking(hits, top_k=2, score_key="rrf_score")
    assert out_rrf[0]["video_id"] == "B", f"Phai xep theo rrf_score, duoc {out_rrf}"

    out_margin_rrf = apply_risk_aware_ranking(
        hits, top_k=2, score_key="rrf_score", margin_key="rrf_score")
    assert [h["video_id"] for h in out_margin_rrf] == ["B", "A"], "margin_key doi duoc khi can"

    out_cos = apply_risk_aware_ranking(hits, top_k=2)
    assert out_cos[0]["video_id"] == "A", (
        "score_key mac dinh phai van la cosine (khong doi hanh vi cu)"
    )
