"""
_smoke_test.py — Kiểm tra toàn bộ backend API một lượt: KIS -> QA -> TRAKE -> queue -> export -> validate.
Không phải pytest (test tất định đã nằm ở tests/unit/) — script độc lập, chạy tay, gọi LLM thật.

Usage:
    .venv\\Scripts\\python.exe scripts\\api\\_smoke_test.py

Cần OPENROUTER_API_KEY thật (gọi LLM thật qua rewrite/qa/trake) và data/ đã giải nén sẵn.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient
from scripts.api.main import app

SESSION = "smoke-test-session"


def main() -> None:
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        print("[smoke] health OK")

        r = c.post("/api/kis/search", json={"query": "a red car parked on the street", "top_k": 5})
        assert r.status_code == 200, r.text
        kis_hits = r.json()["hits"]
        assert len(kis_hits) == 5
        print(f"[smoke] kis/search OK ({len(kis_hits)} hits)")

        # Ảnh keyframe thật: 200 + image/jpeg cho hit có ảnh; 404 cho keyframe không tồn tại.
        h0 = kis_hits[0]
        r = c.get(f"/api/images/{h0['video_id']}/{h0['frame_idx']}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg", r.text
        assert len(r.content) > 1000, "file ảnh quá nhỏ, có vẻ không phải .jpg thật"
        print(f"[smoke] images OK ({h0['video_id']} frame_idx={h0['frame_idx']}, {len(r.content)} bytes)")
        r = c.get("/api/images/L99_V999/123456")
        assert r.status_code == 404
        print("[smoke] images 404 (keyframe không tồn tại) OK")

        # Video gốc: meta có fps > 0; GET kèm header Range trả về 206 + đúng số byte yêu cầu.
        r = c.get(f"/api/videos/{h0['video_id']}/meta")
        assert r.status_code == 200, r.text
        vmeta = r.json()
        assert vmeta["fps"] > 0, vmeta
        print(f"[smoke] videos/meta OK (fps={vmeta['fps']}, duration={vmeta['duration']})")
        r = c.get(f"/api/videos/{h0['video_id']}", headers={"Range": "bytes=0-1023"})
        assert r.status_code == 206, f"mong đợi 206 Partial Content, nhận {r.status_code}"
        assert len(r.content) == 1024, f"mong đợi 1024 byte, nhận {len(r.content)}"
        print(f"[smoke] videos Range OK (206, {len(r.content)} bytes)")
        r = c.get("/api/videos/L99_V999")
        assert r.status_code == 404
        print("[smoke] videos 404 (video không tồn tại) OK")

        # Dải lướt toàn bộ keyframe của video (màn chi tiết KIS): >= số keyframe của riêng video đó,
        # có chứa đúng frame_idx của hit đang xét.
        r = c.get(f"/api/keyframes/{h0['video_id']}/all")
        assert r.status_code == 200, r.text
        all_kf = r.json()
        assert len(all_kf) >= 1 and any(f["frame_idx"] == h0["frame_idx"] for f in all_kf), (
            f"dai keyframe thieu frame_idx={h0['frame_idx']}"
        )
        print(f"[smoke] keyframes/all OK ({len(all_kf)} keyframe cho {h0['video_id']})")
        r = c.get("/api/keyframes/L99_V999/all")
        assert r.status_code == 404
        print("[smoke] keyframes/all 404 (video không tồn tại) OK")

        r = c.post("/api/queue/" + SESSION + "/add", json={
            "query_id": "smoke-kis", "query_type": "kis",
            "rows": [{"video_id": h["video_id"], "frame_id": h["frame_id"]} for h in kis_hits[:3]],
        })
        assert r.status_code == 200, r.text
        print("[smoke] queue add (kis) OK")

        r = c.post("/api/qa/run", json={
            "query": "Một người đang phát biểu trước đám đông, mặc áo trắng",
            "question": "What color is the speaker's shirt?", "top_k": 10,
        })
        assert r.status_code == 200, r.text
        qa_body = r.json()
        print(f"[smoke] qa/run OK (answer={qa_body['answer']!r}, confidence={qa_body['confidence']:.2f})")

        r = c.post("/api/queue/" + SESSION + "/add", json={
            "query_id": "smoke-qa", "query_type": "qa", "answer": qa_body["answer"],
            "rows": [{"video_id": h["video_id"], "frame_id": h["frame_id"], "answer": qa_body["answer"]}
                     for h in qa_body["hits"][:3]],
        })
        assert r.status_code == 200, r.text
        print("[smoke] queue add (qa) OK")

        events = [
            "athlete running toward the bar during approach run",
            "athlete jumping over the high bar at peak",
            "athlete landing on the mat after clearing",
        ]
        r = c.post("/api/trake/run", json={
            "query": "An athlete performing a high jump in a stadium competition",
            "events": events, "top_k_video": 3,
        })
        assert r.status_code == 200, r.text
        trake_body = r.json()
        print(f"[smoke] trake/run OK ({len(trake_body['candidates'])} candidates)")

        if trake_body["candidates"]:
            best = trake_body["candidates"][0]
            r = c.post("/api/queue/" + SESSION + "/add", json={
                "query_id": "smoke-trake", "query_type": "trake",
                "rows": [{"video_id": best["video_id"], "frame_ids": best["frame_ids"]}],
            })
            assert r.status_code == 200, r.text
            print("[smoke] queue add (trake) OK")

        r = c.get("/api/queue/" + SESSION)
        assert r.status_code == 200 and len(r.json()) >= 2, r.text
        print(f"[smoke] queue GET OK ({len(r.json())} queries queued)")

        r = c.post("/api/export/" + SESSION)
        assert r.status_code == 200, r.text
        export_body = r.json()
        print(f"[smoke] export OK: {export_body['zip_path']} (valid={export_body['valid']}, "
              f"csv_count={export_body['csv_count']})")
        assert export_body["valid"], export_body["errors"]

        r = c.delete("/api/queue/" + SESSION)
        assert r.status_code == 200 and r.json() == []
        print("[smoke] queue clear OK")

    print("\n[smoke] TẤT CẢ BƯỚC PASS")


if __name__ == "__main__":
    main()
