import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { NeighborFrame } from "../api/client";
import Thumb from "./Thumb";
import VideoVerifier from "./VideoVerifier";
import type { VideoVerifierHandle } from "./VideoVerifier";

// Man soi video chi tiet cho 1 MOC su kien TRAKE. Khung giong KeyframeDetail (video + dai luot
// TOAN BO keyframe cua video + nhay nhanh qua metadata), them:
//   - hien ro dang chinh Moc may / N, kem frame cua moc truoc & moc sau (de khong tua lech thu tu)
//   - "✓ Cap nhat frame cho Moc nay" -> ghi frame dang tua vao dung moc do roi quay ve danh sach
//
// TRAKE candidate chi co frame_ids (khong co pts_time) -> quy doi giay = (frame_id - 1) / fps, fps
// do cha truyen xuong (cha da goi videoMeta cho moi video ung vien).
export default function TrakeKeyframeDetail({
  videoId,
  fps,
  momentIdx,
  nMoments,
  eventText,
  frameId,
  prevFrameId,
  nextFrameId,
  onBack,
  onCommit,
}: {
  videoId: string;
  fps: number;
  momentIdx: number; // 0-based
  nMoments: number;
  eventText: string; // mo ta khoanh khac (events[momentIdx]) — co the rong
  frameId: number; // frame_id hien tai cua moc nay
  prevFrameId: number | null; // frame_id moc lien truoc (rang buoc khong giam)
  nextFrameId: number | null; // frame_id moc lien sau
  onBack: () => void;
  onCommit: (frameId: number) => void;
}) {
  const startTime = Math.max(0, (frameId - 1) / fps);
  const [frames, setFrames] = useState<NeighborFrame[]>([]);
  const [current, setCurrent] = useState(startTime);
  const [ptsEdit, setPtsEdit] = useState(startTime.toFixed(2));
  const [fidEdit, setFidEdit] = useState(String(frameId));
  const [flash, setFlash] = useState("");
  const vvRef = useRef<VideoVerifierHandle>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrent(startTime);
    setPtsEdit(startTime.toFixed(2));
    setFidEdit(String(frameId));
    setFlash("");
    api.keyframeAll(videoId).then(setFrames).catch(() => setFrames([]));
    // Chay lai khi doi video hoac doi moc — startTime la ham cua (frameId, fps) nen khong can them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, frameId, momentIdx]);

  // Keyframe gan thoi diem video hien tai nhat -> to sang trong dai luot.
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
    seekTo((n - 1) / fps); // frame_idx = frame_id - 1 (BTC dem tu 1); t = frame_idx / fps
    setFlash(`⏩ Nhảy tới frame ${n}`);
  }

  function commit() {
    const frameIdx = Math.max(0, Math.round(current * fps));
    onCommit(frameIdx + 1);
    onBack();
  }

  const nowFrameId = Math.round(current * fps) + 1;
  const outOfOrder =
    (prevFrameId !== null && nowFrameId < prevFrameId) ||
    (nextFrameId !== null && nowFrameId > nextFrameId);

  return (
    <div className="screen detail-screen">
      <div className="detail-header">
        <button className="btn btn-secondary" onClick={onBack}>
          ← Về danh sách
        </button>
        <span className="mono tag">{videoId}</span>
        <span className="mono tag tag-accent-2">
          Mốc {momentIdx + 1} / {nMoments}
          {eventText ? `: ${eventText}` : ""}
        </span>
      </div>

      <div className="detail-body">
        <p className="trake-detail-ctx">
          {prevFrameId !== null ? `Mốc trước: frame ${prevFrameId}` : "Đây là mốc đầu tiên"}
          {"  ·  "}
          {nextFrameId !== null ? `Mốc sau: frame ${nextFrameId}` : "Đây là mốc cuối cùng"}
          {outOfOrder && "  ·  ⚠️ frame hiện tại đang lệch thứ tự"}
        </p>

        <VideoVerifier
          ref={vvRef}
          videoId={videoId}
          startTime={startTime}
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

        <div className="detail-meta">
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

        <button className="btn btn-primary btn-block" onClick={commit}>
          ✓ Cập nhật frame cho Mốc {momentIdx + 1}
        </button>
        {flash && <p className="status-line">{flash}</p>}
      </div>
    </div>
  );
}
