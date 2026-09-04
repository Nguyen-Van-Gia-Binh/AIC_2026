"""Test cho answer_qa.py + qa_normalize.py + qa_classify.py — chuyển từ _run_self_tests() cũ.

Giữ nguyên mọi assert. Khối cũ gán đè biến global `call_llm`; ở đây dùng `monkeypatch` và patch
ĐÚNG module chứa hàm — sau khi tách file, canonicalize_answer đọc call_llm của qa_normalize chứ
không phải của answer_qa (patch nhầm thì test gọi LLM thật mà vẫn có vẻ "pass").
"""
from __future__ import annotations

from scripts.agent.tools import answer_qa, qa_normalize
from scripts.agent.tools.answer_qa import answer_from_hits, ocr_direct_answer
from scripts.agent.tools.qa_normalize import canonicalize_answer, is_non_answer

_HIT = {"video_id": "V", "n": 1, "frame_idx": 0, "frame_id": 1, "pts_time": 10.0,
        "score": 0.9, "jpg_path": None}


def test_tang_1_va_crosscheck_deu_nhan_duoc_transcript(monkeypatch) -> None:
    captured: list[str] = []

    def _fake_call_llm(prompt, **kwargs):
        captured.append(prompt)
        if "Detected objects in candidate frames" in prompt:
            return "a red car"
        if "Is this answer plausible" in prompt:
            return "YES"
        return "unexpected prompt"

    monkeypatch.setattr(answer_qa, "call_llm", _fake_call_llm)
    monkeypatch.setattr(answer_qa, "get_objects", lambda vid, n: ["car", "person"])
    monkeypatch.setattr(answer_qa, "get_transcript",
                        lambda vid, pts, window=7.5: "a red car passes by quickly")

    result = answer_from_hits("What color is the car?", [_HIT], top_n=1)
    assert result["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result['method']}"
    assert result["answer"] == "a red car", f"Answer sai: {result['answer']!r}"

    tier1 = next(p for p in captured if "Detected objects in candidate frames" in p)
    assert "a red car passes by quickly" in tier1, "Tier 1 prompt phai chua transcript hint"
    crosscheck = next(p for p in captured if "Is this answer plausible" in p)
    assert "a red car passes by quickly" in crosscheck, "Crosscheck prompt phai chua transcript"


def test_transcript_rong_khong_crash(monkeypatch) -> None:
    monkeypatch.setattr(answer_qa, "call_llm",
                        lambda prompt, **k: "a red car" if "Detected objects" in prompt else "YES")
    monkeypatch.setattr(answer_qa, "get_objects", lambda vid, n: ["car", "person"])
    monkeypatch.setattr(answer_qa, "get_transcript", lambda vid, pts, window=7.5: "")
    result = answer_from_hits("What color is the car?", [_HIT], top_n=1)
    assert result["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result['method']}"


def test_canonical_rule_based_khong_goi_llm() -> None:
    assert canonicalize_answer("The answer is: màu trắng") == "màu trắng"
    assert canonicalize_answer("Trong hình có một chiếc xe") == "một chiếc xe"
    assert canonicalize_answer("There are 15 people") == "15 people"
    assert canonicalize_answer("15") == "15", "Answer da chuan phai giu nguyen"


def test_canonical_qua_llm_va_tu_choi_ban_dai_hon(monkeypatch) -> None:
    long_answer = "Ngọn núi xuất hiện trong khung hình này chính là núi Phú Sĩ ở Nhật Bản"

    monkeypatch.setattr(qa_normalize, "call_llm", lambda prompt, **k: "Phú Sĩ")
    assert canonicalize_answer(long_answer, "Núi gì?") == "Phú Sĩ"

    monkeypatch.setattr(qa_normalize, "call_llm",
                        lambda *a, **k: "Đây là một lời giải thích rất dài hơn cả câu trả lời gốc ban đầu")
    assert canonicalize_answer(long_answer, "Núi gì?") == long_answer, (
        "LLM tra ve dai hon -> phai giu ban rule-based"
    )


def test_canonical_khong_bia_so(monkeypatch) -> None:
    # VLM mô tả lòng vòng, không nêu số sạch; canonical LLM "chế" ra '105' -> phải bị từ chối.
    ramble = ("Dựa trên hình ảnh, hông chiếc xe màu trắng có in dòng chữ Hán kèm số hiệu; "
              "nếu xét riêng con số trên thân xe thì đó là ký hiệu biển số / số hiệu của xe")
    monkeypatch.setattr(qa_normalize, "call_llm", lambda *a, **k: "105")
    got = canonicalize_answer(ramble, "Con số trên hông xe là số mấy?")
    assert got != "105" and "105" not in got  # số bịa bị từ chối, giữ bản rule-based

    # Nhưng nếu con số THỰC SỰ có trong answer gốc thì vẫn rút gọn bình thường.
    has_num = "Nhìn kỹ khung hình thứ ba, con số sơn trên hông xe màu trắng là 1204 rõ ràng"
    monkeypatch.setattr(qa_normalize, "call_llm", lambda *a, **k: "1204")
    assert canonicalize_answer(has_num, "Con số trên hông xe là số mấy?") == "1204"


def test_expand_cluster_window_neo_khung_diem_cao_bo_ria_rac(monkeypatch) -> None:
    # Kịch bản đã cắn câu "số hông xe": lõi retrieval n≈202-209, thêm 3 khung BM25-only lẻ ở xa
    # (n=217 điểm thấp, n=218/219 điểm 0). Cửa sổ phải neo vào n=209 (điểm cao nhất), kéo được
    # n=210/211 vào, và KHÔNG để n=218/219 chiếm chỗ.
    from scripts.agent.tools import answer_qa, index_store

    scored = {202: 0.157, 203: 0.189, 204: 0.160, 205: 0.161,
              206: 0.187, 209: 0.198, 217: 0.164, 218: 0.0, 219: 0.0}
    hits = [{"n": n, "video_id": "L21_V009", "jpg_path": f"/fake/{n}.jpg", "score": s}
            for n, s in scored.items()]

    monkeypatch.setattr(index_store, "get_index", lambda qa=False: (None, object(), None))
    monkeypatch.setattr(index_store, "key_index",
                        lambda qa=False: {("L21_V009", k): k for k in range(180, 240)})
    monkeypatch.setattr(index_store, "row_to_hit",
                        lambda meta, row_i, score: {"n": row_i, "video_id": "L21_V009",
                                                    "jpg_path": f"/fake/{row_i}.jpg", "score": score})

    class _P:
        def __init__(self, *_a): ...
        def exists(self): return True
    monkeypatch.setattr(answer_qa, "Path", _P)

    out = answer_qa._expand_cluster_window(hits, pad=2, cap=10)
    out_ns = [h["n"] for h in out]
    assert out_ns[0] == 209                      # neo = khung điểm cao nhất
    assert 210 in out_ns and 211 in out_ns       # neighbor liền kề đã vào
    assert 218 not in out_ns and 219 not in out_ns  # rìa BM25-only bị đẩy khỏi cap
    assert len(out_ns) <= 10


def test_cong_chong_ao_giac() -> None:
    assert is_non_answer("The text is not legible in any frame") is True
    assert is_non_answer("Không nhìn rõ biển số") is True
    assert is_non_answer("") is True
    assert is_non_answer("màu trắng") is False


def test_cong_chong_ao_giac_mau_phu_dinh_dai() -> None:
    # VLM hay trả câu phủ định dài dòng — trước đây lọt lưới, giữ conf 0.85, chặn vòng 2.
    assert is_non_answer(
        "Dựa trên các khung hình video, phần hông xe màu trắng không hiển thị rõ con số nào."
    ) is True
    assert is_non_answer("Không hiển thị") is True
    assert is_non_answer("không hiện số nào") is True
    assert is_non_answer("The number on the side of the car is not shown") is True
    assert is_non_answer("No number is visible in the frame") is True
    assert is_non_answer("Không có dữ liệu") is True
    # Câu phủ định dài, "không" cách "con số nào" cả chục từ (mẫu VLM hay trả).
    assert is_non_answer(
        "Dựa vào các hình ảnh được cung cấp, không có chi tiết nào hiển thị phần hông "
        "xe màu trắng hoặc con số nào được viết trên đó."
    ) is True
    # Không được nuốt nhầm đáp án thật có chứa "số".
    assert is_non_answer("số 5") is False
    assert is_non_answer("63A-01258") is False
    assert is_non_answer("The number is 1204") is False
    assert is_non_answer("số nào cũng được, đáp án là 7") is False


def test_ocr_direct_overwrite_rat_chat() -> None:
    assert ocr_direct_answer("Biển số xe là gì?", {0: ["AG 09399"], 1: ["AG 09399"]}) == "09399"
    assert ocr_direct_answer("Biển số xe là gì?", {0: ["09399"], 1: ["12627"]}) is None, (
        "Nhieu chuoi so khac nhau -> khong ghi de, de VLM quyet dinh"
    )
    assert ocr_direct_answer("Có bao nhiêu người trong hình?", {0: ["15"]}) is None, (
        "Cau hoi DEM vat the khong duoc de OCR ghi de"
    )
    assert ocr_direct_answer("Biển số xe là gì?", {}) is None


def test_answer_from_hits_max_tier_1_skips_vision(monkeypatch) -> None:
    calls = []
    def _mock_call(prompt, model="auto", **kwargs):
        calls.append((prompt, model))
        return "ANSWER: quả bóng màu đỏ"

    monkeypatch.setattr(answer_qa, "call_llm", _mock_call)
    monkeypatch.setattr(answer_qa, "get_objects", lambda vid, n: ["sports ball", "person"])
    monkeypatch.setattr(answer_qa, "get_transcript", lambda vid, pts, window=7.5: "")

    res = answer_from_hits("Quả bóng màu gì?", [_HIT], top_n=1, max_tier=1)
    assert res["method"] == "objects"
    assert res["answer"] == "quả bóng màu đỏ"
    # Chỉ gọi text LLM, không gọi vision
    assert all(model != "vision" for prompt, model in calls)

