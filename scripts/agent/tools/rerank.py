"""
rerank.py — Risk-aware re-ranking hau xu ly cho KIS/QA, chay sau khi fast_retrieve tra ve top-K.

Y tuong (PLAN.md Phase 3): quan sat "margin" giua video ung vien manh nhat va video ung vien manh
nhi trong danh sach hits (so sanh best score moi video).
  - Margin lon (1 video noi bat han so voi phan con lai) -> che do "dat cuoc": danh nhieu dong ket
    qua hon cho dung video do (dao sau hon trong video do bang fast_retrieve_for_video neu can), tang
    co hoi trung R@1/R@5.
  - Margin nho (khong video nao noi bat ro) -> che do "trai rui ro": gioi han so dong toi da tren 1
    video trong danh sach, ep ket qua trai rong hon nhieu video, tang co hoi trung R@50/R@100.

Khong goi LLM (PLAN.md Phase 3: "khong can LLM"). Chi phu thuoc fast_retrieve_for_video khi can dao
sau them trong video dang "dat cuoc" — khong tu doc/ghi index, khong doi retrieve.py.

MARGIN_THRESHOLD / BET_VIDEO_SHARE / SPREAD_MAX_PER_VIDEO la gia tri khoi diem, da can chinh so bo
bang du lieu that (xem docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md) —
se tinh chinh tiep o Phase 6 checkpoint bang benchmark that (tests/e2e/test_phase3_rerank.py),
khong phai doan mo hinh.

Usage:
    from scripts.agent.tools.rerank import apply_risk_aware_ranking
    ranked = apply_risk_aware_ranking(hits, top_k=100, query_text="a red car parked on the street")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.tools.temporal_nms import temporal_nms, MIN_TIME_GAP

# Nguong chenh lech score (cosine similarity CLIP, thuong ~0.28-0.31 cho query that) de coi video #1
# la "noi bat ro rang" so voi video #2.
MARGIN_THRESHOLD = 0.012

# Nguong margin TUONG DOI (ti le) dung khi xep hang theo diem RRF thay vi cosine (hybrid retrieval —
# xem retrieve.hybrid_retrieve). Diem RRF co thang do rat khac (w/(k+rank), ~0.012 o hang 1 va giam
# rat cham), nen mot nguong TUYET DOI nhu MARGIN_THRESHOLD se khong bao gio dat -> luon roi vao che do
# trai rui ro. Dung ti le so voi diem cao nhat de giu dung y nghia "video #1 noi bat hon han #2".
MARGIN_RATIO_RRF = 0.05

# Che do "dat cuoc": ti le toi da so dong (tren top_k) danh cho video noi bat nhat.
BET_VIDEO_SHARE = 0.5

# Che do "trai rui ro": so dong toi da cho 1 video khi khong co video nao noi bat.
SPREAD_MAX_PER_VIDEO = 3

# So ung vien tho can lay tu fast_retrieve TRUOC KHI rerank/cat ve top_k submission. Lon hon han so voi
# top_k thuc te (thuong 100) vi chan doan thuc te tren eval_ground_truth.json cho thay GT frame chi nam
# trong top-100 o 12/23 cau nhung nam trong top-500 o 20/23 cau (xem
# docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md) — trong khi chi phi tinh gan nhu mien
# phi (fast_retrieve da nhan full ma tran 177K keyframe, chi argsort cat nhieu hon).
RETRIEVAL_POOL_SIZE = 500

# So dong DAU danh sach do rerank toan quyen quyet dinh. Tu dong (RECALL_HEAD_N + 1) tro di, danh
# sach duoc lap lai theo DUNG THU TU RETRIEVAL GOC (xem _preserve_recall_tail).
#
# Vi sao: do that tren 18 cau KIS cua eval_ground_truth.json cho thay hau xu ly KHONG hon retrieval
# thuan o bat ky moc nao, va THUA ro tu hang 20 tro di:
#     retrieval thuan (run_eval.py) : R@1 0.389  R@5 0.611  R@20 0.833  R@50 0.889  R@100 1.000
#     pipeline that (score_pipelines): R@1 0.389  R@5 0.611  R@20 0.722  R@50 0.778  R@100 0.833
# Nguyen nhan: _bet_mode bo qua (`continue`) moi hit cua video dat cuoc vuot tran BET_VIDEO_SHARE, va
# _spread_mode chi lay SPREAD_MAX_PER_VIDEO hit/video roi `break` — ca hai deu VUT HAN ung vien ma
# retrieval da tim ra, thay bang dong khac.
#
# Lap luan (khong phu thuoc co mau eval nho): Final Score chi tinh CU TRUNG DAU TIEN
# (R@k = max trong k dong dau), va dong 21-100 chi dang 0.4/0.2 diem. Nen XOA mot ung vien retrieval
# de nhuong cho cho dong khac o phan duoi khong bao gio co loi — cung lam la hoa. Day dong do xuong
# cuoi thi vua giu duoc cai loi cua rerank o dau, vua khong mat gi o duoi. Do la mot lua chon thiet
# ke BI TROI HOAN TOAN (strictly dominated), khong phai chuyen tinh chinh tham so.
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
    """Sap xep lai hits theo chien luoc "dat cuoc" hoac "trai rui ro" tuy margin giua cac video.

    Args:
        hits: Ket qua da co tu fast_retrieve/hybrid_retrieve, da sap xep giam dan theo score_key.
        top_k: So dong toi da tra ve (gioi han submission — xem build_submission.py).
        query_text: Query da rewrite (tieng Anh) dung de dao sau them trong video "dat cuoc" khi can.
                    None = chi sap xep lai hits san co, khong goi them fast_retrieve_for_video.
        score_key: Truong dung de XEP HANG. "score" (mac dinh) = cosine similarity nhu truoc gio;
                   "rrf_score" khi hits den tu retrieve.hybrid_retrieve (Dense+BM25 da dung hop).
        margin_key: Truong dung de QUYET DINH dat cuoc/trai rui ro — mac dinh "score" (cosine) DU
                   cho xep hang bang rrf_score. Ly do: MARGIN_THRESHOLD duoc can chinh bang benchmark
                   that tren thang cosine; do margin tren thang RRF (w/(k+rank), khoang cach giua cac
                   hang rat nho va deu) lam che do dat cuoc bat sai nhieu hon han — do that tren 18
                   cau KIS: Final 0.656 (margin cosine) vs 0.633 (margin RRF).
        apply_nms: Bat Temporal NMS (BAN DAC TA §3.2) — loai keyframe lan can trong cung video de
                   khong lang phi dong nop bai cho cung 1 canh. Mac dinh TAT de duong goi cu
                   (pipeline_qa) giu nguyen hanh vi da benchmark; pipeline_kis bat tuong minh.
        nms_min_gap: Khoang cach thoi gian toi thieu (giay) giua 2 keyframe duoc giu trong 1 video.
        preserve_recall_tail: Giu phan duoi danh sach theo dung thu tu retrieval goc, de hau xu ly
                    khong vut mat ung vien ma retrieval da tim ra (xem ghi chu o RECALL_HEAD_N).
                    Mac dinh BAT. Dat False de tai hien hanh vi cu khi can do truoc-sau.
        head_n: So dong dau do rerank toan quyen quyet dinh khi preserve_recall_tail=True.

    Returns:
        list[dict] cung dinh dang voi hits dau vao, do dai <= top_k.
    """
    if not hits:
        return hits

    # None = doc tu env (tien le AIC_RETRIEVE_MODEL/AIC_MODE: env var, mac dinh giu hanh vi tot nhat
    # da do, doi duoc tuong minh khi can benchmark truoc-sau ma khong phai sua code).
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

    # Nguong: tuyet doi tren thang cosine (da can chinh bang benchmark that), tuong doi neu ai do
    # co tinh do margin tren thang RRF (khong phai mac dinh — xem docstring margin_key).
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
        print(f"[rerank] giu duoi theo thu tu retrieval goc (head_n={head_n}) -> cuu lai {n_cuu} "
              f"ung vien bi hau xu ly loai")
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
    """Giu nguyen `head_n` dong dau do rerank quyet dinh, phan con lai lap lai theo THU TU UU TIEN.

    Muc dich: khong de hau xu ly VUT HAN ung vien ma retrieval da tim ra (xem ghi chu o RECALL_HEAD_N),
    nhung cung khong lang phi dong nop cho frame trung canh.

    Thu tu uu tien khi lap phan duoi — day la XEP HANG, khong phai chon mot trong hai, nen khong bao
    gio bo phi mot dong nao:
      1. Dinh cuc bo cua `pool` (sau Temporal NMS) chua co trong phan dau — gia tri cao nhat.
      2. Frame bi NMS nen xuong (trung canh voi mot dinh o tren) — gia tri thap vi gan nhu chac chan
         sai/dung CUNG LUC voi dinh cua no, nhung van hon de trong dong.
      3. Phan con lai cua `ranked` (vd frame dao sau tu fast_retrieve_for_video — KHONG nam trong pool).

    Vi sao muc 2 dung sau muc 1 chu khong bi loai han: R@k chi tinh CU TRUNG DAU TIEN, nen 2 frame sat
    nhau trong cung 1 canh gan nhu hoan toan tuong quan — frame thu hai dang ~0. Nhung dong 21-100
    cung chi dang 0.4/0.2 diem, va neu pool da het ung vien da dang thi giu no van hon bo trong.

    Khoa chong trung la (video_id, frame_idx): `frame_idx` chi duy nhat TRONG 1 video (index cuc bo,
    xem index.py) nen bat buoc phai ghep voi video_id, khong dung frame_idx mot minh.
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
    """"Dat cuoc" = ADD them ung vien dao sau tu video dang thang, de chung canh tranh cong bang
    theo score that voi phan con lai — KHONG ep chung len dau danh sach bat ke score (lam vay se
    day cac hit dung tu video khac xuong duoi mot cach vo ly, gay regression R@20/R@50 — xem
    docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md).

    Voi Temporal NMS bat: sau khi sap xep, loai keyframe sat nhau trong cung video, roi ap TRAN
    BET_VIDEO_SHARE (mac dinh 50% so dong) cho chinh video dat cuoc — BAN DAC TA §3.2. Khong co tran
    nay thi khi 1 video ap dao, no co the chiem gan het 100 dong bang cac frame gan giong nhau.
    """
    n_target = max(1, int(top_k * BET_VIDEO_SHARE))
    top_video_hits = [h for h in hits if h["video_id"] == top_video_id]

    if query_text and len(top_video_hits) < n_target:
        from scripts.agent.tools.retrieve import fast_retrieve_for_video
        deeper = fast_retrieve_for_video(query_text, top_video_id, top_k=n_target)
        # Chi loai trung voi frame_idx CUA CHINH top_video_id — frame_idx la index cuc bo trong tung
        # video (khong globally unique, xem index.py), so voi ca "hits" (nhieu video) se xoa nham cac
        # ung vien dao sau hop le chi vi trung frame_idx voi 1 video khac hoan toan.
        seen_frame_idx = {h["frame_idx"] for h in top_video_hits}
        extra = [d for d in deeper if d["frame_idx"] not in seen_frame_idx]
        if score_key != "score":
            # Ung vien dao sau KHONG nam trong pool dense ban dau (neu nam thi da bi dedup o tren) ->
            # thu hang dense toan cuc cua chung chac chan sau pool. Gan diem theo dung cong thuc RRF
            # voi thu hang uoc luong do, thay vi de trong (se thanh 0 va bi day xuong cuoi mot cach
            # tuy tien) hay gan bua diem cao (se vuot mat ung vien pool that su tot hon).
            from scripts.agent.tools.fusion import RRF_K, W_DENSE
            base_rank = len(hits) + 1
            for i, d in enumerate(sorted(extra, key=lambda h: -h["score"])):
                d[score_key] = W_DENSE / (RRF_K + base_rank + i)
        hits = hits + extra

    result = sorted(hits, key=lambda h: -float(h.get(score_key, 0.0)))
    if apply_nms:
        result = temporal_nms(result, min_gap=nms_min_gap, max_per_video=None, score_key=score_key)

    # Tran cho video dat cuoc: van uu tien no manh (50% so dong) nhung khong de no nuot ca danh sach.
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
    """"Trai rui ro" = uu tien theo THU HANG CUA VIDEO (best score/video), lay het dan (den
    SPREAD_MAX_PER_VIDEO) cho tung video truoc khi chuyen sang video ke — KHONG round-robin dan deu.

    Da thu round-robin (1 hit/video/vong) truoc — bi loi: khi pool rong (vd 250+ video khac nhau,
    xem docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md), vong 0 mot minh da chiem het
    top_k cho MOI video 1 hit, nen video dung (dang o hang tot, vd #44/255) chi duoc 1 hit dau (co the
    khong phai frame dung) ma khong con luot vong 1/2 de lay frame dung sau do — mat han ket qua da co
    truoc khi rerank (regression). Fix: xu ly video theo thu tu diem tot nhat, MOI video duoc lay du
    (toi da SPREAD_MAX_PER_VIDEO) hit CUA CHINH NO truoc khi xet video ke tiep — video dung thuong nam
    trong nhom diem kha tot (khong can toan bo hang dau), duoc dam bao co du kien de frame dung (khong
    nhat thiet la frame diem cao nhat cua video) van lot vao top_k.
    """
    by_video: dict[str, list[dict]] = {}
    video_best_score: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        by_video.setdefault(vid, []).append(h)  # hits() da sort giam dan -> list nay cung giam dan
        val = float(h.get(score_key, 0.0))
        if vid not in video_best_score or val > video_best_score[vid]:
            video_best_score[vid] = val

    videos_by_score = sorted(by_video.keys(), key=lambda v: -video_best_score[v])

    result: list[dict] = []
    for vid in videos_by_score:
        if apply_nms:
            # Lay dinh cuc bo (local peak) thay vi SPREAD_MAX_PER_VIDEO frame dau danh sach — cac
            # frame dau thuong sat nhau trong cung 1 canh, chiem cho ma khong tang co hoi trung.
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


# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
if __name__ == "__main__":
    from collections import Counter

    def _fake_hit(video_id: str, i: int, score: float) -> dict:
        return {
            "video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
            "pts_time": 0.0, "score": score, "jpg_path": None,
        }

    # Test 1: bet mode - video A noi bat ro rang (margin lon)
    hits_bet = (
        [_fake_hit("A", i, 0.9 - i * 0.001) for i in range(5)]
        + [_fake_hit(f"V{i}", i, 0.5 - i * 0.001) for i in range(20)]
    )
    out_bet = apply_risk_aware_ranking(hits_bet, top_k=10)
    n_a = sum(1 for h in out_bet if h["video_id"] == "A")
    assert n_a >= 5, f"Bet mode phai uu tien video A, chi thay {n_a}/10"
    print(f"[rerank] Test bet mode: OK ({n_a}/10 dong la video A)")

    # Test 2: spread mode - khong video nao noi bat (diem gan bang nhau), du nhieu video khac nhau
    # (20 video x 5 hit = 100 hit) de cap 3/video co the thoa man top_k=30 (can >=10 video de dat 30).
    hits_spread = [
        _fake_hit(f"V{i // 5}", i, 0.5 - i * 0.0001) for i in range(100)
    ]
    # 2a. Hanh vi CU (preserve_recall_tail=False): tran SPREAD_MAX_PER_VIDEO ap cho CA danh sach.
    out_spread_cu = apply_risk_aware_ranking(hits_spread, top_k=30, preserve_recall_tail=False)
    counts_cu = Counter(h["video_id"] for h in out_spread_cu)
    assert max(counts_cu.values()) <= SPREAD_MAX_PER_VIDEO, \
        f"Spread mode (hanh vi cu) vuot qua {SPREAD_MAX_PER_VIDEO} dong/video: {counts_cu}"
    print(f"[rerank] Test spread mode (cu): OK ({len(counts_cu)} video / {len(out_spread_cu)} dong, "
          f"max/video={max(counts_cu.values())})")

    # 2b. Hanh vi MOI: tran chi con ap cho PHAN DAU (head_n dong). Tu dong head_n+1 tro di danh sach
    # lap theo thu tu retrieval goc, nen 1 video CO THE co qua 3 dong — day la doi moi co chu y, khong
    # phai loi: dong 21-100 chi dang 0.4/0.2 diem nen giu them ung vien retrieval o do luon tot hon
    # vut chung di (xem ghi chu o RECALL_HEAD_N).
    out_spread = apply_risk_aware_ranking(hits_spread, top_k=30, head_n=10)
    counts_head = Counter(h["video_id"] for h in out_spread[:10])
    assert max(counts_head.values()) <= SPREAD_MAX_PER_VIDEO, \
        f"Phan dau van phai giu tran {SPREAD_MAX_PER_VIDEO} dong/video: {counts_head}"
    # Bat bien moi: khong duoc mat ung vien nao ma retrieval da tim ra, khi con cho trong.
    key = lambda L: {(h["video_id"], h["frame_idx"]) for h in L}
    mat = key(hits_spread[:30]) - key(out_spread)
    assert not mat, f"Mat {len(mat)} ung vien retrieval du con cho trong: {sorted(mat)[:5]}"
    print(f"[rerank] Test spread mode (moi): OK (phan dau max/video={max(counts_head.values())}, "
          f"khong mat ung vien retrieval nao)")

    # Test 3: hits rong khong crash
    assert apply_risk_aware_ranking([], top_k=10) == []
    print("[rerank] Test empty input: OK")

    # Test 4: bet mode KHONG duoc loai ung vien dao sau chi vi trung frame_idx voi 1 VIDEO KHAC —
    # frame_idx la index cuc bo tung video (khong globally unique), dedup sai o ban truoc chi kiem tra
    # "hits" (ca pool nhieu video) thay vi chi rieng top_video_hits (code review Phase 6).
    import scripts.agent.tools.retrieve as _retrieve_module

    def _fake_fetch_deeper(query_text, video_id, top_k):
        # Video A dat cuoc co 1 ung vien dao sau moi (frame_idx=99) chua tung xuat hien trong hits cua
        # rieng A, nhung video KHAC (V0) trong pool da co san frame_idx=99 — dedup sai se loai nham.
        return [_fake_hit("A", 99, 0.85)]

    _orig_fetch = _retrieve_module.fast_retrieve_for_video
    _retrieve_module.fast_retrieve_for_video = _fake_fetch_deeper
    try:
        hits_collision = (
            [_fake_hit("A", i, 0.9 - i * 0.001) for i in range(3)]          # video A: chi 3 hit co san
            + [_fake_hit("V0", 99, 0.5)]                                     # video khac trung frame_idx=99
            + [_fake_hit(f"V{i}", i, 0.4 - i * 0.001) for i in range(1, 20)]
        )
        out_collision = apply_risk_aware_ranking(hits_collision, top_k=10, query_text="fake query")
        frame_idxs_a = {h["frame_idx"] for h in out_collision if h["video_id"] == "A"}
        assert 99 in frame_idxs_a, (
            f"Ung vien dao sau (frame_idx=99) cua video A bi loai nham do trung voi video khac: {frame_idxs_a}"
        )
    finally:
        _retrieve_module.fast_retrieve_for_video = _orig_fetch
    print("[rerank] Test bet mode khong loai nham ung vien trung frame_idx voi video khac: OK")

    # ─── Temporal NMS + xep hang theo RRF (BAN DAC TA §2/§3.2) ────────────────────────────────
    def _hit_t(video_id: str, i: int, score: float, pts: float, rrf: float | None = None) -> dict:
        h = {
            "video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
            "pts_time": pts, "score": score, "jpg_path": None,
        }
        if rrf is not None:
            h["rrf_score"] = rrf
        return h

    # Test 5: spread mode + NMS — 5 keyframe SAT NHAU (cach 1s) cua 1 video chi con 1 dong, thay vi
    # 3 dong lien tiep cung 1 canh nhu khi tat NMS.
    hits_nms = [_hit_t("A", i, 0.5 - i * 0.0001, pts=10.0 + i * 0.5) for i in range(5)]
    hits_nms += [_hit_t(f"V{i}", i, 0.4995 - i * 0.0001, pts=float(i * 30)) for i in range(1, 20)]
    # Hanh vi CU: NMS gom 5 keyframe sat nhau cua A ve dung 1 dinh, 4 frame kia bi VUT HAN.
    out_nms_cu = apply_risk_aware_ranking(hits_nms, top_k=30, apply_nms=True,
                                          preserve_recall_tail=False)
    n_a_cu = sum(1 for h in out_nms_cu if h["video_id"] == "A")
    assert n_a_cu == 1, f"NMS (hanh vi cu) phai gom 5 keyframe sat nhau cua A ve 1 dinh, con {n_a_cu}"

    # Hanh vi MOI: chi co 24 ung vien cho top_k=30 -> con 6 cho TRONG. Vut 4 frame A di de giao ra
    # danh sach NGAN HON so ung vien san co la mat khong cong gi. Chung duoc giu, nhung phai xep SAU
    # toan bo ung vien tu video khac (uu tien 2 trong _preserve_recall_tail).
    out_nms = apply_risk_aware_ranking(hits_nms, top_k=30, apply_nms=True)
    vids = [h["video_id"] for h in out_nms]
    vi_tri_a = [i for i, v in enumerate(vids) if v == "A"]
    assert vi_tri_a and vi_tri_a[0] < SPREAD_MAX_PER_VIDEO, \
        f"Dinh cua A phai nam gan dau danh sach, dang o {vi_tri_a[:1]}"
    if len(vi_tri_a) > 1:
        vi_tri_khac_cuoi = max(i for i, v in enumerate(vids) if v != "A")
        assert vi_tri_a[1] > vi_tri_khac_cuoi, (
            "Frame A bi NMS nen phai xep SAU moi ung vien cua video khac, "
            f"dang o {vi_tri_a[1]} trong khi ung vien khac cuoi cung o {vi_tri_khac_cuoi}"
        )
    out_no_nms = apply_risk_aware_ranking(hits_nms, top_k=30, apply_nms=False,
                                          preserve_recall_tail=False)
    assert sum(1 for h in out_no_nms if h["video_id"] == "A") == SPREAD_MAX_PER_VIDEO, (
        "Tat NMS + hanh vi cu phai giu SPREAD_MAX_PER_VIDEO dong dau moi video"
    )
    # Voi backfill bat: 24 ung vien / top_k=30 nen KHONG duoc bo sot cai nao, va SPREAD_MAX_PER_VIDEO
    # dong dau tien cua A van phai nam trong phan dau danh sach.
    out_no_nms_moi = apply_risk_aware_ranking(hits_nms, top_k=30, apply_nms=False)
    assert len(out_no_nms_moi) == len(hits_nms), (
        f"Con cho trong ma van bo sot: giao {len(out_no_nms_moi)} dong / {len(hits_nms)} ung vien"
    )
    print("[rerank] Test spread mode + Temporal NMS: OK")

    # Test 6: bet mode + NMS ap tran BET_VIDEO_SHARE cho video dat cuoc (khong nuot ca danh sach).
    hits_bet_cap = [_hit_t("A", i, 0.9 - i * 0.0001, pts=float(i * 10)) for i in range(40)]
    hits_bet_cap += [_hit_t(f"V{i}", i, 0.5 - i * 0.0001, pts=float(i * 10)) for i in range(30)]
    out_cap = apply_risk_aware_ranking(hits_bet_cap, top_k=20, apply_nms=True)
    n_a_cap = sum(1 for h in out_cap if h["video_id"] == "A")
    assert n_a_cap == int(20 * BET_VIDEO_SHARE), (
        f"Video dat cuoc phai bi cap o {int(20 * BET_VIDEO_SHARE)} dong, duoc {n_a_cap}"
    )
    assert len(out_cap) == 20, f"Phai tra du top_k=20 dong, duoc {len(out_cap)}"
    print("[rerank] Test bet mode + tran BET_VIDEO_SHARE: OK")

    # Test 7: score_key='rrf_score' — xep hang theo diem RRF, KHONG theo cosine. Video B co cosine
    # thap hon nhung RRF cao hon (duoc ca BM25 dong y) phai dung tren A.
    hits_rrf = [
        _hit_t("A", 0, score=0.90, pts=0.0, rrf=0.0100),
        _hit_t("B", 0, score=0.10, pts=0.0, rrf=0.0160),
    ]
    out_rrf = apply_risk_aware_ranking(hits_rrf, top_k=2, score_key="rrf_score")
    assert out_rrf[0]["video_id"] == "B", f"Phai xep theo rrf_score, duoc {out_rrf}"
    # margin_key mac dinh van la "score" (cosine) du xep hang theo rrf_score — quyet dinh dat cuoc/
    # trai rui ro phai dua tren thang da can chinh, khong phai thang RRF.
    out_margin_rrf = apply_risk_aware_ranking(
        hits_rrf, top_k=2, score_key="rrf_score", margin_key="rrf_score"
    )
    assert [h["video_id"] for h in out_margin_rrf] == ["B", "A"], "margin_key doi duoc khi can"
    out_cos = apply_risk_aware_ranking(hits_rrf, top_k=2)
    assert out_cos[0]["video_id"] == "A", "score_key mac dinh phai van la cosine (khong doi hanh vi cu)"
    print("[rerank] Test xep hang theo rrf_score: OK")

    print("[rerank] Tat ca self-test PASS")
