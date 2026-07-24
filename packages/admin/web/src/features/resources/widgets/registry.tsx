import type { ColumnSchema } from "../../../shared/api/types";
import { FkWidget } from "./FkWidget";
import { M2mWidget } from "./M2mWidget";
import type { FieldWidget, FieldWidgetProps, WidgetName } from "./types";

function FieldShell({
  column,
  error,
  children,
  row,
}: {
  column: ColumnSchema;
  error?: string;
  children: React.ReactNode;
  row?: boolean;
}) {
  return (
    <label
      className={`field${error ? " field-error" : ""}${row ? " field-row" : ""}`}
      data-testid={`field-wrap-${column.name}`}
    >
      <span>
        {column.label}
        {column.required ? " *" : ""}
        {column.file_kind ? " · file" : ""}
      </span>
      {children}
      {error ? (
        <span className="field-error-msg" data-testid={`field-error-${column.name}`}>
          {error}
        </span>
      ) : null}
    </label>
  );
}

const TextWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <input
      type="text"
      value={value}
      readOnly={readOnly}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      placeholder={column.label}
      aria-invalid={Boolean(error)}
    />
  </FieldShell>
);

const NumberWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <input
      type="number"
      value={value}
      readOnly={readOnly}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      placeholder={column.label}
      aria-invalid={Boolean(error)}
    />
  </FieldShell>
);

const BoolWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => {
  const checked = value === "true" || value === "1" || value === "True";
  return (
    <FieldShell column={column} error={error} row>
      <input
        type="checkbox"
        checked={checked}
        disabled={readOnly}
        data-testid={`field-${column.name}`}
        onChange={(e) => onChange(e.target.checked ? "true" : "false")}
        aria-invalid={Boolean(error)}
      />
    </FieldShell>
  );
};

const DateWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <input
      type="date"
      value={value ? value.slice(0, 10) : ""}
      readOnly={readOnly}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      aria-invalid={Boolean(error)}
    />
  </FieldShell>
);

const DateTimeWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => {
  // datetime-local wants YYYY-MM-DDTHH:mm
  let local = value;
  if (value && value.includes(" ") && !value.includes("T")) {
    local = value.replace(" ", "T").slice(0, 16);
  } else if (value && value.length >= 16) {
    local = value.slice(0, 16);
  }
  return (
    <FieldShell column={column} error={error}>
      <input
        type="datetime-local"
        value={local}
        readOnly={readOnly}
        data-testid={`field-${column.name}`}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
      />
    </FieldShell>
  );
};

const TextareaWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <textarea
      value={value}
      readOnly={readOnly}
      rows={4}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      placeholder={column.label}
      aria-invalid={Boolean(error)}
    />
  </FieldShell>
);

const JsonWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <textarea
      className="mono"
      value={value}
      readOnly={readOnly}
      rows={6}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      placeholder="{}"
      aria-invalid={Boolean(error)}
    />
  </FieldShell>
);

const FileWidget: FieldWidget = ({ column, value, readOnly, error, onChange }) => (
  <FieldShell column={column} error={error}>
    <input
      type="text"
      value={value}
      readOnly={readOnly}
      data-testid={`field-${column.name}`}
      onChange={(e) => onChange(e.target.value)}
      placeholder="storage key / path"
      aria-invalid={Boolean(error)}
    />
    <span className="muted" style={{ fontSize: 11 }}>
      File key (upload via Media)
    </span>
  </FieldShell>
);

const REGISTRY: Record<string, FieldWidget> = {
  text: TextWidget,
  number: NumberWidget,
  bool: BoolWidget,
  date: DateWidget,
  datetime: DateTimeWidget,
  textarea: TextareaWidget,
  json: JsonWidget,
  file: FileWidget,
  fk: FkWidget,
  m2m: M2mWidget,
};

/** Allow plugins / tests to register custom widgets. */
export function registerWidget(name: WidgetName, widget: FieldWidget): void {
  REGISTRY[name] = widget;
}

export function resolveWidget(column: ColumnSchema): FieldWidget {
  const name = column.widget || inferWidgetName(column);
  return REGISTRY[name] || TextWidget;
}

export function inferWidgetName(column: ColumnSchema): WidgetName {
  if (column.widget) return column.widget;
  if (column.fk_resource) return "fk";
  if (column.file_kind) return "file";
  if (column.filter_type === "bool") return "bool";
  if (column.filter_type === "number") return "number";
  return "text";
}

export function renderField(props: FieldWidgetProps) {
  const Widget = resolveWidget(props.column);
  return <Widget {...props} />;
}
