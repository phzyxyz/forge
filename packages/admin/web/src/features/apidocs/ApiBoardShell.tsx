/**
 * Standalone shell for /apiboard — same SPA bundle & theme as AdminBoard,
 * separate product surface (not nested admin nav).
 */
import { useEffect } from "react";
import { applyTheme, useShellStore } from "../../shared/stores/shell";
import {
  IconMonitor,
  IconMoon,
  IconSun,
} from "../../shared/ui/Icons";
import type { ThemePref } from "../../shared/api/types";
import { useSessionStore } from "../auth/sessionStore";
import { ApiDocsPage } from "./ApiDocsPage";

const THEME_CYCLE: ThemePref[] = ["stellar-dark", "magical-white", "system-ambient"];

function themeMeta(pref: ThemePref) {
  if (pref === "magical-white")
    return { label: "Theme · Light", Icon: IconSun, hint: "Magical White" };
  if (pref === "system-ambient")
    return { label: "Theme · System", Icon: IconMonitor, hint: "System Ambient" };
  return { label: "Theme · Dark", Icon: IconMoon, hint: "Stellar Dark" };
}

export function isApiBoardPath(pathname: string = window.location.pathname): boolean {
  const p = pathname.replace(/\/+$/, "") || "/";
  return p === "/apiboard" || p.endsWith("/apiboard");
}

export function ApiBoardShell() {
  const branding = useShellStore((s) => s.branding);
  const themePref = useShellStore((s) => s.themePref);
  const setThemePref = useShellStore((s) => s.setThemePref);
  const reducedTransparency = useShellStore((s) => s.reducedTransparency);
  const density = useShellStore((s) => s.density);
  const toasts = useShellStore((s) => s.toasts);
  const dismissToast = useShellStore((s) => s.dismissToast);
  const { username, logout } = useSessionStore();
  const theme = themeMeta(themePref);

  useEffect(() => {
    applyTheme(themePref, reducedTransparency, density);
    document.title = `API Board · ${branding.site_title || "Phzyx"}`;
  }, [themePref, reducedTransparency, density, branding.site_title]);

  function cycleTheme() {
    const i = THEME_CYCLE.indexOf(themePref);
    setThemePref(THEME_CYCLE[(i + 1) % THEME_CYCLE.length]!);
  }

  function signOut() {
    const csrf = useSessionStore.getState().csrfToken;
    void fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    }).finally(() => logout());
    logout();
  }

  // AdminBoard lives at /admin/ by default
  const adminHref = "/admin/";

  return (
    <div className="apiboard-shell" data-testid="apiboard-shell">
      <header className="apiboard-topbar">
        <div className="apiboard-brand">
          <img
            className="brand-mark"
            src={`${import.meta.env.BASE_URL}phzyx-mark.svg`}
            alt="Phzyx"
            width={28}
            height={28}
            draggable={false}
          />
          <div className="brand-text">
            <strong>API Board</strong>
            <span>{branding.header_subtitle || "Phzyx"}</span>
          </div>
        </div>
        <div className="apiboard-topbar-actions">
          <a className="btn btn-sm" href={adminHref}>
            AdminBoard
          </a>
          <button
            type="button"
            className="btn btn-sm"
            onClick={cycleTheme}
            title={theme.hint}
            data-testid="apiboard-theme"
          >
            <theme.Icon className="ico" />
            <span className="apiboard-theme-label">{theme.label}</span>
          </button>
          {username && (
            <button type="button" className="btn btn-sm" onClick={signOut}>
              Sign out
            </button>
          )}
        </div>
      </header>
      <main className="apiboard-main">
        <ApiDocsPage />
      </main>
      <div className="toast-stack">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast${t.kind === "error" ? " error" : ""}`}
            role="status"
            onClick={() => dismissToast(t.id)}
          >
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
