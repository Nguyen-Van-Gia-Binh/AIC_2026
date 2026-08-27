import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "../api/client";

// Trinh phat video kiem chung 1 keyframe (KIS): nap video goc, tua thang toi timestamp cua
// keyframe, kem phim tat de soi nhanh (tua tung frame, +/-5s, doi toc do, ve dung keyframe).
//
// Luu y: <video> HTML5 tua KHONG chinh xac tuyet doi tung frame o ranh gioi — "1 frame" o day
// la 1/fps giay. Du dung de mat thuong kiem tra hit dung/sai.

export type VideoVerifierHandle = { seek: (t: number) => void };

type Props = {
  videoId: string;
  startTime: number; // pts_time cua keyframe (giay)
  onTimeChange?: (t: number) => void; // bao cho cha biet frame hien tai (de "them vao danh sach")
};

const RATES = [0.25, 0.5, 1, 1.5, 2, 4];

const VideoVerifier = forwardRef<VideoVerifierHandle, Props>(function VideoVerifier(
  { videoId, startTime, onTimeChange },
  ref
) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [fps, setFps] = useState(25);
  const [duration, setDuration] = useState(0);
  const [current, setCurrent] = useState(startTime);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);

  // fps tu backend (hang so trong 1 video) — fallback 25 neu loi.
  useEffect(() => {
    let alive = true;
    api
      .videoMeta(videoId)
      .then((m) => alive && setFps(m.fps > 0 ? m.fps : 25))
      .catch(() => alive && setFps(25));
    return () => {
      alive = false;
    };
  }, [videoId]);

  // Doi video/keyframe -> nap lai va tua ve dau keyframe.
  useEffect(() => {
    setCurrent(startTime);
  }, [videoId, startTime]);

  function applyTime(t: number) {
    const v = videoRef.current;
    if (!v) return;
    const clamped = Math.max(0, Math.min(t, duration || t));
    v.currentTime = clamped;
    setCurrent(clamped);
    onTimeChange?.(clamped);
  }

  function seekBy(delta: number) {
    applyTime((videoRef.current?.currentTime ?? current) + delta);
  }

  function stepFrame(dir: number) {
    videoRef.current?.pause();
    seekBy((dir * 1) / fps);
  }

  function togglePlay() {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play();
    else v.pause();
  }

  function changeRate(next: number) {
    const clamped = Math.max(0.25, Math.min(4, next));
    setRate(clamped);
    if (videoRef.current) videoRef.current.playbackRate = clamped;
  }

  function bumpRate(dir: number) {
    const idx = RATES.indexOf(rate);
    const nextIdx = idx < 0 ? RATES.indexOf(1) : Math.max(0, Math.min(RATES.length - 1, idx + dir));
    changeRate(RATES[nextIdx]);
  }

  useImperativeHandle(ref, () => ({ seek: applyTime }));

  function onKey(e: React.KeyboardEvent) {
    switch (e.key) {
      case " ":
      case "k":
      case "K":
        e.preventDefault();
        togglePlay();
        break;
      case "ArrowRight":
        e.preventDefault();
        if (e.shiftKey) seekBy(5);
        else stepFrame(1);
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (e.shiftKey) seekBy(-5);
        else stepFrame(-1);
        break;
      case ".":
        e.preventDefault();
        if (e.shiftKey) bumpRate(1);
        else stepFrame(1);
        break;
      case ",":
        e.preventDefault();
        if (e.shiftKey) bumpRate(-1);
        else stepFrame(-1);
        break;
      case "l":
      case "L":
        e.preventDefault();
        seekBy(5);
        break;
      case "j":
      case "J":
        e.preventDefault();
        seekBy(-5);
        break;
      case "1":
        changeRate(1);
        break;
      case "2":
        changeRate(2);
        break;
      case "0":
      case "Home":
        e.preventDefault();
        applyTime(startTime);
        break;
      case "f":
      case "F":
        e.preventDefault();
        if (document.fullscreenElement) document.exitFullscreen();
        else stageRef.current?.requestFullscreen?.();
        break;
    }
  }

  const frameNo = Math.round(current * fps);

  return (
    <div className="video-verifier">
      <div className="vv-stage" ref={stageRef} tabIndex={0} onKeyDown={onKey} autoFocus>
        <video
          ref={videoRef}
          src={api.videoUrl(videoId)}
          preload="metadata"
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            setDuration(v.duration || 0);
            v.currentTime = startTime;
            v.playbackRate = rate;
          }}
          onTimeUpdate={(e) => {
            const t = e.currentTarget.currentTime;
            setCurrent(t);
            onTimeChange?.(t);
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          controls={false}
        />
      </div>

      <input
        className="vv-scrub"
        type="range"
        min={0}
        max={duration || Math.max(current, 1)}
        step={1 / fps}
        value={current}
        onChange={(e) => applyTime(Number(e.target.value))}
      />

      <div className="vv-controls">
        <button className="btn btn-secondary" onClick={togglePlay}>
          {playing ? "⏸ Dừng" : "▶ Chạy"}
        </button>
        <button className="btn btn-secondary" onClick={() => stepFrame(-1)}>⏮ −1f</button>
        <button className="btn btn-secondary" onClick={() => stepFrame(1)}>+1f ⏭</button>
        <button className="btn btn-secondary" onClick={() => seekBy(-5)}>−5s</button>
        <button className="btn btn-secondary" onClick={() => seekBy(5)}>+5s</button>
        <select value={rate} onChange={(e) => changeRate(Number(e.target.value))}>
          {RATES.map((r) => (
            <option key={r} value={r}>
              {r}×
            </option>
          ))}
        </select>
        <button className="btn btn-secondary" onClick={() => applyTime(startTime)}>
          ⟲ Về keyframe
        </button>
        <span className="vv-readout">
          t = {current.toFixed(2)}s · frame ≈ {frameNo} · fps {fps}
        </span>
      </div>

      <div className="vv-legend">
        <kbd>Space</kbd>/<kbd>K</kbd> chạy/dừng · <kbd>←</kbd><kbd>→</kbd> hoặc <kbd>,</kbd><kbd>.</kbd> ±1 frame ·{" "}
        <kbd>J</kbd>/<kbd>L</kbd> hoặc <kbd>Shift</kbd>+<kbd>←</kbd>/<kbd>→</kbd> ±5s ·{" "}
        <kbd>Shift</kbd>+<kbd>,</kbd>/<kbd>.</kbd> tốc độ · <kbd>0</kbd> về keyframe · <kbd>F</kbd> toàn màn hình
      </div>
    </div>
  );
});

export default VideoVerifier;
