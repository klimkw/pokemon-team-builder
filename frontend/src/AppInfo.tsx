import { useEffect, useRef, useState } from "react";
import RefreshButton from "./RefreshButton";
import { getAppInfo, type AppInfo as Info } from "./api";

const date = (value: string | null) => value ? new Date(value).toLocaleString() : "Not completed";

export default function AppInfo() {
  const [open, setOpen] = useState(false);
  const [retry, setRetry] = useState(0);
  const [data, setData] = useState<Info | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const element = dialog.current!;
    element.showModal();
    return () => element.close();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    getAppInfo(controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setLoading(false); }
    }, failure => {
      if (!controller.signal.aborted) { setError(failure instanceof Error ? failure.message : "Unable to load app info."); setLoading(false); }
    });
    return () => controller.abort();
  }, [open, retry]);
  return <>
    <button className="icon-button" aria-label="App info" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/></svg>
    </button>
    {open && <dialog className="app-info-dialog" ref={dialog} aria-labelledby="app-info-title" onCancel={() => setOpen(false)}>
      <div className="panel-heading"><h2 id="app-info-title">App info</h2><div className="panel-header-actions"><RefreshButton label="Refresh info" loading={loading} onRefresh={() => setRetry(value => value + 1)} /><button className="icon-button" aria-label="Close app info" onClick={() => setOpen(false)}>×</button></div></div>
      {loading && <p role="status">Loading app info…</p>}
      {error && <p className="message error" role="alert">{error}</p>}
      {!loading && !error && data && <>
        <dl className="info-values">
          <div><dt>Version</dt><dd>{data.app_version}</dd></div>
          <div><dt>Catalog source</dt><dd><a href={data.catalog_source_url} target="_blank" rel="noreferrer">PokéAPI ↗</a></dd></div>
          <div><dt>Pokémon catalog</dt><dd>{data.catalog_count.toLocaleString()} entries</dd></div>
          <div><dt>Live refresh interval</dt><dd>{data.scan_interval_hours} hours</dd></div>
          <div><dt>Alert window</dt><dd>{data.alert_window_days} days</dd></div>
          <div><dt>Last successful live refresh</dt><dd>{data.last_successful_live_refresh ? date(data.last_successful_live_refresh.finished_at) : "None recorded"}</dd></div>
        </dl>
        <nav className="info-links"><a href={data.repository_url} target="_blank" rel="noreferrer">Repository ↗</a><a href="/counter-method" target="_blank" rel="noreferrer">Calculation guide ↗</a></nav>
      </>}
    </dialog>}
  </>;
}
