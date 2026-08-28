import { useRef, useState } from "react";

// O nhap chat: textarea tu co gian, chip tac vu nhanh (chi chen goi y, khong tu gui),
// Enter = gui / Shift+Enter = xuong dong.
const CHIPS: { label: string; prefix: string }[] = [
  { label: "Tìm cảnh", prefix: "Tìm cảnh " },
  { label: "Hỏi đáp", prefix: "Trong video, " },
  { label: "Chuỗi hành động", prefix: "Chuỗi hành động: " },
];

export default function ChatInput({
  disabled,
  onSend,
}: {
  disabled?: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function grow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function submit() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
    requestAnimationFrame(grow);
  }

  return (
    <div className="chat-input">
      <div className="chat-input-chips">
        {CHIPS.map((c) => (
          <button
            key={c.label}
            className="chip"
            onClick={() => {
              setText((prev) => (prev ? prev : c.prefix));
              ref.current?.focus();
              requestAnimationFrame(grow);
            }}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="chat-input-row">
        <textarea
          ref={ref}
          className="input"
          rows={1}
          placeholder="Mô tả sự kiện, đặt câu hỏi, hoặc nêu chuỗi hành động… (Enter để gửi)"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            grow();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="btn btn-primary" onClick={submit} disabled={disabled || !text.trim()}>
          Gửi
        </button>
      </div>
    </div>
  );
}
