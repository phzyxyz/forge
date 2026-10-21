import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "./sessionStore";
import { useShellStore } from "../../shared/stores/shell";

export function LoginPage() {
  const setSession = useSessionStore((s) => s.setSession);
  const setRoute = useShellStore((s) => s.setRoute);
  const toast = useShellStore((s) => s.toast);
  const branding = useShellStore((s) => s.branding);
  const qc = useQueryClient();
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("phzyx");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Backend accepts email OR username (Django-style dual login).
      const identity = user.trim();
      const r = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email: identity, username: identity, password: pass }),
      });
      if (!r.ok) {
        const msg =
          r.status === 401
            ? "Invalid email/username or password"
            : `Sign-in failed (${r.status})`;
        setError(msg);
        toast(msg, "error");
        return;
      }
      const data = (await r.json()) as {
        csrf_token?: string;
        email?: string;
        mfa_required?: boolean;
        mfa_challenge_id?: string;
      };
      if (data.mfa_required) {
        const msg =
          "MFA is required for this account, but the demo sign-in UI has no MFA step. Use a password-only demo user (admin / phzyx after reseed).";
        setError(msg);
        toast(msg, "error");
        return;
      }
      setSession(data.email || identity, data.csrf_token ?? null);
      toast("Signed in");
      setRoute({ page: "overview" });
      await qc.invalidateQueries();
    } catch {
      const msg = "Sign-in failed (network)";
      setError(msg);
      toast(msg, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page" data-testid="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="brand" style={{ padding: 0 }}>
          <img
            className="brand-mark"
            src={`${import.meta.env.BASE_URL}phzyx-mark.svg`}
            alt="Phzyx"
            width={32}
            height={32}
            draggable={false}
          />
          <div className="brand-text">
            <strong>{branding.header_title}</strong>
            <span>{branding.header_subtitle}</span>
          </div>
        </div>
        <h1>Sign in</h1>
        <p className="sub">Use your dashboard credentials to continue.</p>
        {error && (
          <div className="alert error" data-testid="login-error">
            {error}
          </div>
        )}
        <label className="field">
          <span>Email or username</span>
          <input
            autoComplete="username"
            data-testid="login-username"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            required
            autoFocus
            placeholder="you@domain.com or handle"
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            data-testid="login-password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={busy}
          style={{ marginTop: 6 }}
          data-testid="login-submit"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          Demo defaults: <span className="mono">admin</span> / <span className="mono">phzyx</span>
        </p>
      </form>
    </div>
  );
}
