import { useState } from "react";
import { api } from "../api/client";

// Buoc rewrite cau truy van (KIS/QA/TRAKE) — ban gon cua luong Gradio cu: bam "Goi y" de sinh
// toi da 3 phuong an, hien dang chip. Bam 1 chip -> do vao o truy van (van sua tay duoc). KHONG
// tu dong search — nguoi dung van phai bam Search/Run rieng.
type Props = {
  query: string;
  question?: string;
  onPick: (text: string) => void;
  note?: string; // chu thich nho (vd TRAKE: chi ap cho mo ta tong quat)
};

export default function RewriteChips({ query, question, onPick, note }: Props) {
  const [candidates, setCandidates] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
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
      setCandidates(out.candidates);
      if (out.candidates.length === 0) setError("Không sinh được phương án nào.");
    } catch (e) {
      setError(`⚠️ Rewrite thất bại: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rewrite">
      <div className="rewrite-head">
        <button className="btn btn-secondary" onClick={suggest} disabled={loading || !query.trim()}>
          {loading ? "Đang sinh…" : "✨ Gợi ý câu truy vấn"}
        </button>
        {error && <span className="rewrite-note">{error}</span>}
      </div>
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
