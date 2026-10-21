import { useEffect, useRef, useState } from "react";
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
  const dialog = useRef<HTMLDialogElement>(null);
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
  useEffect(() => {
    if (open && dialog.current && !dialog.current.open) {
      if (typeof dialog.current.showModal === "function") dialog.current.showModal();
      else dialog.current.setAttribute("open", "");
    }
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
  function close() { dialog.current?.close?.(); setOpen(false); }
  const unread = data?.unread_total ?? data?.total ?? 0;
  return <>
    <button className="icon-button alert-icon" aria-label={`Alerts${unread ? `, ${unread} unread` : ""}`} aria-haspopup="dialog" aria-expanded={open} onClick={() => { setOpen(true); setRetry(n => n + 1); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>
      {unread > 0 && <span className="unread-badge" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
      {error && <span className="alert-error-dot" aria-hidden="true">!</span>}
    </button>
    {open && <dialog ref={dialog} className="alerts-drawer" aria-labelledby="alerts-title" onCancel={() => setOpen(false)} onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <section className="alerts-content" aria-busy={loading}>
        <div className="panel-heading"><h2 id="alerts-title">Recent changes{data ? ` (${data.total})` : ""}</h2><button className="icon-button" aria-label="Close alerts" onClick={close}>×</button></div>
        <div className="alerts-meta"><span>Saved teams · {data?.window_days ?? 7} days</span><button className="quiet-button" disabled={loading} onClick={() => { setOffset(0); setRetry(n => n + 1); }}>Refresh alerts</button></div>
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
    </dialog>}
  </>;
}
