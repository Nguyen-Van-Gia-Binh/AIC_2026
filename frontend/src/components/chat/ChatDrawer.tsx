import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import type { NeighborFrame } from "../../api/client";
import type { InspectState } from "../../types/chat";
import Thumb from "../Thumb";
import VideoVerifier from "../VideoVerifier";
import type { VideoVerifierHandle } from "../VideoVerifier";

// Drawer truot phai — trinh kiem chung video dung chung cho KIS/Q&A/TRAKE. Chat timeline van thay
// & cuon duoc (drawer la position:fixed doc canh phai). Nut chinh: ghi frame dang tua vao dung
// vi tri card/moc (onCommitFrame) va chot ket qua vao hang doi (onSubmitQueue).
export default function ChatDrawer({
  inspect,
  onClose,
  onCommitFrame,
  onSubmitQueue,
}: {
  inspect: InspectState | null;
  onClose: () => void;
  onCommitFrame: (frameId: number, frameIdx: number, ptsTime: number) => void;
  onSubmitQueue: () => void;
}) {
  const [frames, setFrames] = useState<NeighborFrame[]>([]);
  const [fps, setFps] = useState(25);
  const [current, setCurrent] = useState(0);
  const [flash, setFlash] = useState("");
  const vvRef = useRef<VideoVerifierHandle>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  const videoId = inspect?.videoId ?? "";
  const startTime = inspect?.ptsTime ?? 0;
  const rankLabel =
    inspect?.taskType === "trake"
      ? `Mốc ${(inspect?.resultIndex ?? 0) + 1}`
      : `#${(inspect?.resultIndex ?? 0) + 1}`;

  useEffect(() => {
    if (!inspect) return;
    setCurrent(startTime);
    setFlash("");
    api.keyframeAll(inspect.videoId).then(setFrames).catch(() => setFrames([]));
    api
      .videoMeta(inspect.videoId)
      .then((m) => setFps(m.fps > 0 ? m.fps : 25))
      .catch(() => setFps(25));
    // Chay lai khi doi video / frame / vi tri card dang soi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inspect?.videoId, inspect?.frameId, inspect?.resultIndex]);

  // Esc de dong.
  useEffect(() => {
    if (!inspect) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inspect, onClose]);

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

  function commit() {
    const frameIdx = Math.max(0, Math.round(current * fps));
    onCommitFrame(frameIdx + 1, frameIdx, current);
    setFlash(`✓ Đã cập nhật ${rankLabel}: frame ${frameIdx + 1} · ${current.toFixed(2)}s`);
  }

  const nowFrameId = Math.round(current * fps) + 1;

  return (
    <>
      <div
        className={`chat-drawer-overlay ${inspect ? "open" : ""}`}
        onClick={onClose}
        aria-hidden={!inspect}
      />
      <aside className={`chat-drawer ${inspect ? "open" : ""}`} aria-hidden={!inspect}>
        {inspect && (
          <div className="chat-drawer-inner">
            <div className="chat-drawer-head">
              <button className="btn btn-secondary" onClick={onClose}>
                ✕ Đóng
              </button>
              <span className="mono tag">{videoId}</span>
              <span className="mono tag tag-accent-2">Đang soi {rankLabel}</span>
            </div>

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
              {frames.length === 0 && (
                <span className="text-muted">Đang tải danh sách keyframe…</span>
              )}
            </div>

            <p className="chat-drawer-readout mono">
              đang xem: frame ≈ {nowFrameId} · {current.toFixed(2)}s · fps {fps}
            </p>

            <div className="chat-drawer-actions">
              <button className="btn btn-primary btn-block" onClick={commit}>
                📌 Cập nhật Frame {nowFrameId} vào vị trí {rankLabel}
              </button>
              <button className="btn btn-secondary btn-block" onClick={onSubmitQueue}>
                📥 Chốt vào Hàng đợi nộp
              </button>
            </div>
            {flash && <p className="status-line">{flash}</p>}
          </div>
        )}
      </aside>
    </>
  );
}
