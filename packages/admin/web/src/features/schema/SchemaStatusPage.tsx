import { useQuery } from "@tanstack/react-query";
import { apiJson } from "../../shared/api/client";
import type { SchemaStatus } from "../../shared/api/types";

export function SchemaStatusPage({ demo }: { demo: boolean }) {
  const q = useQuery({
    queryKey: ["schema-status", demo],
    queryFn: async () => {
      if (demo) {
        return {
          ok: true,
          dialect: "demo",
          version: "offline",
          capabilities: [],
          migrations: { applied: [], pending: [] },
          plan_summary: "Offline demo — no live schema engine",
        } satisfies SchemaStatus;
      }
      return apiJson<SchemaStatus>("/schema/status");
    },
  });

  const data = q.data;

  return (
    <div className="page" data-testid="schema-status-page">
      <div className="page-header">
        <div>
          <h1>Schema status</h1>
          <p className="sub">Dialect, migrations history, and desired-vs-live plan (read-only).</p>
        </div>
      </div>

      {q.isLoading && <p className="muted">Loading…</p>}
      {q.isError && <div className="alert error">Failed to load schema status</div>}

      {data && (
        <div className="table-panel" style={{ padding: 20, display: "grid", gap: 16 }}>
          <div>
            <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Connection</h3>
            <p className="mono" style={{ margin: 0 }}>
              {data.ok ? "OK" : "Error"} · dialect={data.dialect ?? "—"} · version=
              {data.version ?? "—"}
            </p>
            {data.error && <div className="alert error">{data.error}</div>}
          </div>

          {data.capabilities && data.capabilities.length > 0 && (
            <div>
              <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Capabilities</h3>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {data.capabilities.map((c) => (
                  <li key={c} className="mono" style={{ fontSize: 12 }}>
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Migrations</h3>
            <p className="muted" style={{ margin: "0 0 8px", fontSize: 13 }}>
              dir: {data.migrations_dir ?? "—"}
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <strong>Applied</strong>
                <ul data-testid="schema-applied">
                  {(data.migrations?.applied?.length
                    ? data.migrations.applied
                    : ["(none)"]
                  ).map((v) => (
                    <li key={v} className="mono" style={{ fontSize: 12 }}>
                      {v}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <strong>Pending</strong>
                <ul data-testid="schema-pending">
                  {(data.migrations?.pending?.length
                    ? data.migrations.pending
                    : ["(none)"]
                  ).map((v) => (
                    <li key={v} className="mono" style={{ fontSize: 12 }}>
                      {v}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            {data.migrations?.note && (
              <p className="muted" style={{ fontSize: 12 }}>
                {data.migrations.note}
              </p>
            )}
          </div>

          {data.plan_summary && (
            <div>
              <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Plan summary</h3>
              <pre
                className="mono"
                data-testid="schema-plan"
                style={{
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  fontSize: 12,
                  padding: 12,
                  borderRadius: 12,
                  background: "var(--phzyx-bg-input)",
                  border: "1px solid var(--phzyx-border)",
                }}
              >
                {data.plan_summary}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
