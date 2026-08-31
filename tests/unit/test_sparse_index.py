"""Test cho scripts/agent/tools/sparse_index.py — chuyển từ `--self-test` của CLI, giữ nguyên assert.

Chạy trên index GIẢ dựng trong bộ nhớ, không đọc cache thật, không đụng data/.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.agent.tools import sparse_index
from scripts.agent.tools.sparse_index import search_sparse, tokenize


def test_tokenize_lowercase_bo_stopword_va_token_1_ky_tu() -> None:
    assert tokenize("A red Double-Decker BUS") == ["red", "double", "decker", "bus"]
    assert tokenize("") == []
    assert tokenize("a of the in") == []


def test_bm25_uu_tien_document_chua_term_hiem(monkeypatch) -> None:
    sp = pytest.importorskip("scipy.sparse", reason="sparse_index cần scipy để dựng ma trận tf")

    df_t = np.array([1, 3], dtype=np.float32)
    monkeypatch.setattr(sparse_index, "_VOCAB", {"bus": 0, "person": 1})
    monkeypatch.setattr(sparse_index, "_MATRIX_CSC",
                        sp.csc_matrix(np.array([[1, 1], [0, 1], [0, 1]], dtype=np.float32)))
    monkeypatch.setattr(sparse_index, "_DOC_LEN", np.array([2, 1, 1], dtype=np.float32))
    monkeypatch.setattr(sparse_index, "_AVG_DL", 4.0 / 3.0)
    monkeypatch.setattr(sparse_index, "_IDF",
                        np.log(1.0 + (3 - df_t + 0.5) / (df_t + 0.5)).astype(np.float32))
    monkeypatch.setattr(sparse_index, "_DOC_VIDEO", np.array(["V1", "V2", "V3"]))
    monkeypatch.setattr(sparse_index, "_DOC_N", np.array([1, 2, 3], dtype=np.int32))

    out = search_sparse("bus person", top_k=3)
    assert out[0]["video_id"] == "V1", f"Doc chua term hiem 'bus' phai dung dau: {out}"
    assert len(out) == 3, f"Ca 3 doc deu chua 'person' -> phai co diem: {out}"
    assert search_sparse("giraffe") == [], "Term ngoai vocab -> rong"
