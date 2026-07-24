import { useEffect, useMemo, useRef, useState } from "react";
import { autocompleteResource, getM2mIds, setM2mIds } from "../api";
import { useFormContext } from "../FormContext";
import type { FieldWidgetProps } from "./types";

type Option = { value: string; label: string };

/** Multi-select for M2M relations (Diamond D4.5). Value is comma-separated IDs. */
export function M2mWidget({ column, value, readOnly, error, onChange }: FieldWidgetProps) {
  const { demo, identity, resourceName, mode } = useFormContext() as {
    demo: boolean;
    identity?: string;
    resourceName?: string;
    mode?: string;
  };
  const target = column.fk_resource || column.m2m_resource;
  const relation = column.m2m_relation || column.name;
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Option[]>([]);
  const [selected, setSelected] = useState<Option[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  const ids = useMemo(
    () =>
      String(value || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    [value],
  );

  // Load current memberships when editing existing record
  useEffect(() => {
    if (!resourceName || !identity || !relation || mode === "create" || demo === undefined) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await getM2mIds(demo, resourceName, identity, relation);
        if (cancelled) return;
        const nextIds = res.ids.map(String);
        onChange(nextIds.join(","));
        // resolve labels
        if (target && nextIds.length) {
          const rows = await autocompleteResource(demo, target, { q: "", limit: 50 });
          const map = new Map(rows.map((r) => [String(r.value), r.label]));
          setSelected(
            nextIds.map((id) => ({
              value: id,
              label: map.get(id) || id,
            })),
          );
        } else {
          setSelected(nextIds.map((id) => ({ value: id, label: id })));
        }
      } catch {
        /* keep draft */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo, resourceName, identity, relation, mode, target]);

  // Keep selected chips in sync when value changes externally
  useEffect(() => {
    setSelected((prev) => {
      const byId = new Map(prev.map((o) => [o.value, o]));
      return ids.map((id) => byId.get(id) || { value: id, label: id });
    });
  }, [ids]);

  useEffect(() => {
    if (!target || readOnly) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        const rows = await autocompleteResource(demo, target, { q: query, limit: 15 });
        setOptions(
          rows
            .map((r) => ({ value: String(r.value), label: r.label }))
            .filter((o) => !ids.includes(o.value)),
        );
      } catch {
        setOptions([]);
      }
    }, 200);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [demo, target, query, readOnly, ids]);

  const add = (opt: Option) => {
    if (ids.includes(opt.value)) return;
    const next = [...ids, opt.value];
    onChange(next.join(","));
    setSelected((s) => [...s, opt]);
    setQuery("");
    setOpen(false);
  };

  const remove = (id: string) => {
    const next = ids.filter((x) => x !== id);
    onChange(next.join(","));
    setSelected((s) => s.filter((o) => o.value !== id));
  };

  const persist = async () => {
    if (!resourceName || !identity || mode === "create") return;
    setBusy(true);
    try {
      await setM2mIds(demo, resourceName, identity, relation, ids);
    } finally {
      setBusy(false);
    }
  };

  return (
    <label
      className={`field${error ? " field-error" : ""}`}
      data-testid={`field-wrap-${column.name}`}
    >
      <span>
        {column.label}
        {column.required ? " *" : ""}
        {target ? ` · M2M → ${target}` : " · M2M"}
      </span>
      <div className="m2m-widget" data-testid={`m2m-widget-${column.name}`}>
        <div className="filter-chips" style={{ marginBottom: 8 }}>
          {selected.map((o) => (
            <button
              key={o.value}
              type="button"
              className="filter-chip"
              data-testid={`m2m-chip-${o.value}`}
              disabled={readOnly}
              onClick={() => !readOnly && remove(o.value)}
              title={readOnly ? o.label : "Remove"}
            >
              <span className="filter-chip-label">{o.label}</span>
              {!readOnly && <span aria-hidden>×</span>}
            </button>
          ))}
          {selected.length === 0 && (
            <span className="muted" style={{ fontSize: 12 }}>
              None selected
            </span>
          )}
        </div>
        {!readOnly && (
          <div className="fk-typeahead">
            <input
              type="text"
              value={query}
              data-testid={`field-${column.name}`}
              placeholder={target ? `Search ${target}…` : "Search…"}
              aria-invalid={Boolean(error)}
              onFocus={() => setOpen(true)}
              onChange={(e) => {
                setQuery(e.target.value);
                setOpen(true);
              }}
              onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            />
            {open && options.length > 0 && (
              <ul className="fk-options" role="listbox" data-testid={`m2m-options-${column.name}`}>
                {options.map((opt) => (
                  <li key={opt.value}>
                    <button
                      type="button"
                      className="fk-option"
                      data-testid={`m2m-option-${opt.value}`}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => add(opt)}
                    >
                      <strong>{opt.label}</strong>
                      <span className="muted mono">{opt.value}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {!readOnly && identity && mode !== "create" && (
          <button
            type="button"
            className="btn btn-sm"
            style={{ marginTop: 8 }}
            data-testid={`m2m-save-${column.name}`}
            disabled={busy}
            onClick={() => void persist()}
          >
            {busy ? "Saving…" : "Save memberships"}
          </button>
        )}
      </div>
      {error ? (
        <span className="field-error-msg" data-testid={`field-error-${column.name}`}>
          {error}
        </span>
      ) : null}
    </label>
  );
}
