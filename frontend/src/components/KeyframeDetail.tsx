import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { Hit, NeighborFrame } from "../api/client";
import Thumb from "./Thumb";
import VideoVerifier from "./VideoVerifier";
import type { VideoVerifierHandle } from "./VideoVerifier";

// Man chi tiet 1 keyframe (KIS). Video la chinh (tua toi timestamp keyframe + phim tat), kem:
//  - dai luot TOAN BO keyframe cua video (cuon ngang, bam de tua toi frame do)
//  - bang metadata co o nhap "nhay nhanh": go so giay hoac so frame roi Enter -> video tua toi do
// Nut chinh GHI DE frame dang xem vao dung vi tri card #rank ma nguoi dung mo len (khong tao dong
// moi) — de sua nhanh 1 ket qua sau khi soi video.
export default function KeyframeDetail({
  hit,
  rank,
  onBack,
  onUpdateFrame,
}: {
  hit: Hit;
  rank: number; // vi tri (1-based) cua card trong luoi ket qua
  onBack: () => void;
  onUpdateFrame: (h: Hit) => void;
}) {
  const [frames, setFrames] = useState<NeighborFrame[]>([]);
  const [fps, setFps] = useState(25);
  const [current, setCurrent] = useState(hit.pts_time);
  const [ptsEdit, setPtsEdit] = useState(hit.pts_time.toFixed(2));
  const [fidEdit, setFidEdit] = useState(String(hit.frame_id));
  const [flash, setFlash] = useState("");
  const vvRef = useRef<VideoVerifierHandle>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrent(hit.pts_time);
    setPtsEdit(hit.pts_time.toFixed(2));
    setFidEdit(String(hit.frame_id));
    setFlash("");
    api.keyframeAll(hit.video_id).then(setFrames).catch(() => setFrames([]));
    api
      .videoMeta(hit.video_id)
      .then((m) => setFps(m.fps > 0 ? m.fps : 25))
      .catch(() => setFps(25));
  }, [hit.video_id, hit.frame_id, hit.pts_time]);

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

  // Cuon dai luot sao cho keyframe dang chon vao tam nhin — chi khi doi frame (index roi rac),
  // khong phai moi tick timeupdate.
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
    // frame_idx = frame_id - 1 (BTC dem tu 1); t = frame_idx / fps
    seekTo((n - 1) / fps);
    setFlash(`⏩ Nhảy tới frame ${n}`);
  }

  function commitCurrent() {
    const frameIdx = Math.max(0, Math.round(current * fps));
    onUpdateFrame({
      ...hit,
      frame_idx: frameIdx,
      frame_id: frameIdx + 1,
      pts_time: current,
    });
    setFlash(`✓ Đã cập nhật vị trí #${rank}: frame ${frameIdx + 1} · ${current.toFixed(2)}s`);
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

        <button className="btn btn-primary btn-block" onClick={commitCurrent}>
          Cập nhật vị trí #{rank} với frame hiện tại
        </button>
        {flash && <p className="status-line">{flash}</p>}
      </div>
    </div>
  );
}
