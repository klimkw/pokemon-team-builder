import { useEffect, useRef, useState, type FormEvent } from "react";
import { login, logout, type User } from "./api";

export default function SessionRecovery({ user, onRecovered }: { user: User; onRecovered: (user: User) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    return () => element.close();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try {
      const restored = await login({ username: user.username, password });
      if (restored.id !== user.id) {
        await logout();
        throw new Error("Please use the original account to recover this draft.");
      }
      onRecovered(restored);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to sign in. Try again.");
    } finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="session-recovery" aria-labelledby="recovery-title" aria-describedby="recovery-description" onCancel={event => event.preventDefault()}>
    <h2 id="recovery-title">Continue building</h2>
    <p id="recovery-description">Your session expired. Your lineup and edits are still here. Sign in as {user.username} to continue, then retry your last action.</p>
    <form onSubmit={submit}>
      <label htmlFor="recovery-username">Username</label>
      <input id="recovery-username" autoComplete="username" value={user.username} readOnly />
      <label htmlFor="recovery-password">Password</label>
      <input id="recovery-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={128} disabled={busy} autoFocus />
      {error && <p className="message error" role="alert">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? "Signing in…" : "Sign in and keep editing"}</button>
    </form>
  </dialog>;
}
