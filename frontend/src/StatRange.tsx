import type { CSSProperties } from "react";

export default function StatRange({ label, maximum, low, high, onChange }: {
  label: string; maximum: number; low: number; high: number;
  onChange: (low: number, high: number) => void;
}) {
  return <div className="stat-slider">
    <div className="range-heading"><span>{label}</span><output aria-live="polite">{low}–{high}</output></div>
    <div className="dual-range" style={{ "--range-start": `${low / maximum * 100}%`, "--range-end": `${high / maximum * 100}%` } as CSSProperties}>
      <div className="range-track" aria-hidden="true" />
      <input type="range" min={0} max={maximum} step={1} value={low} aria-label={`${label} minimum`}
        aria-valuemax={high} className="range-low" style={{ zIndex: low === maximum ? 3 : 1 }}
        onChange={event => onChange(Math.min(Number(event.target.value), high), high)} />
      <input type="range" min={0} max={maximum} step={1} value={high} aria-label={`${label} maximum`}
        aria-valuemin={low} className="range-high"
        onChange={event => onChange(low, Math.max(Number(event.target.value), low))} />
    </div>
  </div>;
}
