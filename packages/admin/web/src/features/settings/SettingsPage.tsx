import { useState } from "react";
import type { BrandingInfo, Density, ThemePref } from "../../shared/api/types";
import { apiJson } from "../../shared/api/client";
import { applyTheme, useShellStore } from "../../shared/stores/shell";

export function SettingsPage() {
  const {
    themePref,
    setThemePref,
    reducedTransparency,
    setReducedTransparency,
    density,
    setDensity,
    demoForced,
    setDemoForced,
    demoMode,
    branding,
    setBranding,
    toast,
  } = useShellStore();
  const [brandDraft, setBrandDraft] = useState<BrandingInfo>(branding);
  const [brandBusy, setBrandBusy] = useState(false);

  async function saveBranding() {
    setBrandBusy(true);
    try {
      if (!demoMode && !demoForced) {
        const current = await apiJson<Record<string, unknown>>("/settings");
        await apiJson("/settings", {
          method: "PUT",
          body: JSON.stringify({ ...current, branding: brandDraft }),
        });
      }
      setBranding(brandDraft);
      toast("Branding saved");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Save failed";
      toast(msg, "error");
    } finally {
      setBrandBusy(false);
    }
  }

  return (
    <div className="page" data-testid="settings-page">
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="sub">Appearance, branding, and dashboard preferences.</p>
        </div>
      </div>

      <section className="table-panel" style={{ padding: 20, display: "grid", gap: 18 }}>
        <div data-testid="branding-settings">
          <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Branding</h3>
          <p className="sub" style={{ marginTop: 0 }}>
            Superusers can rename the product chrome (Django-style). Defaults: AdminBoard / Phzyx.
          </p>
          <div style={{ display: "grid", gap: 10, maxWidth: 420 }}>
            {(
              [
                ["site_title", "Site title (browser tab)"],
                ["header_title", "Header title"],
                ["header_subtitle", "Header subtitle"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="field">
                <span>{label}</span>
                <input
                  value={brandDraft[key]}
                  data-testid={`branding-${key}`}
                  onChange={(e) =>
                    setBrandDraft((d) => ({ ...d, [key]: e.target.value }))
                  }
                />
              </label>
            ))}
            <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                type="checkbox"
                checked={brandDraft.show_powered_by}
                data-testid="branding-powered-by"
                onChange={(e) =>
                  setBrandDraft((d) => ({
                    ...d,
                    show_powered_by: e.target.checked,
                  }))
                }
              />
              Show “Powered by Phzyx” footer
            </label>
            <button
              type="button"
              className="btn btn-primary"
              data-testid="branding-save"
              disabled={brandBusy}
              onClick={() => void saveBranding()}
            >
              {brandBusy ? "Saving…" : "Save branding"}
            </button>
          </div>
        </div>

        <div>
          <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Theme</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {(
              [
                ["stellar-dark", "Stellar Dark"],
                ["magical-white", "Magical White"],
                ["system-ambient", "System Ambient"],
              ] as [ThemePref, string][]
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`btn ${themePref === id ? "btn-primary" : ""}`}
                data-testid={`theme-${id}`}
                onClick={() => {
                  setThemePref(id);
                  toast(`Theme: ${label}`);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            type="checkbox"
            checked={reducedTransparency}
            onChange={(e) => setReducedTransparency(e.target.checked)}
          />
          Reduced transparency
        </label>

        <div>
          <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Table density</h3>
          <div style={{ display: "flex", gap: 8 }}>
            {(
              [
                ["comfortable", "Comfortable"],
                ["compact", "Compact"],
              ] as [Density, string][]
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`btn ${density === id ? "btn-primary" : ""}`}
                onClick={() => {
                  setDensity(id);
                  applyTheme(themePref, reducedTransparency, id);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Data source</h3>
          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input
              type="checkbox"
              checked={demoForced || demoMode}
              onChange={(e) => {
                setDemoForced(e.target.checked);
                toast(e.target.checked ? "Using demo data" : "Will reconnect to API");
                window.setTimeout(() => window.location.reload(), 400);
              }}
            />
            Force demo / offline data
          </label>
        </div>
      </section>
    </div>
  );
}
