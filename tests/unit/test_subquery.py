"""Test cho scripts/agent/tools/subquery.py — tách câu con + đếm token (tất định, không cần data/)."""
from scripts.agent.tools.subquery import (
    split_subqueries,
    count_tokens,
    MAX_ENCODER_TOKENS,
    MAX_SUBQUERIES,
)


def test_max_encoder_tokens_la_64():
    # Trần kiến trúc của SigLIP/SigLIP2 text encoder — không được đổi khơi khơi.
    assert MAX_ENCODER_TOKENS == 64


def test_tach_theo_dau_cham_co_ban():
    t = ("A car interior with the steering wheel turning right. "
         "A white car turns left under a red sign with 6 Chinese characters.")
    subs = split_subqueries(t)
    assert len(subs) == 2
    assert "steering wheel" in subs[0]
    assert "red sign" in subs[1]
    assert not subs[0].endswith(".")  # dấu chấm đã bị strip


def test_bo_manh_rong_va_manh_khong_co_chu_so():
    assert split_subqueries("Hello world. ... . Foo bar.") == ["Hello world", "Foo bar"]


def test_mot_cau_hoac_khong_co_dau_cham_tra_nguyen_cau():
    assert split_subqueries("just one clause with no period") == [
        "just one clause with no period"
    ]
    assert split_subqueries("one clause.") == ["one clause."]  # <2 mảnh -> [text]


def test_gop_con_toi_da_MAX_SUBQUERIES_manh():
    # 5 câu DÀI (tổng > 64 token) -> gộp còn <= MAX_SUBQUERIES mảnh, mỗi mảnh vẫn ≤ 64 token
    # (tách vụn 4-5 mảnh hại retrieval — xem tests/eval/rewrite_eval.py).
    t = (
        "A man in a blue jacket walks slowly into a wide brightly lit conference room. "
        "He pulls out a wooden chair and sits down carefully at the long glass desk. "
        "He opens a silver laptop and the cooling fan starts spinning up. "
        "The screen displays a large colourful financial spreadsheet with many rows. "
        "He leans forward and begins typing a long sequence of numbers into a cell."
    )
    assert count_tokens(t) > MAX_ENCODER_TOKENS
    subs = split_subqueries(t)
    assert 2 <= len(subs) <= MAX_SUBQUERIES
    assert all(count_tokens(s) <= MAX_ENCODER_TOKENS for s in subs)
    joined = " ".join(subs).lower()
    for frag in ("walks slowly into a wide", "opens a silver laptop", "typing a long sequence"):
        assert frag in joined  # không mất câu nào khi gộp


def test_rong():
    assert split_subqueries("") == []
    assert split_subqueries("   ") == []


def test_count_tokens_rong_bang_0():
    assert count_tokens("") == 0
    assert count_tokens("   ") == 0


def test_count_tokens_duong_va_don_dieu():
    # Không phụ thuộc có tokenizer thật hay dùng ước lượng dự phòng: câu dài hơn -> không ít token hơn.
    ngan = count_tokens("a white car")
    dai = count_tokens(
        "a white car turning left under a red sign with six Chinese characters painted on its side"
    )
    assert ngan > 0
    assert dai >= ngan
