// Header phien Chat: Query ID (dung khi chot vao hang doi), badge model/quota (tinh o GD1),
// nut Reset phien (xoa lich su hien thi).
export default function ChatHeader({
  queryId,
  onQueryIdChange,
  onReset,
}: {
  queryId: string;
  onQueryIdChange: (v: string) => void;
  onReset: () => void;
}) {
  return (
    <div className="chat-header">
      <label className="chat-header-qid">
        <span className="text-muted">Query ID</span>
        <input
          className="input"
          value={queryId}
          onChange={(e) => onQueryIdChange(e.target.value)}
          placeholder="chat-query-001"
        />
      </label>
      <span className="chat-header-model mono tag" title="Giai doan 1: du lieu mock tinh">
        Mock · Gemini 2.5 Flash · quota —
      </span>
      <button className="btn btn-secondary" onClick={onReset}>
        ↺ Reset phiên
      </button>
    </div>
  );
}
