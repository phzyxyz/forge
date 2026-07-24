import { useQueries } from "@tanstack/react-query";
import type { ResourceSchema } from "../../shared/api/types";
import { relativeTime } from "../../shared/lib/format";
import { useActivityStore, useShellStore } from "../../shared/stores/shell";
import { listRecords } from "../resources/api";

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
  const activity = useActivityStore((s) => s.items);

  const counts = useQueries({
    queries: resources.map((r) => ({
      queryKey: ["list", r.name, "overview"],
      queryFn: () => listRecords(demo, r.name, { page: 1, page_size: 5 }),
    })),
  });

  const totalRows = counts.reduce((acc, q) => acc + (q.data?.total ?? 0), 0);

  return (
    <div className="page" data-testid="overview-page">
      <div className="page-header">
        <div>
          <h1>Overview</h1>
          <p className="sub">AdminBoard control surface for your Phzyx resources.</p>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Resources</div>
          <div className="value">{resources.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">Records</div>
          <div className="value">{totalRows}</div>
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

      <section>
        <h2 style={{ margin: "8px 0 12px", fontSize: "0.95rem" }}>Quick open</h2>
        <div className="card-grid">
          {resources.map((r, i) => (
            <button
              key={r.name}
              type="button"
              className="card"
              data-testid={`quick-${r.name}`}
              onClick={() => setRoute({ page: "resource", name: r.name })}
            >
              <h3>{r.label}</h3>
              <p>
                {counts[i]?.data
                  ? `${counts[i].data!.total} record${counts[i].data!.total === 1 ? "" : "s"}`
                  : "Loading…"}
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
