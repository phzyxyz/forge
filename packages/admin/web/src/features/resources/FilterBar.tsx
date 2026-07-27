import { useEffect, useId, useMemo, useRef, useState } from "react";
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

/** Short labels for chips */
export const OP_LABELS: Record<string, string> = {
  eq: "=",
  ne: "≠",
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  contains: "contains",
  startswith: "starts with",
  endswith: "ends with",
  in: "in",
  is_null: "is empty",
  is_not_null: "is not empty",
  like: "like",
  ilike: "ilike",
};

/** Full labels for the operator menu */
export const OP_MENU_LABELS: Record<string, string> = {
  eq: "Equals",
  ne: "Not equal",
  lt: "Less than",
  lte: "Less or equal",
  gt: "Greater than",
  gte: "Greater or equal",
  contains: "Contains",
  startswith: "Starts with",
  endswith: "Ends with",
  in: "In list",
  is_null: "Is empty",
  is_not_null: "Is not empty",
  like: "Like",
  ilike: "ILike",
};

function opsForColumn(c: ColumnSchema): string[] {
  if (c.filter_ops && c.filter_ops.length) return c.filter_ops;
  if (c.filter_type === "bool") return ["eq", "ne"];
  if (c.filter_type === "number") return ["eq", "ne", "lt", "lte", "gt", "gte"];
  return ["eq", "contains", "startswith", "ne"];
}

function activeForField(
  filters: Record<string, string>,
  field: string,
): { key: string; op: string; value: string } | null {
  const entry = Object.entries(filters).find(
    ([k, v]) => v !== "" && parseFilterWireKey(k).field === field,
  );
  if (!entry) return null;
  const { op } = parseFilterWireKey(entry[0]);
  return { key: entry[0], op, value: entry[1] };
}

type FilterBarProps = {
  schema: ResourceSchema;
  filters: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
};

/**
 * Chip-first filters: toolbar control + popover editor + active chips.
 * Wire format unchanged (field / field__op).
 */
export function FilterBar({ schema, filters, onChange }: FilterBarProps) {
  const cols = useMemo(() => filterableColumns(schema), [schema]);
  const [open, setOpen] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  const entries = useMemo(
    () => Object.entries(filters).filter(([, v]) => v !== ""),
    [filters],
  );

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!cols.length) return null;

  const clearFieldKeys = (next: Record<string, string>, field: string) => {
    for (const k of Object.keys(next)) {
      if (parseFilterWireKey(k).field === field) delete next[k];
    }
  };

  const setFilter = (field: string, op: string, value: string) => {
    const next = { ...filters };
    clearFieldKeys(next, field);
    if (value === "") {
      onChange(next);
      return;
    }
    next[filterWireKey(field, op)] = value;
    onChange(next);
  };

  const setOp = (field: string, newOp: string, value: string) => {
    const next = { ...filters };
    clearFieldKeys(next, field);
    const wk = filterWireKey(field, newOp);
    if (newOp === "is_null" || newOp === "is_not_null") {
      next[wk] = "1";
    } else if (value !== "") {
      next[wk] = value;
    }
    // Empty value: no chip yet, but FilterEditor keeps draftOp locally
    onChange(next);
  };

  const removeField = (field: string) => {
    const next = { ...filters };
    for (const k of Object.keys(next)) {
      if (parseFilterWireKey(k).field === field) delete next[k];
    }
    onChange(next);
  };

  const openEditor = (field: string) => {
    setEditingField(field);
    setOpen(true);
  };

  const editingCol = cols.find((c) => c.name === editingField) ?? null;
  const editingActive = editingField ? activeForField(filters, editingField) : null;

  return (
    <div className="filter-bar" data-testid="filter-bar" ref={rootRef}>
      <div className="filter-toolbar-slot">
        <button
          type="button"
          className={`btn btn-sm filter-open-btn${open ? " is-open" : ""}${entries.length ? " has-filters" : ""}`}
          data-testid="filter-open"
          aria-expanded={open}
          aria-controls={popoverId}
          onClick={() => {
            setOpen((v) => !v);
            if (!editingField && cols[0]) setEditingField(cols[0].name);
          }}
        >
          Filters
          {entries.length > 0 && (
            <span className="filter-badge" data-testid="filter-count">
              {entries.length}
            </span>
          )}
          <span className="filter-caret" aria-hidden>
            ▾
          </span>
        </button>

        {open && (
          <div
            className="filter-popover"
            id={popoverId}
            data-testid="filter-popover"
            role="dialog"
            aria-label="Table filters"
          >
            <div className="filter-popover-body">
              <div className="filter-field-list" role="listbox" aria-label="Filterable fields">
                {cols.map((c) => {
                  const active = activeForField(filters, c.name);
                  const selected = editingField === c.name;
                  return (
                    <button
                      key={c.name}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      className={`filter-field-item${selected ? " is-selected" : ""}${active ? " is-active" : ""}`}
                      data-testid={`filter-field-${c.name}`}
                      onClick={() => setEditingField(c.name)}
                    >
                      <span className="filter-field-item-label">{c.label}</span>
                      {active && (
                        <span className="filter-field-item-hint">
                          {OP_LABELS[active.op] ?? active.op}
                          {active.op.startsWith("is_") ? "" : ` ${active.value}`}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="filter-editor">
                {editingCol ? (
                  <FilterEditor
                    key={editingCol.name}
                    col={editingCol}
                    activeOp={editingActive?.op ?? "eq"}
                    activeVal={editingActive?.value ?? ""}
                    onSetFilter={setFilter}
                    onSetOp={setOp}
                    onClear={() => removeField(editingCol.name)}
                  />
                ) : (
                  <p className="filter-editor-empty muted">Choose a field to filter</p>
                )}
              </div>
            </div>

            {entries.length > 0 && (
              <div className="filter-popover-footer">
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  data-testid="filter-clear-all"
                  onClick={() => {
                    onChange({});
                    setEditingField(cols[0]?.name ?? null);
                  }}
                >
                  Clear all
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {entries.length > 0 && (
        <div className="filter-chips" data-testid="filter-chips">
          {entries.map(([k, v]) => {
            const { field, op } = parseFilterWireKey(k);
            const col = cols.find((c) => c.name === field);
            const label = col?.label ?? field;
            return (
              <span key={k} className="filter-chip" data-testid={`filter-chip-${field}`}>
                <button
                  type="button"
                  className="filter-chip-main"
                  onClick={() => openEditor(field)}
                  title="Edit filter"
                >
                  <span className="filter-chip-label">{label}</span>
                  <span className="filter-chip-val">
                    {OP_LABELS[op] ?? op}
                    {op.startsWith("is_") ? "" : ` ${v}`}
                  </span>
                </button>
                <button
                  type="button"
                  className="filter-chip-remove"
                  aria-label={`Remove filter ${label}`}
                  data-testid={`filter-chip-remove-${field}`}
                  onClick={() => removeField(field)}
                >
                  ×
                </button>
              </span>
            );
          })}
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            data-testid="filter-clear-all-chips"
            onClick={() => onChange({})}
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}

/** Custom op menu — native <select> is clipped/unusable inside overflow panels. */
function OperatorMenu({
  field,
  ops,
  value,
  onChange,
}: {
  field: string;
  ops: string[];
  value: string;
  onChange: (op: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const label = OP_MENU_LABELS[value] ?? OP_LABELS[value] ?? value;

  return (
    <div className="filter-op-menu" ref={ref}>
      <button
        type="button"
        className={`filter-op-trigger${open ? " is-open" : ""}`}
        data-testid={`filter-op-${field}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="filter-op-trigger-label">{label}</span>
        <span className="filter-op-trigger-chevron" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <ul className="filter-op-list" role="listbox" aria-label="Operator">
          {ops.map((op) => (
            <li key={op} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={op === value}
                className={`filter-op-option${op === value ? " is-selected" : ""}`}
                data-testid={`filter-op-option-${field}-${op}`}
                onClick={() => {
                  onChange(op);
                  setOpen(false);
                }}
              >
                <span className="filter-op-option-main">
                  {OP_MENU_LABELS[op] ?? OP_LABELS[op] ?? op}
                </span>
                <span className="filter-op-option-sym muted">
                  {OP_LABELS[op] && OP_LABELS[op] !== (OP_MENU_LABELS[op] ?? op)
                    ? OP_LABELS[op]
                    : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FilterEditor({
  col,
  activeOp,
  activeVal,
  onSetFilter,
  onSetOp,
  onClear,
}: {
  col: ColumnSchema;
  activeOp: string;
  activeVal: string;
  onSetFilter: (field: string, op: string, value: string) => void;
  onSetOp: (field: string, newOp: string, value: string) => void;
  onClear: () => void;
}) {
  const ops = opsForColumn(col);
  // Draft op is local so choosing "Contains" before typing does not snap back to Equals
  // (parent filters only store non-empty values → would otherwise re-default to eq).
  const [draftOp, setDraftOp] = useState(activeOp);
  const [draftVal, setDraftVal] = useState(activeVal);

  useEffect(() => {
    setDraftVal(activeVal);
    // Only adopt parent op when a filter is actually applied (or null-ops).
    if (activeVal !== "" || activeOp === "is_null" || activeOp === "is_not_null") {
      setDraftOp(activeOp);
    }
  }, [activeOp, activeVal]);

  if (col.filter_type === "bool") {
    return (
      <div className="filter-editor-inner">
        <div className="filter-editor-title">{col.label}</div>
        <label className="filter-editor-field">
          <span className="muted">Value</span>
          <div className="filter-select-wrap">
            <select
              className="input filter-select"
              data-testid={`filter-input-${col.name}`}
              value={draftVal}
              onChange={(e) => {
                setDraftVal(e.target.value);
                onSetFilter(col.name, "eq", e.target.value);
              }}
              aria-label={`Filter ${col.label}`}
            >
              <option value="">Any</option>
              <option value="true">Active / true</option>
              <option value="false">Off / false</option>
            </select>
            <span className="filter-select-chevron" aria-hidden>
              ▾
            </span>
          </div>
        </label>
        {draftVal !== "" && (
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => {
              setDraftVal("");
              onClear();
            }}
          >
            Clear field
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="filter-editor-inner">
      <div className="filter-editor-title">{col.label}</div>
      <div className="filter-editor-field">
        <span className="muted">Operator</span>
        <OperatorMenu
          field={col.name}
          ops={ops}
          value={draftOp}
          onChange={(op) => {
            setDraftOp(op);
            onSetOp(col.name, op, draftVal);
          }}
        />
      </div>
      {draftOp === "is_null" || draftOp === "is_not_null" ? (
        <p className="muted filter-editor-hint">No value needed for this operator.</p>
      ) : (
        <label className="filter-editor-field">
          <span className="muted">Value</span>
          <input
            className="input"
            data-testid={`filter-input-${col.name}`}
            placeholder={
              draftOp === "contains"
                ? "Contains…"
                : draftOp === "startswith"
                  ? "Starts with…"
                  : draftOp === "endswith"
                    ? "Ends with…"
                    : col.filter_type === "number"
                      ? "Number"
                      : "Value"
            }
            value={draftOp.startsWith("is_") ? "" : draftVal}
            onChange={(e) => {
              const v = e.target.value;
              setDraftVal(v);
              onSetFilter(col.name, draftOp, v);
            }}
            aria-label={`Filter ${col.label}`}
          />
        </label>
      )}
      {draftVal !== "" && (
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() => {
            setDraftVal("");
            setDraftOp("eq");
            onClear();
          }}
        >
          Clear field
        </button>
      )}
    </div>
  );
}
