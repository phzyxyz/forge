import { useQuery } from "@tanstack/react-query";
import type { ResourceSchema } from "../../shared/api/types";
import { relativeTime } from "../../shared/lib/format";
import { useActivityStore, useShellStore } from "../../shared/stores/shell";
import { fetchDashboardWidgets } from "../resources/api";

export function OverviewPage({
  resources,
  demo,
}: {
  resources: ResourceSchema[];
  demo: boolean;
}) {
  const setRoute = useShellStore((s) => s.setRoute);
  const apiVersion = useShellStore((s) => s.apiVersion);
  const themePref = useShellStore((s) => s.themePref);
  const t = useShellStore((s) => s.t);
  const activity = useActivityStore((s) => s.items);

  const widgetsQ = useQuery({
    queryKey: ["dashboard-widgets", demo, resources.map((r) => r.name).join(",")],
    queryFn: () => fetchDashboardWidgets(demo, resources),
  });

  const widgets = widgetsQ.data ?? [];
  const totalRows = widgets.reduce((acc, w) => acc + (Number(w.value) || 0), 0);
  const countByResource = Object.fromEntries(
    widgets.map((w) => [w.resource, Number(w.value) || 0]),
  );

  return (
    <div className="page" data-testid="overview-page">
      <div className="page-header">
        <div>
          <h1>{t("nav.overview", "Overview")}</h1>
          <p className="sub">AdminBoard control surface for your Phzyx resources.</p>
        </div>
      </div>

      <div className="stat-grid" data-testid="dashboard-widgets">
        <div className="stat-card">
          <div className="label">{t("nav.resources", "Resources")}</div>
          <div className="value">{resources.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">Records</div>
          <div className="value">{widgetsQ.isLoading ? "…" : totalRows}</div>
        </div>
        <div className="stat-card">
          <div className="label">API</div>
          <div className="value" style={{ fontSize: "1.1rem" }}>
            {demo ? "Demo" : apiVersion ?? "live"}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Theme</div>
          <div className="value" style={{ fontSize: "1.05rem", textTransform: "capitalize" }}>
            {themePref.replace("-", " ")}
          </div>
        </div>
      </div>

      {widgets.length > 0 && (
        <section data-testid="widget-counts">
          <h2 style={{ margin: "8px 0 12px", fontSize: "0.95rem" }}>By resource</h2>
          <div className="stat-grid">
            {widgets.map((w) => (
              <button
                key={w.resource}
                type="button"
                className="stat-card"
                style={{ cursor: "pointer", textAlign: "left", border: 0 }}
                onClick={() => setRoute({ page: "resource", name: w.resource })}
              >
                <div className="label">{w.label || w.title || w.resource}</div>
                <div className="value">{w.value}</div>
              </button>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 style={{ margin: "8px 0 12px", fontSize: "0.95rem" }}>Quick open</h2>
        <div className="card-grid">
          {resources.map((r) => (
            <button
              key={r.name}
              type="button"
              className="card"
              data-testid={`quick-${r.name}`}
              onClick={() => setRoute({ page: "resource", name: r.name })}
            >
              <h3>{r.label}</h3>
              <p>
                {widgetsQ.isLoading
                  ? "Loading…"
                  : `${countByResource[r.name] ?? 0} record${
                      (countByResource[r.name] ?? 0) === 1 ? "" : "s"
                    }`}
                {r.primary_key.length > 1 ? " · composite PK" : ""}
              </p>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 style={{ margin: "8px 0 12px", fontSize: "0.95rem" }}>Session activity</h2>
        {activity.length === 0 ? (
          <div className="empty">
            <h3>No activity yet</h3>
            <p>Creates, updates, deletes, and exports will show up here for this session.</p>
          </div>
        ) : (
          <div className="table-panel">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.map((a) => (
                    <tr key={a.id}>
                      <td className="muted">{relativeTime(a.at)}</td>
                      <td>{a.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
