import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { QaHit, NeighborFrame } from "../api/client";
import Thumb from "./Thumb";
import VideoVerifier from "./VideoVerifier";
import type { VideoVerifierHandle } from "./VideoVerifier";

// Man soi video chi tiet cho Q&A. Khung giong KeyframeDetail (video + dai luot TOAN BO keyframe cua
// video + nhay nhanh qua metadata) nhung them 3 hanh dong rieng cua Q&A:
//   - o nhap dap an rieng cho frame dang soi
//   - "⭐ Dat lam Rank #1"  -> dua frame nay len dau danh sach nop
//   - "🌐 Ap dung dap an nay cho toan bo ket qua"  -> dong bo dap an cho ca 100 dong
//   - "✓ Cap nhat frame hien tai"  -> ghi de frame/thoi gian dang tua vao dung card
export default function QaKeyframeDetail({
  hit,
  rank,
  answer,
  onBack,
  onUpdateFrame,
  onSetRank1,
  onApplyAnswerToAll,
}: {
  hit: QaHit;
  rank: number;
  answer: string; // dap an chung hien tai — seed cho o dap an frame
  onBack: () => void;
  onUpdateFrame: (h: QaHit) => void; // gom ca frame moi (vi tri/thoi gian) + dap an rieng cua card
  onSetRank1: () => void;
  onApplyAnswerToAll: (answer: string) => void;
}) {
  const [frames, setFrames] = useState<NeighborFrame[]>([]);
  const [fps, setFps] = useState(25);
  const [current, setCurrent] = useState(hit.pts_time);
  const [ptsEdit, setPtsEdit] = useState(hit.pts_time.toFixed(2));
  const [fidEdit, setFidEdit] = useState(String(hit.frame_id));
  const [frameAnswer, setFrameAnswer] = useState(hit.answer || answer);
  const [flash, setFlash] = useState("");
  const vvRef = useRef<VideoVerifierHandle>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrent(hit.pts_time);
    setPtsEdit(hit.pts_time.toFixed(2));
    setFidEdit(String(hit.frame_id));
    setFrameAnswer(hit.answer || answer);
    setFlash("");
    api.keyframeAll(hit.video_id).then(setFrames).catch(() => setFrames([]));
    api
      .videoMeta(hit.video_id)
      .then((m) => setFps(m.fps > 0 ? m.fps : 25))
      .catch(() => setFps(25));
    // Chi seed lai o dap an frame khi DOI frame — khong khi doi dap an chung (`answer`), de khong
    // ghi de doan user dang go dang do o man soi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit.video_id, hit.frame_id, hit.pts_time]);

  const currentStripIdx = useMemo(() => {
    let best = -1;
    let bestD = Infinity;
    frames.forEach((f, i) => {
      const d = Math.abs(f.pts_time - current);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best;
  }, [frames, current]);

  useEffect(() => {
    if (currentStripIdx < 0) return;
    const el = stripRef.current?.children[currentStripIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [currentStripIdx]);

  function seekTo(t: number) {
    vvRef.current?.seek(t);
    setCurrent(t);
  }

  function jumpPts() {
    const t = Number(ptsEdit.trim());
    if (!Number.isFinite(t) || t < 0) {
      setFlash("⚠️ Số giây không hợp lệ.");
      return;
    }
    seekTo(t);
    setFlash(`⏩ Nhảy tới ${t.toFixed(2)}s`);
  }

  function jumpFid() {
    const n = Number(fidEdit.trim());
    if (!Number.isInteger(n) || n <= 0) {
      setFlash("⚠️ frame_id phải là số nguyên dương.");
      return;
    }
    seekTo((n - 1) / fps); // frame_idx = frame_id - 1; t = frame_idx / fps
    setFlash(`⏩ Nhảy tới frame ${n}`);
  }

  function commitCurrent() {
    const frameIdx = Math.max(0, Math.round(current * fps));
    // Ghi de CA frame (vi tri/thoi gian) LAN dap an rieng cua card nay.
    onUpdateFrame({
      ...hit,
      frame_idx: frameIdx,
      frame_id: frameIdx + 1,
      pts_time: current,
      answer: frameAnswer,
    });
    setFlash(
      `✓ Đã cập nhật vị trí #${rank}: frame ${frameIdx + 1} · ${current.toFixed(2)}s · đáp án "${frameAnswer}"`
    );
  }

  const nowFrameId = Math.round(current * fps) + 1;

  const metaRows: [string, ReactNode][] = [
    ["video_id", <span key="v" className="mono">{hit.video_id}</span>],
    ["vị trí trong danh sách", <span key="r" className="mono">#{rank}</span>],
    ["score", <span key="s" className="mono">{hit.score.toFixed(4)}</span>],
    [
      "frame gốc (khi tìm)",
      <span key="f" className="mono">
        {hit.frame_id} · {hit.pts_time.toFixed(2)}s
      </span>,
    ],
  ];

  return (
    <div className="screen detail-screen">
      <div className="detail-header">
        <button className="btn btn-secondary" onClick={onBack}>
          ← Về kết quả
        </button>
        <span className="mono tag">
          {hit.video_id} · vị trí #{rank}
        </span>
        <span className="mono tag tag-accent-2">score {hit.score.toFixed(4)}</span>
      </div>

      <div className="detail-body">
        <VideoVerifier
          ref={vvRef}
          videoId={hit.video_id}
          startTime={hit.pts_time}
          onTimeChange={setCurrent}
        />

        <div className="kf-strip" ref={stripRef}>
          {frames.map((f, i) => (
            <button
              key={f.frame_id}
              className={`kf-strip-item ${i === currentStripIdx ? "current" : ""}`}
              onClick={() => seekTo(f.pts_time)}
              title={`frame ${f.frame_id} · ${f.pts_time.toFixed(1)}s`}
            >
              <Thumb videoId={f.video_id} frameIdx={f.frame_idx} label={`${f.frame_id}`} />
            </button>
          ))}
          {frames.length === 0 && <span className="text-muted">Đang tải danh sách keyframe…</span>}
        </div>

        <div className="field">
          <label>Đáp án cho frame đang soi</label>
          <div className="qa-frame-answer">
            <input
              className="input answer-input"
              value={frameAnswer}
              onChange={(e) => setFrameAnswer(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={() => {
                setFrameAnswer(answer);
                setFlash("↺ Đã lấy lại đáp án chung vào ô này.");
              }}
              disabled={frameAnswer === answer}
              title="Ghi đè ô này bằng đáp án chung hiện tại"
            >
              ↺ Đáp án chung
            </button>
          </div>
        </div>

        <div className="detail-meta">
          {metaRows.map(([k, v]) => (
            <div key={k}>
              <span>{k}</span>
              {v}
            </div>
          ))}

          <div className="meta-jump">
            <span>pts_time (giây) → nhảy</span>
            <input
              className="input frame-input"
              value={ptsEdit}
              onChange={(e) => setPtsEdit(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && jumpPts()}
            />
            <button className="btn btn-secondary" onClick={jumpPts}>
              ⏩
            </button>
          </div>
          <div className="meta-jump">
            <span>frame_id → nhảy</span>
            <input
              className="input frame-input"
              value={fidEdit}
              onChange={(e) => setFidEdit(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && jumpFid()}
            />
            <button className="btn btn-secondary" onClick={jumpFid}>
              ⏩
            </button>
          </div>
          <div>
            <span>đang xem</span>
            <span className="mono">
              frame ≈ {nowFrameId} · {current.toFixed(2)}s
            </span>
          </div>
        </div>

        <div className="qa-detail-actions">
          <button
            className="btn btn-secondary"
            onClick={() => {
              onSetRank1();
              setFlash("⭐ Đã đưa frame này lên Rank #1.");
            }}
          >
            ⭐ Đặt làm Rank #1
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => {
              onApplyAnswerToAll(frameAnswer);
              setFlash("🌐 Đã áp đáp án này cho toàn bộ kết quả.");
            }}
          >
            🌐 Áp đáp án này cho toàn bộ
          </button>
          <button className="btn btn-primary" onClick={commitCurrent}>
            ✓ Cập nhật frame &amp; đáp án
          </button>
        </div>
        {flash && <p className="status-line">{flash}</p>}
      </div>
    </div>
  );
}
