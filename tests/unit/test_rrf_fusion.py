from __future__ import annotations

from scripts.agent.tools.fusion import rrf_fuse_hits


def _hit(video_id: str, n: int, score: float) -> dict:
    return {
        "video_id": video_id,
        "n": n,
        "frame_idx": n,
        "frame_id": n + 1,
        "pts_time": float(n),
        "score": score,
        "jpg_path": None,
    }


def test_rrf_fuses_shared_frames_and_keeps_model_metadata() -> None:
    model_hits = [
        [_hit("V1", 1, 0.90), _hit("V2", 2, 0.80)],
        [_hit("V2", 2, 0.70), _hit("V1", 1, 0.60)],
        [_hit("V1", 1, 0.50), _hit("V3", 3, 0.40)],
    ]

    fused = rrf_fuse_hits(model_hits, top_k=3, rrf_k=60)

    assert [(hit["video_id"], hit["n"]) for hit in fused] == [
        ("V1", 1),
        ("V2", 2),
        ("V3", 3),
    ]
    assert fused[0]["score"] == 1 / 61 + 1 / 62 + 1 / 61
    assert fused[0]["rrf_ranks"] == [1, 2, 1]
    assert fused[1]["rrf_ranks"] == [2, 1]
    assert fused[2]["rrf_ranks"] == [2]


def test_rrf_returns_empty_for_empty_streams() -> None:
    assert rrf_fuse_hits([[], []], top_k=10) == []


if __name__ == "__main__":
    test_rrf_fuses_shared_frames_and_keeps_model_metadata()
    test_rrf_returns_empty_for_empty_streams()
    print("RRF tests: PASS")