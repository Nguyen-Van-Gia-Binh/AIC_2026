from __future__ import annotations

import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.tools import answer_qa
from scripts.agent.tools.answer_qa import extract_visual_count, is_visual_count_question


def test_map_marker_question_is_visual_counting() -> None:
    question = "Không tính bảng chú giải, có bao nhiêu vị trí ghi nhận động đất cấp độ 4?"

    assert is_visual_count_question(question)


def test_visual_count_rejects_earthquake_scale_explanation() -> None:
    response = "Dựa vào bản đồ, thang đo cường độ gồm các mức: <4.0, 4.0-4.5, ..."

    assert extract_visual_count(response) is None


def test_visual_count_extracts_only_the_count() -> None:
    assert extract_visual_count("Có 7 vị trí, không tính bảng chú giải.") == "7"


def test_visual_count_uses_count_prompt_and_skips_ocr() -> None:
    original_call_llm = answer_qa.call_llm
    original_get_transcript = answer_qa.get_transcript
    prompts: list[str] = []

    def fake_call_llm(prompt: str, **kwargs: object) -> str:
        prompts.append(prompt)
        return "Có 7 vị trí trong khu vực bản đồ."

    with tempfile.NamedTemporaryFile(suffix=".jpg") as image:
        answer_qa.call_llm = fake_call_llm
        answer_qa.get_transcript = lambda *args, **kwargs: ""
        hit = {
            "video_id": "V1", "n": 1, "frame_idx": 0, "frame_id": 1,
            "pts_time": 0.0, "score": 0.9, "jpg_path": image.name,
        }
        try:
            result = answer_qa.answer_from_hits(
                "Không tính bảng chú giải, có bao nhiêu vị trí cấp độ 4?",
                [hit],
                top_n=1,
            )
        finally:
            answer_qa.call_llm = original_call_llm
            answer_qa.get_transcript = original_get_transcript

    assert result["answer"] == "7"
    assert len(prompts) == 1
    assert "Ignore the entire legend" in prompts[0]


def test_visual_count_prints_evidence_and_prompt_trace() -> None:
    original_call_llm = answer_qa.call_llm
    original_get_transcript = answer_qa.get_transcript
    output = StringIO()

    def fake_call_llm(prompt: str, **kwargs: object) -> str:
        return "7"

    with tempfile.NamedTemporaryFile(suffix=".jpg") as image:
        answer_qa.call_llm = fake_call_llm
        answer_qa.get_transcript = lambda *args, **kwargs: ""
        hit = {
            "video_id": "V1", "n": 1, "frame_idx": 0, "frame_id": 1,
            "pts_time": 0.0, "score": 0.9, "jpg_path": image.name,
        }
        try:
            with redirect_stdout(output):
                answer_qa.answer_from_hits(
                    "Không tính bảng chú giải, có bao nhiêu vị trí cấp độ 4?",
                    [hit],
                    top_n=1,
                )
        finally:
            answer_qa.call_llm = original_call_llm
            answer_qa.get_transcript = original_get_transcript

    trace = output.getvalue()
    assert "[qa] Evidence" in trace
    assert "Vintern caption:" in trace
    assert "[qa] Prompt" in trace



if __name__ == "__main__":
    test_map_marker_question_is_visual_counting()
    test_visual_count_rejects_earthquake_scale_explanation()
    test_visual_count_extracts_only_the_count()
    test_visual_count_uses_count_prompt_and_skips_ocr()
    test_visual_count_prints_evidence_and_prompt_trace()
    print("Q&A answer contract tests: PASS")