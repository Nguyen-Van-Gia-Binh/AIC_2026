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
    """Tìm chuỗi 1 frame/event sao cho frame_idx TĂNG DẦN qua từng event và TỔNG score là lớn nhất,
    bằng quy hoạch động — thay vì greedy cũ (chọn điểm cao nhất cho event đầu tiên rồi khoá cứng, có
    thể chặn mất lựa chọn tốt hơn ở các event sau, xem "Lý do thiết kế" trong plan
    docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md).

    Args:
        event_hits: event_hits[i] = list ứng viên (từ fast_retrieve_for_video, đã sắp xếp giảm dần
                    theo score) cho event thứ i.
        strict:     True (mặc định, BẢN ĐẶC TẢ §5.2 "Strict Monotonic") = frame_idx phải TĂNG NGHIÊM
                    NGẶT (f_1 < f_2 < ... < f_N) — 2 mốc khác nhau không được trỏ về cùng 1 frame.
                    False = cho phép bằng nhau (hành vi cũ từ Phase 4; giữ lại vì dữ liệu thật có
                    trường hợp 2 event liên tiếp rơi vào cùng 1 keyframe khi keyframe thưa).

    Returns:
        list[dict] do dai == len(event_hits), 1 hit/event, frame_idx tang dan, tong score lon nhat
        có thể; None nếu KHÔNG TỒN TẠI chuỗi hợp lệ nào (video này bị loại hoàn toàn).
    """
    n = len(event_hits)
    if n == 0 or any(not candidates for candidates in event_hits):
        return None

    NEG_INF = float("-inf")
    # dp[i][j] = tổng score lớn nhất của chuỗi kết thúc bằng ứng viên j của event i
    dp: list[list[float]] = [[NEG_INF] * len(candidates) for candidates in event_hits]
    back: list[list[Optional[int]]] = [[None] * len(candidates) for candidates in event_hits]

    for j, hit in enumerate(event_hits[0]):
        dp[0][j] = hit["score"]

    for i in range(1, n):
        for j, hit in enumerate(event_hits[i]):
            for k, prev_hit in enumerate(event_hits[i - 1]):
                if strict:
                    if prev_hit["frame_idx"] >= hit["frame_idx"]:
                        continue  # phải TĂNG NGHIÊM NGẶT — 2 mốc không được trùng 1 frame
                elif prev_hit["frame_idx"] > hit["frame_idx"]:
                    continue  # chế độ nới lỏng: chỉ cấm lùi về trước
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
    Cổng lọc nhanh rule-based (§5.3): độ khớp từ khoá giữa Objects JSON của từng frame trong chuỗi
    và mô tả event tương ứng. Trả về [0.0, 1.0] = trung bình tỉ lệ từ khoá event tìm thấy trong
    objects của frame đó.

    Không gọi API, không đọc ảnh — chạy được cho cả 20 video candidate. Frame không có objects JSON
    được tính 0 cho event đó (không đoán bừa), nhưng không làm cả chuỗi bị loại.
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
