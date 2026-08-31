import { useState } from "react";
import { api } from "../api/client";

// Buoc rewrite cau truy van (KIS/QA/TRAKE) — ban gon cua luong Gradio cu: bam "Goi y" de sinh
// toi da 3 phuong an, hien dang chip. Bam 1 chip -> do vao o truy van (van sua tay duoc). KHONG
// tu dong search — nguoi dung van phai bam Search/Run rieng.
// Them "Dich tho" (khong qua LLM, xem scripts/agent/tools/translate_raw.py) de doi chieu voi ban
// rewrite qua LLM — LLM co the "sang tao" lech y goc ma khong nhan ra. Ca 2 nut deu nho lai cau
// truoc do vao `original` de hien dong "Goc: ..." ben duoi, tranh mat cau goc sau khi bam 1 chip.
type Props = {
  query: string;
  question?: string;
  onPick: (text: string) => void;
  note?: string; // chu thich nho (vd TRAKE: chi ap cho mo ta tong quat)
};

export default function RewriteChips({ query, question, onPick, note }: Props) {
  const [candidates, setCandidates] = useState<string[]>([]);
  const [rawTranslation, setRawTranslation] = useState("");
  const [original, setOriginal] = useState(""); // cau truoc lan bam Goi y/Dich tho gan nhat
  const [loading, setLoading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState("");

  async function suggest() {
    if (!query.trim()) {
      setError("⚠️ Nhập câu truy vấn trước.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const out = await api.rewrite(query, question);
      setOriginal(query);
      setCandidates(out.candidates);
      if (out.candidates.length === 0) setError("Không sinh được phương án nào.");
    } catch (e) {
      setError(`⚠️ Rewrite thất bại: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function translateRaw() {
    if (!query.trim()) {
      setError("⚠️ Nhập câu truy vấn trước.");
      return;
    }
    setTranslating(true);
    setError("");
    try {
      const out = await api.translateRaw(query);
      setOriginal(query);
      setRawTranslation(out.translation);
    } catch (e) {
      setError(`⚠️ Dịch thô thất bại: ${(e as Error).message}`);
    } finally {
      setTranslating(false);
    }
  }

  return (
    <div className="rewrite">
      <div className="rewrite-head">
        <button className="btn btn-secondary" onClick={suggest} disabled={loading || !query.trim()}>
          {loading ? "Đang sinh…" : "✨ Gợi ý câu truy vấn"}
        </button>
        <button
          className="btn btn-secondary"
          onClick={translateRaw}
          disabled={translating || !query.trim()}
          title="Dịch máy thuần, không qua LLM — để đối chiếu với câu gợi ý"
        >
          {translating ? "Đang dịch…" : "🌐 Dịch thô"}
        </button>
        {error && <span className="rewrite-note">{error}</span>}
      </div>

      {original && original !== query && (
        <div className="rewrite-original">
          <span className="rewrite-original-label">Gốc:</span>
          <span className="rewrite-original-text">{original}</span>
          <button className="rewrite-original-close" title="Ẩn dòng này" onClick={() => setOriginal("")}>
            ×
          </button>
        </div>
      )}

      {rawTranslation && (
        <div className="rewrite-chips">
          <button
            className="chip chip-raw"
            onClick={() => onPick(rawTranslation)}
            title="Bấm để dùng câu dịch thô này (không qua LLM)"
          >
            🌐 {rawTranslation}
          </button>
        </div>
      )}

      {candidates.length > 0 && (
        <div className="rewrite-chips">
          {candidates.map((c, i) => (
            <button key={i} className="chip" onClick={() => onPick(c)} title="Bấm để dùng câu này">
              {c}
            </button>
          ))}
        </div>
      )}
      {note && <span className="rewrite-note">{note}</span>}
    </div>
  );
}
