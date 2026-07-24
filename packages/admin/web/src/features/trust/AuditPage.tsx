import { useQuery } from "@tanstack/react-query";
import { apiJson, ApiError } from "../../shared/api/client";
import { useShellStore } from "../../shared/stores/shell";

type AuditEvent = {
  action: string;
  resource: string;
  principal_id?: string | null;
  at?: string;
  details?: Record<string, unknown>;
  source?: string;
};

export function AuditPage({ demo }: { demo: boolean }) {
  const toast = useShellStore((s) => s.toast);
  const q = useQuery({
    queryKey: ["audit", demo],
    queryFn: async () => {
      if (demo) {
        return {
          items: [
            {
              action: "create",
              resource: "users",
              principal_id: "demo",
              at: new Date().toISOString(),
              details: {},
            },
          ],
          total: 1,
        };
      }
      try {
        return await apiJson<{ items: AuditEvent[]; total: number }>("/audit?limit=200");
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) {
          toast("You do not have permission to view the audit log", "error");
        }
        throw e;
      }
    },
  });

  const items = [...(q.data?.items ?? [])].reverse();

  return (
    <div className="page" data-testid="audit-page">
      <div className="page-header">
        <div>
          <h1>Audit log</h1>
          <p className="sub">Admin mutations and auth security events (Diamond D7).</p>
        </div>
      </div>

      {q.isLoading && <p className="muted">Loading…</p>}
      {q.isError && (
        <div className="alert error" data-testid="audit-forbidden">
          Unable to load audit events. Staff access may be required.
        </div>
      )}

      {!q.isLoading && !q.isError && items.length === 0 && (
        <div className="empty">
          <h3>No events yet</h3>
          <p>Create, update, delete, or export records to populate the log.</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="table-panel" style={{ overflow: "auto" }}>
          <table className="data-table" data-testid="audit-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Actor</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e, i) => (
                <tr key={`${e.at}-${e.action}-${i}`}>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {e.at ? new Date(e.at).toLocaleString() : "—"}
                  </td>
                  <td>
                    <span className="filter-chip" style={{ cursor: "default" }}>
                      {e.action}
                    </span>
                  </td>
                  <td className="mono">{e.resource}</td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {e.principal_id ?? "—"}
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>
                    {e.source ?? "admin"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
