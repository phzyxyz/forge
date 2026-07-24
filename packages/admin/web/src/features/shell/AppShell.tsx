import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ResourceSchema } from "../../shared/api/types";
import { FORBIDDEN_EVENT } from "../../shared/api/client";
import { applyTheme, useShellStore } from "../../shared/stores/shell";
import {
  IconImage,
  IconLayout,
  IconPanel,
  IconSettings,
  IconTable,
} from "../../shared/ui/Icons";
import { useSessionStore } from "../auth/sessionStore";
import { OverviewPage } from "../overview/OverviewPage";
import { ResourcePage } from "../resources/ResourcePage";
import { MediaPage } from "../media/MediaPage";
import { SchemaStatusPage } from "../schema/SchemaStatusPage";
import { SettingsPage } from "../settings/SettingsPage";
import { AuditPage } from "../trust/AuditPage";
import { ForbiddenBanner } from "../trust/ForbiddenBanner";

export function AppShell({
  resources,
  demo,
}: {
  resources: ResourceSchema[];
  demo: boolean;
}) {
  const qc = useQueryClient();
  const {
    route,
    setRoute,
    sidebarCollapsed,
    toggleSidebar,
    themePref,
    reducedTransparency,
    density,
    commandOpen,
    setCommandOpen,
    toasts,
    dismissToast,
    demoMode,
    globalSearch,
    setGlobalSearch,
    closeDrawer,
    setSelectedIds,
    syncRouteFromHash,
    branding,
  } = useShellStore();
  const { username, logout } = useSessionStore();
  const [forbidden, setForbidden] = useState<{
    message: string;
    action?: string;
    resource?: string;
  } | null>(null);

  useEffect(() => {
    applyTheme(themePref, reducedTransparency, density);
  }, [themePref, reducedTransparency, density]);

  useEffect(() => {
    const onForbidden = (ev: Event) => {
      const d = (ev as CustomEvent).detail as {
        message?: string;
        action?: string;
        resource?: string;
      };
      setForbidden({
        message: d.message || "You do not have permission for this action",
        action: d.action != null ? String(d.action) : undefined,
        resource: d.resource != null ? String(d.resource) : undefined,
      });
    };
    window.addEventListener(FORBIDDEN_EVENT, onForbidden);
    return () => window.removeEventListener(FORBIDDEN_EVENT, onForbidden);
  }, []);

  useEffect(() => {
    const onHash = () => syncRouteFromHash();
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [syncRouteFromHash]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing =
        tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(!commandOpen);
        return;
      }
      if (e.key === "/" && !typing) {
        e.preventDefault();
        document.getElementById("resource-search")?.focus();
        document.getElementById("top-search")?.focus();
      }
      if (e.key === "Escape") {
        setCommandOpen(false);
        closeDrawer();
      }
      if (e.key.toLowerCase() === "n" && !typing && route.page === "resource") {
        useShellStore.getState().openDrawer("create", route.name);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commandOpen, setCommandOpen, route, closeDrawer]);

  const breadcrumb = useMemo(() => {
    if (route.page === "overview") return "Overview";
    if (route.page === "media") return "Media";
    if (route.page === "schema") return "Schema";
    if (route.page === "audit") return "Audit";
    if (route.page === "settings") return "Settings";
    if (route.page === "resource") {
      return resources.find((r) => r.name === route.name)?.label ?? route.name;
    }
    return "AdminBoard";
  }, [route, resources]);

  function signOut() {
    const csrf = useSessionStore.getState().csrfToken;
    void fetch("/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    }).finally(() => {
      logout();
    });
    logout();
    closeDrawer();
    setSelectedIds([]);
    qc.clear();
    setRoute({ page: "overview" });
  }

  const paletteItems = [
    { label: "Overview", sub: "Dashboard home", run: () => setRoute({ page: "overview" }) },
    ...resources.map((r) => ({
      label: r.label,
      sub: `Resource · ${r.name}`,
      run: () => setRoute({ page: "resource", name: r.name }),
    })),
    { label: "Media", sub: "File keys", run: () => setRoute({ page: "media" }) },
    { label: "Schema", sub: "Migrations & plan", run: () => setRoute({ page: "schema" }) },
    { label: "Audit", sub: "Security events", run: () => setRoute({ page: "audit" }) },
    { label: "Settings", sub: "Theme & density", run: () => setRoute({ page: "settings" }) },
  ];

  return (
    <div
      className={`shell${sidebarCollapsed ? " collapsed" : ""}`}
      data-testid="app-shell"
    >
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" />
          <div className="brand-text">
            <strong>{branding.header_title}</strong>
            <span>{branding.header_subtitle}</span>
          </div>
        </div>

        <div className="nav-section">Workspace</div>
        <button
          type="button"
          className={`nav-item${route.page === "overview" ? " active" : ""}`}
          data-testid="nav-overview"
          onClick={() => setRoute({ page: "overview" })}
        >
          <IconLayout className="ico" />
          <span className="nav-label">Overview</span>
        </button>

        <div className="nav-section">Resources</div>
        {resources.map((r) => (
          <button
            key={r.name}
            type="button"
            className={`nav-item${route.page === "resource" && route.name === r.name ? " active" : ""}`}
            data-testid={`nav-${r.name}`}
            onClick={() => setRoute({ page: "resource", name: r.name })}
          >
            <IconTable className="ico" />
            <span className="nav-label">{r.label}</span>
          </button>
        ))}

        <div className="nav-section">Library</div>
        <button
          type="button"
          className={`nav-item${route.page === "media" ? " active" : ""}`}
          data-testid="nav-media"
          onClick={() => setRoute({ page: "media" })}
        >
          <IconImage className="ico" />
          <span className="nav-label">Media</span>
        </button>
        <button
          type="button"
          className={`nav-item${route.page === "schema" ? " active" : ""}`}
          data-testid="nav-schema"
          onClick={() => setRoute({ page: "schema" })}
        >
          <IconTable className="ico" />
          <span className="nav-label">Schema</span>
        </button>
        <button
          type="button"
          className={`nav-item${route.page === "audit" ? " active" : ""}`}
          data-testid="nav-audit"
          onClick={() => setRoute({ page: "audit" })}
        >
          <IconPanel className="ico" />
          <span className="nav-label">Audit</span>
        </button>
        <button
          type="button"
          className={`nav-item${route.page === "settings" ? " active" : ""}`}
          data-testid="nav-settings"
          onClick={() => setRoute({ page: "settings" })}
        >
          <IconSettings className="ico" />
          <span className="nav-label">Settings</span>
        </button>

        <div className="sidebar-foot">
          <button type="button" className="btn btn-ghost btn-sm" onClick={toggleSidebar}>
            <IconPanel />
            <span className="hide-collapsed">{sidebarCollapsed ? "Expand" : "Collapse"}</span>
          </button>
        </div>
      </aside>

      <div className="main-col">
        <header className="topbar">
          <div className="breadcrumb">
            <span>AdminBoard</span>
            <span aria-hidden>/</span>
            <strong>{breadcrumb}</strong>
          </div>
          <div className="topbar-spacer" />
          <input
            id="top-search"
            className="topbar-search"
            placeholder="Search or jump…  ⌘K"
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            onFocus={() => setCommandOpen(true)}
            aria-label="Command search"
          />
          <div className="user-chip">
            <span className="user-avatar" />
            <span>{username || (demo ? "demo" : "signed in")}</span>
            {!demo && (
              <button
                type="button"
                className="btn btn-sm"
                style={{ height: 28, padding: "0 10px" }}
                title="Sign out of AdminBoard"
                data-testid="sign-out"
                onClick={signOut}
              >
                Sign out
              </button>
            )}
          </div>
        </header>

        {(demoMode || demo) && (
          <div style={{ padding: "10px 24px 0" }}>
            <div className="demo-banner">
              <span>
                {demo
                  ? "Demo data mode — interactive offline sample (not connected to live API)."
                  : "Connected to live API."}
              </span>
            </div>
          </div>
        )}

        {route.page === "overview" && <OverviewPage resources={resources} demo={demo} />}
        {route.page === "resource" && (
          <ResourcePage name={route.name} resources={resources} demo={demo} />
        )}
        {route.page === "media" && <MediaPage resources={resources} demo={demo} />}
        {route.page === "schema" && <SchemaStatusPage demo={demo} />}
        {route.page === "audit" && <AuditPage demo={demo} />}
        {forbidden && (
          <div style={{ padding: "12px 24px 0" }}>
            <ForbiddenBanner
              message={forbidden.message}
              action={forbidden.action}
              resource={forbidden.resource}
              onDismiss={() => setForbidden(null)}
            />
          </div>
        )}
        {route.page === "settings" && <SettingsPage />}
        {route.page === "login" && null}
        {branding.show_powered_by ? (
          <footer
            className="muted"
            style={{
              padding: "16px 24px 24px",
              fontSize: 12,
              opacity: 0.75,
            }}
            data-testid="powered-by-phzyx"
          >
            Powered by{" "}
            <a href="https://phzyx.xyz" target="_blank" rel="noopener noreferrer">
              Phzyx
            </a>
          </footer>
        ) : null}
      </div>

      {commandOpen && (
        <>
          <div className="overlay" onClick={() => setCommandOpen(false)} />
          <div className="palette" role="dialog" aria-label="Command palette" data-testid="command-palette">
            <input
              autoFocus
              placeholder="Jump to…"
              defaultValue={globalSearch}
              onChange={(e) => setGlobalSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const q = globalSearch.toLowerCase();
                  const hit =
                    paletteItems.find((i) => i.label.toLowerCase().includes(q)) || paletteItems[0];
                  hit?.run();
                  setCommandOpen(false);
                }
              }}
            />
            <div className="palette-list">
              {paletteItems
                .filter(
                  (i) =>
                    !globalSearch ||
                    i.label.toLowerCase().includes(globalSearch.toLowerCase()) ||
                    i.sub.toLowerCase().includes(globalSearch.toLowerCase()),
                )
                .map((i) => (
                  <button
                    key={i.label}
                    type="button"
                    className="palette-item"
                    onClick={() => {
                      i.run();
                      setCommandOpen(false);
                    }}
                  >
                    {i.label}
                    <small>{i.sub}</small>
                  </button>
                ))}
            </div>
          </div>
        </>
      )}

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
