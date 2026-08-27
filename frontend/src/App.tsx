import { useState } from "react";
import KisScreen from "./screens/KisScreen";
import QaScreen from "./screens/QaScreen";
import TrakeScreen from "./screens/TrakeScreen";
import QueueScreen from "./screens/QueueScreen";

type Mode = "chat" | "kis" | "qa" | "trake" | "queue";

const MODES: { id: Mode; label: string; disabled?: boolean }[] = [
  { id: "chat", label: "Chat", disabled: true },
  { id: "kis", label: "KIS" },
  { id: "qa", label: "Q&A" },
  { id: "trake", label: "TRAKE" },
  { id: "queue", label: "Hàng đợi" },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("kis");

  return (
    <div className="app-shell">
      <nav className="rail">
        <div className="rail-logo">AIC</div>
        {MODES.map((m) => (
          <button
            key={m.id}
            className={`rail-item ${mode === m.id ? "active" : ""}`}
            disabled={m.disabled}
            title={m.disabled ? "Sắp có ở Phase 2/3 (AI Graph)" : undefined}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </nav>
      <main className="main-panel">
        {/* Tat ca man hinh luon mounted, chi an/hien bang CSS -> query/ket qua/shortlist KHONG mat
            khi chuyen tab (truoc day dung `mode === x && <Screen/>` nen React unmount, xoa het state). */}
        <div style={{ display: mode === "kis" ? "block" : "none" }}><KisScreen /></div>
        <div style={{ display: mode === "qa" ? "block" : "none" }}><QaScreen /></div>
        <div style={{ display: mode === "trake" ? "block" : "none" }}><TrakeScreen /></div>
        <div style={{ display: mode === "queue" ? "block" : "none" }}><QueueScreen active={mode === "queue"} /></div>
      </main>
    </div>
  );
}
