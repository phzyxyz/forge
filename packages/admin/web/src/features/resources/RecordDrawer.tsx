import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../shared/api/client";
import type { ColumnSchema, ResourceSchema } from "../../shared/api/types";
import { coerceBody } from "../../shared/lib/format";
import { useActivityStore, useShellStore } from "../../shared/stores/shell";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { IconX } from "../../shared/ui/Icons";
import { createRecord, deleteRecord, setM2mIds, updateRecord } from "./api";
import { FormProvider } from "./FormContext";
import { RelationPanel } from "./RelationPanel";
import { renderField } from "./widgets/registry";
import { M2mWidget } from "./widgets/M2mWidget";

function columnsForFieldset(
  schema: ResourceSchema,
  fieldNames: string[],
): ColumnSchema[] {
  const byName = new Map(schema.columns.map((c) => [c.name, c]));
  return fieldNames
    .map((n) => byName.get(n))
    .filter((c): c is ColumnSchema => Boolean(c) && !c!.hidden);
}

export function RecordDrawer({
  schema,
  demo,
}: {
  schema: ResourceSchema | undefined;
  demo: boolean;
}) {
  const { drawer, closeDrawer, setDraft, toast, openDrawer } = useShellStore();
  const pushActivity = useActivityStore((s) => s.push);
  const qc = useQueryClient();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingClose, setPendingClose] = useState(false);
  const baselineRef = useRef<string>("");

  // Snapshot baseline when drawer opens / mode changes
  useEffect(() => {
    if (drawer.mode && drawer.resource) {
      baselineRef.current = JSON.stringify(drawer.draft);
      setFieldErrors({});
      setFormError(null);
      setPendingClose(false);
    }
  }, [drawer.mode, drawer.resource, drawer.identity]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(() => {
    if (!drawer.mode || drawer.mode === "view") return false;
    return JSON.stringify(drawer.draft) !== baselineRef.current;
  }, [drawer.draft, drawer.mode]);

  const requestClose = () => {
    if (dirty) setPendingClose(true);
    else closeDrawer();
  };

  const save = useMutation({
    mutationFn: async () => {
      if (!drawer.resource || !drawer.mode) throw new Error("Nothing to save");
      // strip virtual m2m draft keys from main body (values stay string for coerceBody)
      const draftClean: Record<string, string> = {};
      for (const [k, v] of Object.entries(drawer.draft)) {
        if (k.startsWith("_m2m_")) continue;
        draftClean[k] = v == null ? "" : String(v);
      }
      const body = coerceBody(draftClean);
      let identity = drawer.identity;
      if (drawer.mode === "create") {
        const created = await createRecord(demo, drawer.resource, body);
        identity = String(
          (created as { _identity?: string })._identity ||
            (created as { id?: string | number }).id ||
            "",
        );
      } else {
        if (!drawer.identity) throw new Error("Missing identity");
        await updateRecord(demo, drawer.resource, drawer.identity, body);
      }
      // persist M2M after parent exists
      if (identity && schema?.relations) {
        for (const rel of schema.relations) {
          if (rel.kind !== "m2m") continue;
          const raw = String(drawer.draft[`_m2m_${rel.name}`] ?? "");
          const ids = raw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          await setM2mIds(demo, drawer.resource, identity, rel.name, ids);
        }
      }
      return { identity };
    },
    onSuccess: () => {
      if (drawer.resource) {
        qc.invalidateQueries({ queryKey: ["list", drawer.resource] });
        qc.invalidateQueries({ queryKey: ["relation", drawer.resource] });
      }
      toast(drawer.mode === "create" ? "Record created" : "Record saved");
      pushActivity(
        drawer.mode === "create"
          ? `Created in ${schema?.label ?? drawer.resource}`
          : `Updated ${schema?.label ?? drawer.resource} ${drawer.identity}`,
      );
      setFieldErrors({});
      setFormError(null);
      baselineRef.current = JSON.stringify(drawer.draft);
      closeDrawer();
    },
    onError: (e: Error) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) {
        setFieldErrors(e.fields);
        setFormError(e.message || "Validation failed");
        toast("Fix highlighted fields", "error");
        return;
      }
      setFormError(e.message || "Save failed");
      toast(e.message || "Save failed", "error");
    },
  });

  const del = useMutation({
    mutationFn: async () => {
      if (!drawer.resource || !drawer.identity) throw new Error("Nothing to delete");
      await deleteRecord(demo, drawer.resource, drawer.identity);
    },
    onSuccess: () => {
      if (drawer.resource) qc.invalidateQueries({ queryKey: ["list", drawer.resource] });
      toast("Record deleted");
      pushActivity(`Deleted ${schema?.label ?? drawer.resource} ${drawer.identity}`);
      closeDrawer();
    },
    onError: (e: Error) => toast(e.message || "Delete failed", "error"),
  });

  const open = Boolean(drawer.mode && drawer.resource && schema);
  if (!open || !schema || !drawer.mode) return null;

  const pk = new Set(schema.primary_key);
  const fieldsets =
    schema.fieldsets && schema.fieldsets.length
      ? schema.fieldsets
      : [
          {
            name: "fields",
            label: "Fields",
            fields: schema.columns.filter((c) => !c.hidden).map((c) => c.name),
          },
        ];

  const title =
    drawer.mode === "create"
      ? `New ${schema.label}`
      : drawer.mode === "edit"
        ? `Edit ${schema.label}`
        : schema.label;

  const renderColumn = (c: ColumnSchema) => {
    const isPk = pk.has(c.name);
    // PK-auto: hide autoincrement on create (server allocates id)
    if (drawer.mode === "create" && c.autoincrement) {
      return null;
    }
    const raw = drawer.draft[c.name] ?? "";
    const readOnly =
      drawer.mode === "view" ||
      (drawer.mode === "edit" && (Boolean(c.readonly) || isPk)) ||
      (drawer.mode === "create" && Boolean(c.readonly) && !isPk);
    const error =
      fieldErrors[c.name] ||
      fieldErrors[`${schema.name}.${c.name}`] ||
      undefined;

    // PK badge on label via required/name; prepend PK hint through label clone
    const col: ColumnSchema = isPk ? { ...c, label: `${c.label} · PK` } : c;

    return (
      <div key={c.name}>
        {renderField({
          column: col,
          value: String(raw),
          readOnly,
          error,
          onChange: (v) => {
            setFieldErrors((fe) => {
              if (!fe[c.name] && !fe[`${schema.name}.${c.name}`]) return fe;
              const next = { ...fe };
              delete next[c.name];
              delete next[`${schema.name}.${c.name}`];
              return next;
            });
            setDraft({ ...drawer.draft, [c.name]: v });
          },
        })}
      </div>
    );
  };

  return (
    <FormProvider
      demo={demo}
      resourceName={drawer.resource || undefined}
      identity={drawer.identity || undefined}
      mode={drawer.mode}
    >
      <div className="overlay" onClick={requestClose} data-testid="drawer-overlay" />
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        data-testid="record-drawer"
        data-dirty={dirty ? "1" : "0"}
      >
        <div className="drawer-header">
          <div>
            <h2 data-testid="drawer-title">{title}</h2>
            {drawer.identity && (
              <p className="muted mono" style={{ margin: "6px 0 0" }}>
                {drawer.identity}
                {schema.primary_key.length > 1 ? " · composite key" : ""}
              </p>
            )}
            {dirty && (
              <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }} data-testid="dirty-badge">
                Unsaved changes
              </p>
            )}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            onClick={requestClose}
            aria-label="Close"
            data-testid="drawer-close"
          >
            <IconX />
          </button>
        </div>
        <div className="drawer-body">
          {formError && (
            <div className="alert error" data-testid="form-error" style={{ marginBottom: 12 }}>
              {formError}
            </div>
          )}
          {fieldsets.map((fs) => {
            const cols = columnsForFieldset(schema, fs.fields);
            if (!cols.length) return null;
            return (
              <section
                key={fs.name}
                className="fieldset"
                data-testid={`fieldset-${fs.name}`}
              >
                <h3 className="fieldset-title">{fs.label}</h3>
                <div className="fieldset-body">{cols.map(renderColumn)}</div>
              </section>
            );
          })}
          {/* Diamond D4.5 — M2M multi-select editors (edit/create) */}
          {(drawer.mode === "edit" || drawer.mode === "create") &&
            (schema.relations || [])
              .filter((r) => r.kind === "m2m")
              .map((rel) => {
                const col: ColumnSchema = {
                  name: `_m2m_${rel.name}`,
                  label: rel.label,
                  widget: "m2m",
                  m2m_resource: rel.resource,
                  m2m_relation: rel.name,
                  fk_resource: rel.resource,
                };
                const key = `_m2m_${rel.name}`;
                const raw = String(drawer.draft[key] ?? "");
                return (
                  <section
                    key={rel.name}
                    className="fieldset"
                    data-testid={`m2m-fieldset-${rel.name}`}
                  >
                    <h3 className="fieldset-title">Related · {rel.label}</h3>
                    <div className="fieldset-body">
                      <M2mWidget
                        column={col}
                        value={raw}
                        readOnly={false}
                        onChange={(v) => setDraft({ ...drawer.draft, [key]: v })}
                      />
                    </div>
                  </section>
                );
              })}
          {drawer.mode === "view" && drawer.identity && schema.relations && schema.relations.length > 0 && (
            <RelationPanel
              parent={schema}
              identity={drawer.identity}
              relations={schema.relations}
              demo={demo}
            />
          )}
        </div>
        <div className="drawer-footer">
          {drawer.mode === "view" && (
            <>
              <button
                type="button"
                className="btn btn-danger"
                data-testid="drawer-delete"
                onClick={() => {
                  if (window.confirm("Delete this record?")) del.mutate();
                }}
              >
                Delete
              </button>
              <button
                type="button"
                className="btn btn-primary"
                data-testid="drawer-edit"
                onClick={() => openDrawer("edit", drawer.resource!, drawer.identity, drawer.draft)}
              >
                Edit
              </button>
            </>
          )}
          {(drawer.mode === "create" || drawer.mode === "edit") && (
            <>
              <button type="button" className="btn btn-ghost" onClick={requestClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                data-testid="drawer-save"
                disabled={save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Saving…" : drawer.mode === "create" ? "Create" : "Save"}
              </button>
            </>
          )}
        </div>
      </aside>

      {pendingClose && (
        <ConfirmDialog
          title="Discard unsaved changes?"
          body="You have unsaved edits. Close and lose them?"
          confirmLabel="Discard"
          danger
          onCancel={() => setPendingClose(false)}
          onConfirm={() => {
            setPendingClose(false);
            closeDrawer();
          }}
        />
      )}
    </FormProvider>
  );
}
