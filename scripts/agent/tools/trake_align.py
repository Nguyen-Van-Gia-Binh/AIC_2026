"""
trake_align.py — Thuật toán căn chỉnh chuỗi mốc thời gian cho TRAKE (module thuần).

Tách khỏi pipeline_trake.py 2026-08-31 để phần thuật toán kiểm thử được độc lập: hai hàm dưới đây
không nạp index, không gọi LLM, không đọc ảnh — chỉ nhận list hit đã có sẵn. pipeline_trake.py giữ
phần điều phối 3 giai đoạn.

  find_best_increasing_chain()  quy hoạch động chọn chuỗi frame tăng dần có tổng score lớn nhất
  rule_plausibility()           chấm độ khớp từ khoá event vs Objects JSON của từng frame (miễn phí)
"""
from __future__ import annotations

from typing import Optional

from scripts.agent.tools.objects_lookup import get_objects


def find_best_increasing_chain(
    event_hits: list[list[dict]], strict: bool = True
) -> list[dict] | None:
    """Tim chuoi 1 frame/event sao cho frame_idx TANG DAN qua tung event va TONG score la lon nhat,
    bang quy hoach dong — thay vi greedy cu (chon diem cao nhat cho event dau tien roi khoa cung, co
    the chan mat lua chon tot hon o cac event sau, xem "Ly do thiet ke" trong plan
    docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md).

    Args:
        event_hits: event_hits[i] = list ung vien (tu fast_retrieve_for_video, da sap xep giam dan
                    theo score) cho event thu i.
        strict:     True (mac dinh, BAN DAC TA §5.2 "Strict Monotonic") = frame_idx phai TANG NGHIEM
                    NGAT (f_1 < f_2 < ... < f_N) — 2 moc khac nhau khong duoc tro ve cung 1 frame.
                    False = cho phep bang nhau (hanh vi cu tu Phase 4; giu lai vi du lieu that co
                    truong hop 2 event lien tiep roi vao cung 1 keyframe khi keyframe thua).

    Returns:
        list[dict] do dai == len(event_hits), 1 hit/event, frame_idx tang dan, tong score lon nhat
        co the; None neu KHONG TON TAI chuoi hop le nao (video nay bi loai hoan toan).
    """
    n = len(event_hits)
    if n == 0 or any(not candidates for candidates in event_hits):
        return None

    NEG_INF = float("-inf")
    # dp[i][j] = tong score lon nhat cua chuoi ket thuc bang ung vien j cua event i
    dp: list[list[float]] = [[NEG_INF] * len(candidates) for candidates in event_hits]
    back: list[list[Optional[int]]] = [[None] * len(candidates) for candidates in event_hits]

    for j, hit in enumerate(event_hits[0]):
        dp[0][j] = hit["score"]

    for i in range(1, n):
        for j, hit in enumerate(event_hits[i]):
            for k, prev_hit in enumerate(event_hits[i - 1]):
                if strict:
                    if prev_hit["frame_idx"] >= hit["frame_idx"]:
                        continue  # phai TANG NGHIEM NGAT — 2 moc khong duoc trung 1 frame
                elif prev_hit["frame_idx"] > hit["frame_idx"]:
                    continue  # che do noi long: chi cam lui ve truoc
                if dp[i - 1][k] == NEG_INF:
                    continue
                candidate_score = dp[i - 1][k] + hit["score"]
                if candidate_score > dp[i][j]:
                    dp[i][j] = candidate_score
                    back[i][j] = k

    last = n - 1
    best_j, best_score = None, NEG_INF
    for j, s in enumerate(dp[last]):
        if s > best_score:
            best_score, best_j = s, j
    if best_j is None or best_score == NEG_INF:
        return None

    chain: list[Optional[dict]] = [None] * n
    j = best_j
    for i in range(last, -1, -1):
        chain[i] = event_hits[i][j]
        j = back[i][j]
    return chain  # type: ignore[return-value]

def rule_plausibility(event_queries_en: list[str], chain: list[dict]) -> float:
    """
    Cong loc nhanh rule-based (§5.3): do khop tu khoa giua Objects JSON cua tung frame trong chuoi
    va mo ta event tuong ung. Tra ve [0.0, 1.0] = trung binh ti le tu khoa event tim thay trong
    objects cua frame do.

    Khong goi API, khong doc anh — chay duoc cho ca 20 video candidate. Frame khong co objects JSON
    duoc tinh 0 cho event do (khong doan bua), nhung khong lam ca chuoi bi loai.
    """
    from scripts.agent.tools.sparse_index import tokenize

    if not chain:
        return 0.0
    per_event: list[float] = []
    for eq, hit in zip(event_queries_en, chain):
        tokens = set(tokenize(eq))
        if not tokens:
            continue
        vid, n = hit.get("video_id", ""), hit.get("n")
        objs = get_objects(vid, int(n)) if vid and n is not None else []
        obj_tokens = set(tokenize(" ".join(objs)))
        per_event.append(len(tokens & obj_tokens) / len(tokens) if obj_tokens else 0.0)
    return sum(per_event) / len(per_event) if per_event else 0.0
