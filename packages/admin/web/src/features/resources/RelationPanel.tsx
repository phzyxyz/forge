import { useQuery } from "@tanstack/react-query";
import type { RelationSchema, ResourceSchema } from "../../shared/api/types";
import { useShellStore } from "../../shared/stores/shell";
import { listRelation } from "./api";

export function RelationPanel({
  parent,
  identity,
  relations,
  demo,
}: {
  parent: ResourceSchema;
  identity: string;
  relations: RelationSchema[];
  demo: boolean;
}) {
  const setRoute = useShellStore((s) => s.setRoute);
  if (!relations.length || !identity) return null;

  return (
    <div className="relation-panels" data-testid="relation-panels">
      {relations.map((rel) => (
        <RelationBlock
          key={rel.name}
          parentName={parent.name}
          identity={identity}
          rel={rel}
          demo={demo}
          onOpenResource={(name) => setRoute({ page: "resource", name })}
        />
      ))}
    </div>
  );
}

function RelationBlock({
  parentName,
  identity,
  rel,
  demo,
  onOpenResource,
}: {
  parentName: string;
  identity: string;
  rel: RelationSchema;
  demo: boolean;
  onOpenResource: (name: string) => void;
}) {
  const q = useQuery({
    queryKey: ["relation", parentName, identity, rel.name],
    queryFn: () => listRelation(demo, parentName, identity, rel.name, { page_size: 25 }),
  });

  const items = q.data?.items ?? [];
  const kind = rel.kind || q.data?.kind || "has_many";

  return (
    <section className="relation-panel" data-testid={`relation-panel-${rel.name}`}>
      <div className="relation-panel-header">
        <h3>
          {rel.label}
          <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
            {kind === "m2m" ? "M2M · " : ""}
            {q.isLoading ? "…" : `${q.data?.total ?? items.length}`}
          </span>
        </h3>
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() => onOpenResource(rel.resource)}
        >
          Open {rel.resource}
        </button>
      </div>
      {kind === "m2m" && (
        <p className="muted" style={{ margin: "0 0 8px", fontSize: 12 }}>
          Many-to-many via {rel.through || "through table"}. Edit memberships in Edit mode.
        </p>
      )}
      {q.isError && (
        <div className="alert error">{(q.error as Error).message || "Failed to load"}</div>
      )}
      {!q.isLoading && items.length === 0 && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          No related {rel.label.toLowerCase()}.
        </p>
      )}
      {items.length > 0 && (
        <ul className="relation-list" data-testid={`relation-list-${rel.name}`}>
          {items.map((row) => {
            const id = String(row._identity ?? "");
            const summary = Object.entries(row)
              .filter(([k]) => k !== "_identity")
              .slice(0, 4)
              .map(([k, v]) => `${k}=${v}`)
              .join(" · ");
            return (
              <li key={id} data-testid="relation-row">
                <span className="mono muted" style={{ fontSize: 11 }}>
                  {id}
                </span>
                <span style={{ fontSize: 13 }}>{summary}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
