import type { ColumnSchema, ResourceSchema } from "../../shared/api/types";

function filterableColumns(schema: ResourceSchema): ColumnSchema[] {
  const named = new Set(schema.filterable ?? []);
  return schema.columns.filter(
    (c) => !c.hidden && (c.filterable || named.has(c.name)),
  );
}

/** Encode operator into wire key: field__op (eq uses bare field). */
export function filterWireKey(field: string, op: string): string {
  if (!op || op === "eq") return field;
  return `${field}__${op}`;
}

export function parseFilterWireKey(key: string): { field: string; op: string } {
  if (key.includes("__")) {
    const i = key.lastIndexOf("__");
    return { field: key.slice(0, i), op: key.slice(i + 2) };
  }
  return { field: key, op: "eq" };
}

const OP_LABELS: Record<string, string> = {
  eq: "=",
  ne: "≠",
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  contains: "contains",
  startswith: "starts",
  endswith: "ends",
  in: "in",
  is_null: "is null",
  is_not_null: "not null",
  like: "like",
  ilike: "ilike",
};

export function FilterBar({
  schema,
  filters,
  onChange,
}: {
  schema: ResourceSchema;
  filters: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}) {
  const cols = filterableColumns(schema);
  if (!cols.length) return null;

  const entries = Object.entries(filters).filter(([, v]) => v !== "");

  const setFilter = (wireKey: string, value: string) => {
    const next = { ...filters };
    if (value === "") delete next[wireKey];
    else next[wireKey] = value;
    onChange(next);
  };

  const setOp = (oldKey: string, field: string, newOp: string, value: string) => {
    const next = { ...filters };
    delete next[oldKey];
    const wk = filterWireKey(field, newOp);
    if (newOp === "is_null" || newOp === "is_not_null") {
      next[wk] = "1";
    } else if (value !== "") {
      next[wk] = value;
    }
    onChange(next);
  };

  return (
    <div className="filter-bar" data-testid="filter-bar">
      <div className="filter-chips">
        {entries.map(([k, v]) => {
          const { field, op } = parseFilterWireKey(k);
          const col = cols.find((c) => c.name === field);
          return (
            <button
              key={k}
              type="button"
              className="filter-chip"
              data-testid={`filter-chip-${field}`}
              onClick={() => setFilter(k, "")}
              title="Remove filter"
            >
              <span className="filter-chip-label">{col?.label ?? field}</span>
              <span className="filter-chip-val">
                {OP_LABELS[op] ?? op} {op.startsWith("is_") ? "" : v}
              </span>
              <span aria-hidden>×</span>
            </button>
          );
        })}
        {entries.length > 0 && (
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            data-testid="filter-clear-all"
            onClick={() => onChange({})}
          >
            Clear filters
          </button>
        )}
      </div>
      <div className="filter-inputs">
        {cols.map((c) => {
          const ops =
            c.filter_ops && c.filter_ops.length
              ? c.filter_ops
              : c.filter_type === "bool"
                ? ["eq", "ne"]
                : c.filter_type === "number"
                  ? ["eq", "ne", "lt", "lte", "gt", "gte"]
                  : ["eq", "contains", "startswith", "ne"];
          // find active wire key for this field
          const activeEntry = entries.find(([k]) => parseFilterWireKey(k).field === c.name);
          const activeKey = activeEntry?.[0] ?? filterWireKey(c.name, "eq");
          const activeOp = activeEntry ? parseFilterWireKey(activeEntry[0]).op : "eq";
          const activeVal = activeEntry?.[1] ?? "";

          if (c.filter_type === "bool") {
            return (
              <label key={c.name} className="filter-field">
                <span className="muted">{c.label}</span>
                <select
                  className="input"
                  data-testid={`filter-input-${c.name}`}
                  value={activeVal}
                  onChange={(e) => setFilter(filterWireKey(c.name, "eq"), e.target.value)}
                  aria-label={`Filter ${c.label}`}
                >
                  <option value="">Any</option>
                  <option value="true">Active / true</option>
                  <option value="false">Off / false</option>
                </select>
              </label>
            );
          }

          return (
            <label key={c.name} className="filter-field" style={{ minWidth: 160 }}>
              <span className="muted">{c.label}</span>
              <div style={{ display: "flex", gap: 6 }}>
                <select
                  className="input"
                  style={{ maxWidth: 110 }}
                  data-testid={`filter-op-${c.name}`}
                  value={activeOp}
                  onChange={(e) => setOp(activeKey, c.name, e.target.value, activeVal)}
                  aria-label={`Operator ${c.label}`}
                >
                  {ops.map((op) => (
                    <option key={op} value={op}>
                      {OP_LABELS[op] ?? op}
                    </option>
                  ))}
                </select>
                {activeOp === "is_null" || activeOp === "is_not_null" ? (
                  <span className="muted" style={{ alignSelf: "center", fontSize: 12 }}>
                    (no value)
                  </span>
                ) : (
                  <input
                    className="input"
                    data-testid={`filter-input-${c.name}`}
                    placeholder={
                      activeOp === "contains"
                        ? "Live search…"
                        : c.filter_type === "number"
                          ? "Number"
                          : "Value"
                    }
                    value={activeOp.startsWith("is_") ? "" : activeVal}
                    onChange={(e) => setFilter(filterWireKey(c.name, activeOp), e.target.value)}
                    aria-label={`Filter ${c.label}`}
                  />
                )}
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
}
