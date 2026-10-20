import { useEffect, useRef, useState, type FormEvent } from "react";
import * as api from "./api";
import TeamBuilder from "./TeamBuilder";
import type { User } from "./api";

type Mode = "login" | "register";
type SessionState =
  | { status: "checking" }
  | { status: "error"; message: string }
  | { status: "ready"; user: User | null };

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

export default function App() {
  const [session, setSession] = useState<SessionState>({ status: "checking" });
  const [retry, setRetry] = useState(0);
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const usernameInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!busy && notice.startsWith("Account created.")) {
      passwordInput.current?.focus();
    }
  }, [busy, notice]);

  useEffect(() => {
    const controller = new AbortController();
    setSession({ status: "checking" });
    // Ignore stale responses when StrictMode remounts or the user retries.
    api.getCurrentUser(controller.signal).then(
      (user) => {
        if (!controller.signal.aborted) setSession({ status: "ready", user });
      },
      (error) => {
        if (!controller.signal.aborted)
          setSession({ status: "error", message: errorMessage(error) });
      },
    );
    return () => controller.abort();
  }, [retry]);

  function changeMode(next: Mode) {
    setMode(next);
    setPassword("");
    setShowPassword(false);
    setError("");
    setNotice("");
    usernameInput.current?.focus();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const credentials = { username, password };
      if (mode === "register") {
        await api.register(credentials);
        setMode("login");
        setPassword("");
        setShowPassword(false);
        setNotice(
          "Account created. Sign in with your new password to continue.",
        );
      } else {
        const user = await api.login(credentials);
        setSession({ status: "ready", user });
        setPassword("");
        setShowPassword(false);
      }
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api.logout();
      setSession({ status: "ready", user: null });
      setMode("login");
      setPassword("");
      setShowPassword(false);
      setNotice("You’re signed out. Your account is saved for next time.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  const user = session.status === "ready" ? session.user : null;

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Pokémon Team Builder home">
          <span className="ball-mark" aria-hidden="true" />
          <span>
            Pokémon<span className="brand-subtitle">TEAM BUILDER</span>
          </span>
        </a>
        <span className="header-note">
          <span className="status-dot" />A place for your next lineup
        </span>
      </header>

      {user ? (
        <TeamBuilder
          user={user}
          onSignOut={signOut}
          signingOut={busy}
          accountError={error}
        />
      ) : (
        <main className="account-layout">
          <section className="intro" aria-labelledby="intro-title">
            <p className="eyebrow">
              <span className="eyebrow-line" />
              THE MAKING OF A GREAT TEAM
            </p>
            <h1 id="intro-title">
              Every great team
              <br />
              starts with <span>you.</span>
            </h1>
            <p className="intro-copy">
              A favorite partner. An unexpected pairing.
              <br className="desktop-break" /> A team that’s entirely yours.
            </p>

            <div className="lineup-art" aria-hidden="true">
              <div className="lineup-label">
                <span>YOUR NEXT CHAPTER</span>
                <span>01 — 06</span>
              </div>
              <div className="lineup-circles">
                <div className="partner-ball">
                  <span />
                </div>
                {[2, 3, 4, 5, 6].map((number) => (
                  <div className="empty-slot" key={number}>
                    <span>+</span>
                    <small>0{number}</small>
                  </div>
                ))}
              </div>
              <div className="lineup-caption">
                <span className="tiny-star">✳</span> SIX SPOTS. ENDLESS
                POSSIBILITIES.
              </div>
            </div>
            <p className="intro-footnote">
              A little strategy. A lot of possibility.
            </p>
          </section>

          <section
            className="account-card"
            aria-labelledby="account-title"
            aria-busy={busy || session.status === "checking"}
          >
            {session.status === "checking" ? (
              <div className="state-panel" role="status">
                <span className="ball-mark large spinning" aria-hidden="true" />
                <h2 id="account-title">Getting things ready</h2>
                <p>Checking your sign-in status…</p>
              </div>
            ) : session.status === "error" ? (
              <div className="state-panel">
                <p className="eyebrow">CONNECTION INTERRUPTED</p>
                <h2 id="account-title">Let’s try that again.</h2>
                <p role="alert">{session.message}</p>
                <button
                  className="primary-button"
                  onClick={() => setRetry((value) => value + 1)}
                >
                  Retry connection <span aria-hidden="true">↗</span>
                </button>
              </div>
            ) : (
              <>
                <div
                  className="mode-switch"
                  role="group"
                  aria-label="Account options"
                >
                  <button
                    type="button"
                    aria-pressed={mode === "login"}
                    onClick={() => changeMode("login")}
                    disabled={busy}
                  >
                    Sign in
                  </button>
                  <button
                    type="button"
                    aria-pressed={mode === "register"}
                    onClick={() => changeMode("register")}
                    disabled={busy}
                  >
                    Create account
                  </button>
                </div>
                <p className="card-kicker">
                  {mode === "login"
                    ? "WELCOME BACK, TRAINER"
                    : "YOUR JOURNEY STARTS HERE"}
                </p>
                <h2 id="account-title">
                  {mode === "login"
                    ? "Pick up where you left off."
                    : "Make it your own."}
                </h2>
                <p className="card-description">
                  {mode === "login"
                    ? "Sign in to your Pokémon Team Builder account."
                    : "Choose a username and password to get started."}
                </p>
                {notice && (
                  <p className="message success" role="status">
                    {notice}
                  </p>
                )}
                {error && (
                  <p className="message error" id="form-error" role="alert">
                    {error}
                  </p>
                )}

                <form
                  onSubmit={submit}
                  aria-describedby={error ? "form-error" : undefined}
                >
                  <label htmlFor="username">Username</label>
                  <input
                    ref={usernameInput}
                    id="username"
                    name="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    required
                    minLength={3}
                    maxLength={32}
                    pattern="[a-zA-Z0-9_]+"
                    disabled={busy}
                    aria-describedby={
                      mode === "register" ? "username-help" : undefined
                    }
                  />
                  {mode === "register" && (
                    <p className="field-help" id="username-help">
                      3–32 letters, numbers, or underscores. Case doesn’t
                      matter.
                    </p>
                  )}
                  <label htmlFor="password">Password</label>
                  <div className="password-field">
                    <input
                      ref={passwordInput}
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      autoComplete={
                        mode === "register"
                          ? "new-password"
                          : "current-password"
                      }
                      required
                      minLength={mode === "register" ? 8 : undefined}
                      maxLength={128}
                      disabled={busy}
                      aria-describedby={
                        mode === "register" ? "password-help" : undefined
                      }
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowPassword((value) => !value)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                      aria-pressed={showPassword}
                      disabled={busy}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                  {mode === "register" && (
                    <p className="field-help" id="password-help">
                      Use 8–128 characters. A longer password is better.
                    </p>
                  )}
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={busy}
                  >
                    {busy
                      ? mode === "register"
                        ? "Creating account…"
                        : "Signing in…"
                      : mode === "register"
                        ? "Create account"
                        : "Sign in"}
                    <span aria-hidden="true">↗</span>
                  </button>
                </form>
                <p className="account-note">
                  <span className="note-icon" aria-hidden="true">
                    ◇
                  </span>
                  {mode === "login"
                    ? "Your teams belong to your account. Come back anytime."
                    : "No email needed. Just a username and a fresh start."}
                </p>
              </>
            )}
          </section>
        </main>
      )}
      <footer className="site-footer">
        <span>BUILT FOR THE TEAM YOU HAVE IN MIND.</span>
        <span>
          Pokémon Team Builder <span aria-hidden="true">↗</span>
        </span>
      </footer>
    </div>
  );
}
