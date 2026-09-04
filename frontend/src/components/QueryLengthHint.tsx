type Props = {
  text: string;
  maxWords?: number; // Mặc định 40 từ (~64 tokens SigLIP)
};

export default function QueryLengthHint({ text, maxWords = 40 }: Props) {
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const isOver = words > maxWords;

  if (words === 0) {
    return (
      <div className="query-hint">
        <span className="query-hint-icon">💡</span>
        <span>
          Mẹo: Model SigLIP chỉ đọc tối đa <b>64 tokens (~40–50 từ)</b>. Hãy đặt vật thể neo &amp; hành động chính ở đầu câu.
        </span>
      </div>
    );
  }

  if (isOver) {
    return (
      <div className="query-hint query-hint-warning">
        <span className="query-hint-icon">⚠️</span>
        <span>
          <b>{words} từ</b> (vượt ngưỡng {maxWords} từ / 64 tokens): Model sẽ <b>cắt bớt phần đuôi</b>. Hãy dồn các chi tiết quan trọng nhất lên đầu câu!
        </span>
      </div>
    );
  }

  return (
    <div className="query-hint">
      <span className="query-hint-count">{words}/{maxWords} từ</span>
      <span>· Model nhận tối đa 64 tokens (~40–50 từ), ưu tiên vật thể ở đầu câu.</span>
    </div>
  );
}
