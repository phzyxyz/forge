import { useEffect, useRef, useState } from "react";
import { autocompleteResource } from "../api";
import { useFormContext } from "../FormContext";
import type { FieldWidgetProps } from "./types";

type Option = { value: string | number; label: string };

export function FkWidget({ column, value, readOnly, error, onChange }: FieldWidgetProps) {
  const { demo } = useFormContext();
  const target = column.fk_resource;
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Option[]>([]);
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(value);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    setLabel(value);
  }, [value]);

  useEffect(() => {
    if (!target || readOnly) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        const rows = await autocompleteResource(demo, target, {
          q: query,
          limit: 12,
        });
        setOptions(
          rows.map((r) => ({
            value: r.value as string | number,
            label: r.label,
          })),
        );
      } catch {
        setOptions([]);
      }
    }, 200);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [demo, target, query, readOnly]);

  // Resolve label for current value once
  useEffect(() => {
    if (!target || !value) return;
    let cancelled = false;
    (async () => {
      try {
        const rows = await autocompleteResource(demo, target, { q: String(value), limit: 20 });
        const hit = rows.find((r) => String(r.value) === String(value));
        if (!cancelled && hit) setLabel(hit.label);
      } catch {
        /* keep raw */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [demo, target, value]);

  return (
    <label
      className={`field${error ? " field-error" : ""}`}
      data-testid={`field-wrap-${column.name}`}
    >
      <span>
        {column.label}
        {column.required ? " *" : ""}
        {target ? ` · → ${target}` : ""}
      </span>
      {readOnly ? (
        <input
          type="text"
          value={label || value}
          readOnly
          data-testid={`field-${column.name}`}
        />
      ) : (
        <div className="fk-typeahead" data-testid={`fk-typeahead-${column.name}`}>
          <input
            type="text"
            value={open ? query : label || value}
            data-testid={`field-${column.name}`}
            placeholder={target ? `Search ${target}…` : "Search…"}
            aria-invalid={Boolean(error)}
            aria-autocomplete="list"
            aria-expanded={open}
            onFocus={() => {
              setOpen(true);
              setQuery(label || value || "");
            }}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onBlur={() => {
              window.setTimeout(() => setOpen(false), 150);
            }}
          />
          {open && options.length > 0 && (
            <ul className="fk-options" role="listbox" data-testid={`fk-options-${column.name}`}>
              {options.map((opt) => (
                <li key={String(opt.value)}>
                  <button
                    type="button"
                    role="option"
                    className="fk-option"
                    data-testid={`fk-option-${opt.value}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      onChange(String(opt.value));
                      setLabel(opt.label);
                      setQuery(opt.label);
                      setOpen(false);
                    }}
                  >
                    <strong>{opt.label}</strong>
                    <span className="muted mono">{String(opt.value)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {error ? (
        <span className="field-error-msg" data-testid={`field-error-${column.name}`}>
          {error}
        </span>
      ) : null}
    </label>
  );
}
