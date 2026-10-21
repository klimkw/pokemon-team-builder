import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import RefreshButton from "./RefreshButton";
import { getAlerts, markAlertsRead } from "./api";
import type { AlertPage } from "./api";
import { TypeBadge, TypeBadges } from "./PokemonDetails";

const labels: Record<string, string> = {
  "stats.hp": "HP", "stats.attack": "Attack", "stats.defense": "Defense",
  "stats.special_attack": "Sp. Atk", "stats.special_defense": "Sp. Def", "stats.speed": "Speed",
  name: "Name", types: "Types", sprite_url: "Sprite",
};
const valueText = (value: unknown) => value === null ? "none" : Array.isArray(value) ? value.join(" / ") : String(value);
const titleCase = (value: string) => value.replace(/\b[a-z]/g, letter => letter.toUpperCase());
const dateText = (value: string) => new Date(value).toLocaleString();

export default function Alerts({ membershipKey }: { membershipKey: string }) {
  const [data, setData] = useState<AlertPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [readError, setReadError] = useState("");
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState({ left: 12, top: 80, arrow: 24 });
  useEffect(() => { setOffset(0); }, [membershipKey]);
  useEffect(() => {
    const refresh = () => setRetry(n => n + 1);
    const timer = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    getAlerts(offset, controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setLoading(false); }
    }, failure => {
      if (!controller.signal.aborted) { setError(failure instanceof Error ? failure.message : "Unable to load alerts."); setLoading(false); }
    });
    return () => controller.abort();
  }, [membershipKey, offset, retry]);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = trigger.current!.getBoundingClientRect();
      if (anchor.bottom <= 0 || anchor.top >= window.innerHeight) { setOpen(false); return; }
      const width = Math.min(440, window.innerWidth - 24);
      const left = Math.max(12, Math.min(anchor.right - width, window.innerWidth - width - 12));
      setPosition({ left, top: anchor.bottom + 12, arrow: Math.max(20, Math.min(width - 20, anchor.left + anchor.width / 2 - left)) });
    };
    place();
    dialog.current?.focus({ preventScroll: true });
    const outside = (event: Event) => {
      if (event.target instanceof Node && !dialog.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("focusin", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);
  useEffect(() => {
    if (!open || loading || !data) return;
    const ids = data.items.filter(item => !item.is_read).map(item => item.id);
    if (!ids.length) return;
    let cancelled = false;
    setReadError("");
    markAlertsRead(ids).then(() => {
      if (!cancelled) setData(current => {
        if (!current) return current;
        const marked = current.items.filter(item => ids.includes(item.id) && !item.is_read).length;
        return { ...current, unread_total: Math.max(0, (current.unread_total ?? current.total) - marked),
          items: current.items.map(item => ids.includes(item.id) ? { ...item, is_read: true } : item) };
      });
    }, () => { if (!cancelled) setReadError("Could not mark alerts as read. Refresh to retry."); });
    return () => { cancelled = true; };
  }, [open, loading, data]);
  function close() { setOpen(false); trigger.current?.focus(); }
  const unread = data?.unread_total ?? data?.total ?? 0;
  return <>
    <button ref={trigger} className="icon-button alert-icon" aria-label={`Alerts${unread ? `, ${unread} unread` : ""}`} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? "alerts-popover" : undefined} onClick={() => { setOpen(!open); if (!open) setRetry(n => n + 1); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>
      {unread > 0 && <span className="unread-badge" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
      {error && <span className="alert-error-dot" aria-hidden="true">!</span>}
    </button>
    {open && createPortal(<div ref={dialog} id="alerts-popover" role="dialog" tabIndex={-1} className="alerts-popover" aria-labelledby="alerts-title"
      style={{ left: position.left, top: position.top, "--popover-arrow": `${position.arrow}px`, "--popover-top": `${position.top}px` } as CSSProperties}>
      <section className="alerts-content" aria-busy={loading}>
        <div className="panel-heading"><h2 id="alerts-title">Recent changes{data ? ` (${data.total})` : ""}</h2><div className="panel-header-actions"><RefreshButton label="Refresh alerts" loading={loading} onRefresh={() => { setOffset(0); setRetry(n => n + 1); }} /><button className="icon-button" aria-label="Close alerts" onClick={close}>×</button></div></div>
        {readError && <p className="message error" role="alert">{readError}</p>}
        {loading ? <p role="status">Loading alerts…</p> : error ? <p className="message error" role="alert">{error}</p> : data && <>
          {data.latest_scan && data.latest_scan.status !== "succeeded" && <p className="message">Latest scan: {data.latest_scan.status}. Data may be incomplete.</p>}
          {!data.latest_scan && <p className="save-hint">Not scanned yet.</p>}
          {data.total === 0 ? <p className="alerts-empty">No recent changes affecting your saved teams.</p> : <ul className="change-list">
            {data.items.map((alert, index) => <li className="alert-timeline-event" key={alert.id}>
              {(index === 0 || new Date(alert.detected_at).toDateString() !== new Date(data.items[index - 1].detected_at).toDateString()) &&
                <h3 className="alert-date">{new Date(alert.detected_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</h3>}
              <article className="alert-event-card">
              {alert.is_manual_demo && <p className="demo-label">Demo change · applied manually through the scanner</p>}
              <h3>{titleCase(alert.entity_kind === "type" ? `${alert.entity_name} type matchups changed` : `${alert.entity_name} changed`)}</h3>
              <time className="save-hint" dateTime={alert.detected_at}>{dateText(alert.detected_at)}</time>
              <ul className="change-values">{Object.entries(alert.changes).map(([field, change]) => {
                const matchup = field.startsWith("damage_to.");
                const label = matchup ? `${titleCase(alert.entity_name)} attacks against ${titleCase(field.slice(10))}` : labels[field] ?? titleCase(field);
                const before = `${valueText(change.before)}${matchup ? "×" : ""}`;
                const after = `${valueText(change.after)}${matchup ? "×" : ""}`;
                return <li className="change-chip" key={field} aria-label={`${label}: ${before} → ${after}`}>
                  <span className="change-chip-label">{matchup ? <><TypeBadge type={alert.entity_name} /><span aria-hidden="true">→</span><TypeBadge type={field.slice(10)} /></> : label}</span>
                  <span className="change-chip-values"><span className="change-before">{before}</span><span className="change-arrow" aria-hidden="true">→</span><strong className="change-after">{after}</strong></span>
                </li>;
              })}</ul>
              {Object.entries(alert.history ?? {}).filter(([, entries]) => entries.length > 1).map(([field, entries]) =>
                <details className="field-history" key={field}>
                  <summary>View history · {labels[field] ?? titleCase(field.replace("damage_to.", "Against "))} ({entries.length})</summary>
                  <ol aria-label={`${labels[field] ?? field} history`}>
                    {entries.map(entry => <li key={entry.id}>
                      <time dateTime={entry.detected_at}>{dateText(entry.detected_at)}</time>
                      <span>{valueText(entry.before)} → <strong>{valueText(entry.after)}</strong>{field.startsWith("damage_to.") ? "×" : ""}</span>
                    </li>)}
                  </ol>
                  <p className="save-hint">Detected changes · last {data.window_days} days · newest first</p>
                </details>)}
              <ul className="alert-affected" aria-label="Affected Pokémon">{alert.affected.map(pokemon => <li className="affected-pokemon" key={pokemon.id}>
                <div className="affected-heading"><h4>{titleCase(pokemon.name)}</h4><TypeBadges types={pokemon.types} /></div>
                {alert.entity_kind === "type" && <p className="affected-reason">{[
                  pokemon.reasons.includes("attacking_type") ? "Attacking matchup changed" : "",
                  pokemon.reasons.includes("defending_type") ? "Defensive matchup changed" : "",
                ].filter(Boolean).join(" · ")}</p>}
                <ul className="affected-teams">{pokemon.teams.map(team => <li key={team.id}>{team.name} · slots {team.positions.map(p => p + 1).join(", ")}</li>)}</ul>
              </li>)}</ul>
              </article>
            </li>)}
          </ul>}
          {data.total > 10 && <nav className="catalog-pagination" aria-label="Alert pages">
            <button className="quiet-button" disabled={!offset} onClick={() => setOffset(n => Math.max(0, n - 10))}>Newer alerts</button>
            <span>{data.items.length ? offset + 1 : 0}–{Math.min(offset + data.items.length, data.total)} of {data.total}</span>
            <button className="quiet-button" disabled={offset + data.limit >= data.total} onClick={() => setOffset(n => n + 10)}>Older alerts</button>
          </nav>}
        </>}
      </section>
    </div>, document.body)}
  </>;
}
