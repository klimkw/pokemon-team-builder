import { useEffect, useState } from "react";
import { getAlerts } from "./api";
import type { AlertPage } from "./api";

const labels: Record<string, string> = {
  "stats.hp": "HP", "stats.attack": "Attack", "stats.defense": "Defense",
  "stats.special_attack": "Special attack", "stats.special_defense": "Special defense",
  "stats.speed": "Speed", name: "Name", types: "Types", sprite_url: "Sprite URL",
};
function valueText(value: unknown) {
  if (value === null) return "none";
  if (Array.isArray(value)) return value.join(" / ");
  return String(value);
}
const dateText = (value: string) => new Date(value).toLocaleString();

export default function Alerts({ membershipKey }: { membershipKey: string }) {
  const [data, setData] = useState<AlertPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { setOffset(0); }, [membershipKey]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    getAlerts(offset, controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setLoading(false); }
    }, failure => {
      if (!controller.signal.aborted) {
        setError(failure instanceof Error ? failure.message : "Unable to load alerts.");
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [membershipKey, offset, retry]);
  return <section className="alerts-panel" aria-labelledby="alerts-title" aria-busy={loading}>
    <div className="panel-heading">
      <h2 id="alerts-title">Recent changes{data ? ` (${data.total})` : ""}</h2>
      <button className="quiet-button" disabled={loading} onClick={() => {
        setOffset(0); setRetry(n => n + 1);
      }}>Refresh alerts</button>
    </div>
    <p>Changes affecting Pokémon in your saved teams. Unsaved drafts are not included.</p>
    {loading ? <p role="status">Checking recent changes…</p> : error ?
      <p className="message error" role="alert">{error} Use Refresh alerts to try again.</p> : data && <>
        {data.is_demo && <p className="message">Demo data: these changes are fictional and stored in a separate demo database.</p>}
        <p className="save-hint">Detected within the last {data.window_days} days. Times show when our scanner observed a change, not when the source changed.</p>
        {data.latest_scan ? <p className="save-hint">
          Latest scan: {data.latest_scan.status} · {dateText(data.latest_scan.finished_at ?? data.latest_scan.started_at)}.
          {data.latest_scan.status !== "succeeded" && " Some source data may not have been checked. Refresh alerts after a successful scan."}
        </p> : <p className="save-hint">No scan has been recorded yet. An empty list does not confirm that source data is current.</p>}
        {data.total === 0 ? <p>No recent changes affecting your saved teams.</p> : <>
          <ul className="change-list">
            {data.items.map(alert => <li key={alert.id}>
              {alert.is_manual_demo && <p className="save-hint">Demo change · applied manually through the scanner</p>}
              <h3>{alert.entity_kind === "type" ? `${alert.entity_name} type matchups changed` : `${alert.entity_name} changed`}</h3>
              <p className="save-hint">Detected <time dateTime={alert.detected_at}>{dateText(alert.detected_at)}</time></p>
              <ul>{Object.entries(alert.changes).map(([field, change]) => <li key={field}>
                {field.startsWith("damage_to.") ? `${alert.entity_name} attacks against ${field.slice(10)}` : labels[field] ?? field}: {valueText(change.before)}{field.startsWith("damage_to.") && "×"} → {valueText(change.after)}{field.startsWith("damage_to.") && "×"}
              </li>)}</ul>
              <p>Affects:</p>
              <ul>{alert.affected.map(pokemon => <li key={pokemon.id}>
                <strong>{pokemon.name}</strong>{pokemon.reasons.includes("attacking_type") && " · uses this attacking type"}{pokemon.reasons.includes("defending_type") && " · its defensive matchup changed"}
                <ul>{pokemon.teams.map(team => <li key={team.id}>{team.name} · slots {team.positions.map(p => p + 1).join(", ")}</li>)}</ul>
              </li>)}</ul>
            </li>)}
          </ul>
          {data.items.length === 0 && <p>No changes on this page. Refresh alerts to return to the latest changes.</p>}
          <nav className="catalog-pagination" aria-label="Alert pages">
            <button className="quiet-button" disabled={!offset} onClick={() => setOffset(n => Math.max(0, n - 10))}>Newer alerts</button>
            <span>{data.items.length ? offset + 1 : 0}–{Math.min(offset + data.items.length, data.total)} of {data.total}</span>
            <button className="quiet-button" disabled={offset + data.limit >= data.total} onClick={() => setOffset(n => n + 10)}>Older alerts</button>
          </nav>
        </>}
      </>}
  </section>;
}
