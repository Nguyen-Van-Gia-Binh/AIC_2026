"""
rerank.py — Risk-aware re-ranking hậu xử lý cho KIS/QA, chạy sau khi fast_retrieve trả về top-K.

Ý tưởng (PLAN.md Phase 3): quan sát "margin" giữa video ứng viên mạnh nhất và video ứng viên mạnh
nhì trong danh sách hits (so sánh best score mỗi video).
  - Margin lớn (1 video nổi bật hẳn so với phần còn lại) -> chế độ "đặt cược": dành nhiều dòng kết
    quả hơn cho đúng video đó (đào sâu hơn trong video đó bằng fast_retrieve_for_video nếu cần), tăng
    cơ hội trúng R@1/R@5.
  - Margin nhỏ (không video nào nổi bật rõ) -> chế độ "trải rủi ro": giới hạn số dòng tối đa trên 1
    video trong danh sách, ép kết quả trải rộng hơn nhiều video, tăng cơ hội trúng R@50/R@100.

Không gọi LLM (PLAN.md Phase 3: "không cần LLM"). Chỉ phụ thuộc fast_retrieve_for_video khi cần đào
sâu thêm trong video đang "đặt cược" — không tự đọc/ghi index, không đợi retrieve.py.

MARGIN_THRESHOLD / BET_VIDEO_SHARE / SPREAD_MAX_PER_VIDEO là giá trị khởi điểm, đã căn chỉnh sơ bộ
bằng dữ liệu thật (xem docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md) —
sẽ tinh chỉnh tiếp bằng benchmark thật (tests/e2e/test_phase3_rerank.py),
không phải đoán mò hình.

Usage:
    from scripts.agent.tools.rerank import apply_risk_aware_ranking
    ranked = apply_risk_aware_ranking(hits, top_k=100, query_text="a red car parked on the street")
"""
from __future__ import annotations

import os
from scripts.agent.tools.temporal_nms import temporal_nms, MIN_TIME_GAP

# Ngưỡng chênh lệch score để coi video #1 là "nổi bật rõ ràng" so với video #2.
# ⚠️ Căn chỉnh trên thang cosine của clip_vitb32 (~0.28-0.31) — model ĐÃ RETIRE 2026-08-28. Cosine
# SigLIP hẹp hơn 2-3 lần (~0.05-0.15) nên giá trị này chưa được hiệu chỉnh lại đúng thang đo hiện
# hành: đo thật 2026-08-31 cho thấy margin điển hình 0.0039-0.0528. Xem PLAN.md mục P2.7.
MARGIN_THRESHOLD = 0.012

# Ngưỡng margin TƯƠNG ĐỐI (tỉ lệ) dùng khi xếp hạng theo điểm RRF thay vì cosine (hybrid retrieval —
# xem hybrid.hybrid_retrieve). Điểm RRF có thang đo rất khác (w/(k+rank), ~0.012 ở hạng 1 và giảm
# rất chậm), nên một ngưỡng TUYỆT ĐỐI như MARGIN_THRESHOLD sẽ không bao giờ đạt -> luôn rơi vào chế độ
# trải rủi ro. Dùng tỉ lệ so với điểm cao nhất để giữ đúng ý nghĩa "video #1 nổi bật hơn hẳn #2".
MARGIN_RATIO_RRF = 0.05

# Chế độ "đặt cược": tỉ lệ tối đa số dòng (trên top_k) dành cho video nổi bật nhất.
BET_VIDEO_SHARE = 0.5

# Chế độ "trải rủi ro": số dòng tối đa cho 1 video khi không có video nào nổi bật.
SPREAD_MAX_PER_VIDEO = 3

# Số ứng viên thô cần lấy từ fast_retrieve TRƯỚC KHI rerank/cắt về top_k submission. Lớn hơn hẳn so với
# top_k thực tế (thường 100) vì chẩn đoán thực tế trên eval_ground_truth.json cho thấy GT frame chỉ nằm
# trong top-100 ở 12/23 câu nhưng nằm trong top-500 ở 20/23 câu (xem
# docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md) — trong khi chi phí tính gần như miễn
# phí (fast_retrieve đã nhận full ma trận 177K keyframe, chỉ argsort cắt nhiều hơn).
RETRIEVAL_POOL_SIZE = 500

# Số dòng ĐẦU danh sách do rerank toàn quyền quyết định. Từ dòng (RECALL_HEAD_N + 1) trở đi, danh
# sách được lặp lại theo ĐÚNG THỨ TỰ RETRIEVAL GỐC (xem _preserve_recall_tail).
#
# Vì sao: đo thật trên 18 câu KIS của eval_ground_truth.json cho thấy hậu xử lý KHÔNG hơn retrieval
# thuần ở bất kỳ mốc nào, và THUA rõ từ hạng 20 trở đi:
#     retrieval thuan (run_eval.py) : R@1 0.389  R@5 0.611  R@20 0.833  R@50 0.889  R@100 1.000
#     pipeline that (score_pipelines): R@1 0.389  R@5 0.611  R@20 0.722  R@50 0.778  R@100 0.833
# Nguyên nhân: _bet_mode bỏ qua (`continue`) mọi hit của video đặt cược vượt trần BET_VIDEO_SHARE, và
# _spread_mode chỉ lấy SPREAD_MAX_PER_VIDEO hit/video rồi `break` — cả hai đều VỨT HẲN ứng viên mà
# retrieval đã tìm ra, thay bằng dòng khác.
#
# Lập luận (không phụ thuộc cỡ mẫu eval nhỏ): Final Score chỉ tính CÚ TRÚNG ĐẦU TIÊN
# (R@k = max trong k dòng đầu), và dòng 21-100 chỉ đáng 0.4/0.2 điểm. Nên XOÁ một ứng viên retrieval
# để nhường chỗ cho dòng khác ở phần dưới không bao giờ có lợi — cùng lắm là hoà. Đẩy dòng đó xuống
# cuối thì vừa giữ được cái lợi của rerank ở đầu, vừa không mất gì ở dưới. Đó là một lựa chọn thiết
# kế BỊ TRỘI HOÀN TOÀN (strictly dominated), không phải chuyện tinh chỉnh tham số.
RECALL_HEAD_N = 20


def apply_risk_aware_ranking(
    hits: list[dict],
    top_k: int = 100,
    query_text: str | None = None,
    *,
    score_key: str = "score",
    margin_key: str = "score",
    apply_nms: bool = False,
    nms_min_gap: float = MIN_TIME_GAP,
    preserve_recall_tail: bool | None = None,
    head_n: int | None = None,
) -> list[dict]:
    """Sắp xếp lại hits theo chiến lược "đặt cược" hoặc "trải rủi ro" tuỳ margin giữa các video.

    Args:
        hits: Kết quả đã có từ fast_retrieve/hybrid_retrieve, đã sắp xếp giảm dần theo score_key.
        top_k: Số dòng tối đa trả về (giới hạn submission — xem build_submission.py).
        query_text: Query đã rewrite (tiếng Anh) dùng để đào sâu thêm trong video "đặt cược" khi cần.
                    None = chỉ sắp xếp lại hits sẵn có, không gọi thêm fast_retrieve_for_video.
        score_key: Trường dùng để XẾP HẠNG. "score" (mặc định) = cosine similarity như trước giờ;
                   "rrf_score" khi hits đến từ hybrid.hybrid_retrieve (Dense+BM25 đã dung hợp).
        margin_key: Trường dùng để QUYẾT ĐỊNH đặt cược/trải rủi ro — mặc định "score" (cosine) DÙ
                   cho xếp hạng bằng rrf_score. Lý do: MARGIN_THRESHOLD được căn chỉnh bằng benchmark
                   thật trên thang cosine; đo margin trên thang RRF (w/(k+rank), khoảng cách giữa các
                   hạng rất nhỏ và đều) làm chế độ đặt cược bật sai nhiều hơn hẳn — đo thật trên 18
                   cau KIS: Final 0.656 (margin cosine) vs 0.633 (margin RRF).
        apply_nms: Bật Temporal NMS (BẢN ĐẶC TẢ §3.2) — loại keyframe lân cận trong cùng video để
                   không lãng phí dòng nộp bài cho cùng 1 cảnh. Mặc định TẮT để đường gọi cũ
                   (pipeline_qa) giữ nguyên hành vi đã benchmark; pipeline_kis bật tường minh.
        nms_min_gap: Khoảng cách thời gian tối thiểu (giây) giữa 2 keyframe được giữ trong 1 video.
        preserve_recall_tail: Giữ phần dưới danh sách theo đúng thứ tự retrieval gốc, để hậu xử lý
                    không vứt mất ứng viên mà retrieval đã tìm ra (xem ghi chú ở RECALL_HEAD_N).
                    Mặc định BẬT. Đặt False để tái hiện hành vi cũ khi cần đo trước-sau.
        head_n: Số dòng đầu do rerank toàn quyền quyết định khi preserve_recall_tail=True.

    Returns:
        list[dict] cùng định dạng với hits đầu vào, độ dài <= top_k.
    """
    if not hits:
        return hits

    # None = đọc từ env (tiền lệ AIC_RETRIEVE_MODEL/AIC_MODE: env var, mặc định giữ hành vi tốt nhất
    # đã đo, đổi được tường minh khi cần benchmark trước-sau mà không phải sửa code).
    if preserve_recall_tail is None:
        preserve_recall_tail = os.getenv("AIC_RERANK_TAIL", "1").strip() not in ("0", "false", "False")
    if head_n is None:
        head_n = int(os.getenv("AIC_RERANK_HEAD_N", str(RECALL_HEAD_N)))

    def _margin_val(h: dict) -> float:
        return float(h.get(margin_key, h.get("score", 0.0)))

    best_score_by_video: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        if vid not in best_score_by_video or _margin_val(h) > best_score_by_video[vid]:
            best_score_by_video[vid] = _margin_val(h)

    ranked_videos = sorted(best_score_by_video.items(), key=lambda kv: -kv[1])

    if len(ranked_videos) == 1:
        margin = float("inf")
    else:
        margin = ranked_videos[0][1] - ranked_videos[1][1]

    # Ngưỡng: tuyệt đối trên thang cosine (đã căn chỉnh bằng benchmark thật), tương đối nếu ai đó
    # cố tình đo margin trên thang RRF (không phải mặc định — xem docstring margin_key).
    if margin_key == "score":
        threshold = MARGIN_THRESHOLD
    else:
        threshold = MARGIN_RATIO_RRF * abs(ranked_videos[0][1])

    if margin >= threshold:
        print(f"[rerank] margin={margin:.4f} >= {threshold:.4f} ({margin_key}) -> che do DAT CUOC "
              f"(video={ranked_videos[0][0]})")
        ranked = _bet_mode(hits, ranked_videos[0][0], top_k, query_text, score_key, apply_nms, nms_min_gap)
    else:
        print(f"[rerank] margin={margin:.4f} < {threshold:.4f} ({margin_key}) -> che do TRAI RUI RO")
        ranked = _spread_mode(hits, top_k, score_key, apply_nms, nms_min_gap)

    if not preserve_recall_tail:
        return ranked

    kept = _preserve_recall_tail(
        ranked, hits, top_k, head_n=head_n,
        apply_nms=apply_nms, nms_min_gap=nms_min_gap, score_key=score_key,
    )
    n_cuu = len({(h["video_id"], h["frame_idx"]) for h in kept}
                - {(h["video_id"], h["frame_idx"]) for h in ranked})
    if n_cuu:
        print(f"[rerank] giữ đuôi theo thứ tự retrieval gốc (head_n={head_n}) -> cứu lại {n_cuu} "
              f"ứng viên bị hậu xử lý loại")
    return kept


def _preserve_recall_tail(
    ranked: list[dict],
    pool: list[dict],
    top_k: int,
    head_n: int = RECALL_HEAD_N,
    *,
    apply_nms: bool = False,
    nms_min_gap: float = MIN_TIME_GAP,
    score_key: str = "score",
) -> list[dict]:
    """Giữ nguyên `head_n` dòng đầu do rerank quyết định, phần còn lại lặp lại theo THỨ TỰ ƯU TIÊN.

    Mục đích: không để hậu xử lý VỨT HẲN ứng viên mà retrieval đã tìm ra (xem ghi chú ở RECALL_HEAD_N),
    nhưng cũng không lãng phí dòng nộp cho frame trùng cảnh.

    Thứ tự ưu tiên khi lặp phần dưới — đây là XẾP HẠNG, không phải chọn một trong hai, nên không bao
    giờ bỏ phí một dòng nào:
      1. Đỉnh cục bộ của `pool` (sau Temporal NMS) chưa có trong phần đầu — giá trị cao nhất.
      2. Frame bị NMS nén xuống (trùng cảnh với một đỉnh ở trên) — giá trị thấp vì gần như chắc chắn
         sai/đúng CÙNG LÚC với đỉnh của nó, nhưng vẫn hơn để trống dòng.
      3. Phần còn lại của `ranked` (vd frame đào sâu từ fast_retrieve_for_video — KHÔNG nằm trong pool).

    Vì sao mục 2 đứng sau mục 1 chứ không bị loại hẳn: R@k chỉ tính CÚ TRÚNG ĐẦU TIÊN, nên 2 frame sát
    nhau trong cùng 1 cảnh gần như hoàn toàn tương quan — frame thứ hai đáng ~0. Nhưng dòng 21-100
    cũng chỉ đáng 0.4/0.2 điểm, và nếu pool đã hết ứng viên đa dạng thì giữ nó vẫn hơn bỏ trống.

    Khoá chống trùng là (video_id, frame_idx): `frame_idx` chỉ duy nhất TRONG 1 video (index cục bộ,
    xem index_store.py) nên bắt buộc phải ghép với video_id, không dùng frame_idx một mình.
    """
    head: list[dict] = ranked[:head_n] if head_n > 0 else []
    _key = lambda h: (h["video_id"], h["frame_idx"])
    seen = {_key(h) for h in head}

    con_lai = [h for h in pool if _key(h) not in seen]
    if apply_nms and con_lai:
        dinh = temporal_nms(con_lai, min_gap=nms_min_gap, max_per_video=None, score_key=score_key)
        dinh_keys = {_key(h) for h in dinh}
        bi_nen = [h for h in con_lai if _key(h) not in dinh_keys]
        nguon = (dinh, bi_nen, ranked[len(head):])
    else:
        nguon = (con_lai, ranked[len(head):])

    tail: list[dict] = []
    for source in nguon:
        for h in source:
            k = _key(h)
            if k in seen:
                continue
            seen.add(k)
            tail.append(h)
            if len(head) + len(tail) >= top_k:
                return (head + tail)[:top_k]

    return (head + tail)[:top_k]


def _bet_mode(
    hits: list[dict],
    top_video_id: str,
    top_k: int,
    query_text: str | None,
    score_key: str = "score",
    apply_nms: bool = False,
    nms_min_gap: float = MIN_TIME_GAP,
) -> list[dict]:
    """"Đặt cược" = THÊM ứng viên đào sâu từ video đang thắng, để chúng cạnh tranh công bằng
    theo score thật với phần còn lại — KHÔNG ép chúng lên đầu danh sách bất kể score (làm vậy sẽ
    đẩy các hit đúng từ video khác xuống dưới một cách vô lý, gây regression R@20/R@50 — xem
    docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md).

    Với Temporal NMS bật: sau khi sắp xếp, loại keyframe sát nhau trong cùng video, rồi áp TRẦN
    BET_VIDEO_SHARE (mặc định 50% số dòng) cho chính video đặt cược — BẢN ĐẶC TẢ §3.2. Không có trần
    này thì khi 1 video áp đảo, nó có thể chiếm gần hết 100 dòng bằng các frame gần giống nhau.
    """
    n_target = max(1, int(top_k * BET_VIDEO_SHARE))
    top_video_hits = [h for h in hits if h["video_id"] == top_video_id]

    if query_text and len(top_video_hits) < n_target:
        from scripts.agent.tools.retrieve import fast_retrieve_for_video
        deeper = fast_retrieve_for_video(query_text, top_video_id, top_k=n_target)
        # Chỉ loại trùng với frame_idx CỦA CHÍNH top_video_id — frame_idx là index cục bộ trong từng
        # video (không globally unique, xem index_store.py), so với cả "hits" (nhiều video) sẽ xoá nhầm
        # các ứng viên đào sâu hợp lệ chỉ vì trùng frame_idx với 1 video khác hoàn toàn.
        seen_frame_idx = {h["frame_idx"] for h in top_video_hits}
        extra = [d for d in deeper if d["frame_idx"] not in seen_frame_idx]
        if score_key != "score":
            # Ứng viên đào sâu KHÔNG nằm trong pool dense ban đầu (nếu nằm thì đã bị dedup ở trên) ->
            # thứ hạng dense toàn cục của chúng chắc chắn sau pool. Gán điểm theo đúng công thức RRF
            # với thứ hạng ước lượng đó, thay vì để trống (sẽ thành 0 và bị đẩy xuống cuối một cách
            # tuỳ tiện) hay gán bừa điểm cao (sẽ vượt mặt ứng viên pool thật sự tốt hơn).
            from scripts.agent.tools.fusion import RRF_K, W_DENSE
            base_rank = len(hits) + 1
            for i, d in enumerate(sorted(extra, key=lambda h: -h["score"])):
                d[score_key] = W_DENSE / (RRF_K + base_rank + i)
        hits = hits + extra

    result = sorted(hits, key=lambda h: -float(h.get(score_key, 0.0)))
    if apply_nms:
        result = temporal_nms(result, min_gap=nms_min_gap, max_per_video=None, score_key=score_key)

    # Trần cho video đặt cược: vẫn ưu tiên nó mạnh (50% số dòng) nhưng không để nó nuốt cả danh sách.
    capped: list[dict] = []
    n_top_video = 0
    for h in result:
        if h["video_id"] == top_video_id:
            if n_top_video >= n_target:
                continue
            n_top_video += 1
        capped.append(h)
        if len(capped) >= top_k:
            break
    return capped[:top_k]


def _spread_mode(
    hits: list[dict],
    top_k: int,
    score_key: str = "score",
    apply_nms: bool = False,
    nms_min_gap: float = MIN_TIME_GAP,
) -> list[dict]:
    """"Trải rủi ro" = ưu tiên theo THỨ HẠNG CỦA VIDEO (best score/video), lấy hết dần (đến
    SPREAD_MAX_PER_VIDEO) cho từng video trước khi chuyển sang video kế — KHÔNG round-robin dàn đều.

    Đã thử round-robin (1 hit/video/vòng) trước — bị lỗi: khi pool rộng (vd 250+ video khác nhau,
    xem docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md), vòng 0 một mình đã chiếm hết
    top_k cho MỌI video 1 hit, nên video đúng (đang ở hạng tốt, vd #44/255) chỉ được 1 hit đầu (có thể
    không phải frame đúng) mà không còn lượt vòng 1/2 để lấy frame đúng sau đó — mất hẳn kết quả đã có
    trước khi rerank (regression). Fix: xử lý video theo thứ tự điểm tốt nhất, MỖI video được lấy đủ
    (tối đa SPREAD_MAX_PER_VIDEO) hit CỦA CHÍNH NÓ trước khi xét video kế tiếp — video đúng thường nằm
    trong nhóm điểm khá tốt (không cần toàn bộ hạng đầu), được đảm bảo có đủ kiện để frame đúng (không
    nhất thiết là frame điểm cao nhất của video) vẫn lọt vào top_k.
    """
    by_video: dict[str, list[dict]] = {}
    video_best_score: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        by_video.setdefault(vid, []).append(h)  # hits() đã sort giảm dần -> list này cũng giảm dần
        val = float(h.get(score_key, 0.0))
        if vid not in video_best_score or val > video_best_score[vid]:
            video_best_score[vid] = val

    videos_by_score = sorted(by_video.keys(), key=lambda v: -video_best_score[v])

    result: list[dict] = []
    for vid in videos_by_score:
        if apply_nms:
            # Lấy đỉnh cục bộ (local peak) thay vì SPREAD_MAX_PER_VIDEO frame đầu danh sách — các
            # frame đầu thường sát nhau trong cùng 1 cảnh, chiếm chỗ mà không tăng cơ hội trúng.
            picked = temporal_nms(
                by_video[vid], min_gap=nms_min_gap,
                max_per_video=SPREAD_MAX_PER_VIDEO, score_key=score_key,
            )
        else:
            picked = by_video[vid][:SPREAD_MAX_PER_VIDEO]
        result.extend(picked)
        if len(result) >= top_k:
            break
    return result[:top_k]

# Bo test: tests/unit/test_rerank.py
