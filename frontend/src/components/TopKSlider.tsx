// Thanh keo chon so ket qua lay ve (top-k) — thay cho gia tri hard-code 20 truoc day.
// Khop voi cac slider ben app Gradio cu: KIS 5..100, QA 5..50, TRAKE 3..10.
type Props = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
};

export default function TopKSlider({ label, value, min, max, step, onChange }: Props) {
  return (
    <label className="topk">
      <span>{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="topk-val">{value}</span>
    </label>
  );
}
