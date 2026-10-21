import { useEffect, useState } from "react";

export default function RefreshButton({ label, loading, onRefresh }: {
  label: string;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [turning, setTurning] = useState(false);
  useEffect(() => {
    if (!turning) return;
    // Keep one full turn visible even when the request resolves immediately.
    const timer = window.setTimeout(() => setTurning(false), 650);
    return () => window.clearTimeout(timer);
  }, [turning]);
  return <button type="button" className={`icon-button refresh-button${loading || turning ? " is-refreshing" : ""}`}
    aria-label={label} title={label} aria-busy={loading} disabled={loading || turning}
    onClick={() => { setTurning(true); onRefresh(); }}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M6.1 6.1A8 8 0 0 1 19.6 10M4.4 14a8 8 0 0 0 13.5 3.9" /></svg>
  </button>;
}
