import { useState, type FormEvent } from "react";
import * as api from "./api";
import type { Team, User } from "./api";

export default function Profile({ user, teams, busy, onBack, onEdit, onDelete, onUpdated, onPasswordChanged, canEndSession, operationError }: {
  operationError?: string;
  user: User; teams: Team[]; busy: boolean; onBack: () => void; onEdit: (team: Team) => void;
  onDelete: (team: Team) => Promise<void>; onUpdated: (user: User) => void;
  onPasswordChanged: () => Promise<void>; canEndSession: () => boolean;
}) {
  const [username, setUsername] = useState(user.username);
  const [password, setPassword] = useState("");
  const [nextPassword, setNextPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving || (nextPassword && !canEndSession())) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await api.updateProfile({ current_password: password,
        ...(username.toLowerCase() !== user.username ? { username } : {}),
        ...(nextPassword ? { new_password: nextPassword } : {}) });
      setPassword(""); setNextPassword(""); onUpdated(result.user);
      if (result.session_revoked) await onPasswordChanged();
      else setNotice("Account updated.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to update account."); }
    finally { setSaving(false); }
  }
  return <section className="profile-page" aria-labelledby="profile-title">
    <div className="panel-heading"><h1 id="profile-title">Profile</h1><button className="quiet-button" disabled={saving} onClick={onBack}>Back to Pokédex</button></div>
    {operationError && <p className="message error" role="alert">{operationError}</p>}
    <div className="profile-columns">
      <section className="profile-card"><h2>Account</h2>
        <form onSubmit={submit}>
          <label htmlFor="profile-username">Username</label>
          <input id="profile-username" value={username} onChange={event => setUsername(event.target.value)} required minLength={3} maxLength={32} pattern="[a-zA-Z0-9_]+" autoComplete="username" disabled={saving} />
          <label htmlFor="new-password">New password</label>
          <input id="new-password" type="password" value={nextPassword} onChange={event => setNextPassword(event.target.value)} minLength={8} maxLength={128} autoComplete="new-password" disabled={saving} placeholder="Leave blank to keep current" />
          <p className="field-help">Changing your password signs out all sessions.</p>
          <label htmlFor="current-password">Current password</label>
          <input id="current-password" type="password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={128} autoComplete="current-password" disabled={saving} />
          {error && <p className="message error" role="alert">{error}</p>}
          {notice && <p className="message success" role="status">{notice}</p>}
          <button className="primary-button" disabled={saving || (!nextPassword && username.toLowerCase() === user.username)}>{saving ? "Saving…" : "Save account"}</button>
        </form>
      </section>
      <section className="profile-card" aria-labelledby="profile-teams"><h2 id="profile-teams">Your teams <span className="muted">{teams.length}</span></h2>
        {!teams.length && <p>No saved teams.</p>}
        <ul className="profile-teams">{teams.map(team => <li key={team.id}>
          <div><h3>{team.name}</h3><p>{team.members.map(member => member.pokemon.name).join(" · ") || "Empty team"}</p></div>
          <div className="profile-team-actions"><button className="quiet-button" disabled={busy} onClick={() => onEdit(team)} aria-label={`Edit ${team.name}`}>Edit</button><button className="quiet-button danger" disabled={busy} onClick={() => void onDelete(team)} aria-label={`Delete ${team.name}`}>Delete</button></div>
        </li>)}</ul>
      </section>
    </div>
  </section>;
}
