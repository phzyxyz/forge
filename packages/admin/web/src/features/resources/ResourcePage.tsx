import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { VisibilityState } from "@tanstack/react-table";
import type { BulkActionInfo, ResourceSchema } from "../../shared/api/types";
import { downloadBlob, downloadText } from "../../shared/lib/format";
import { useActivityStore, useShellStore } from "../../shared/stores/shell";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { IconMore, IconPlus } from "../../shared/ui/Icons";
import { Menu, type MenuItem } from "../../shared/ui/Menu";
import { FilePreview } from "../media/FilePreview";
import {
  copyResource,
  deleteRecord,
  exportResource,
  listAdminActions,
  listRecords,
  runAdminAction,
} from "./api";
import { FilterBar } from "./FilterBar";
import { RecordDrawer } from "./RecordDrawer";
import { ResourceTable } from "./ResourceTable";
import { clearSavedView, loadSavedView, saveView } from "./savedViews";

export function ResourcePage({
  name,
  resources,
  demo,
}: {
  name: string;
  resources: ResourceSchema[];
  demo: boolean;
}) {
  const schema = resources.find((r) => r.name === name);
  const { openDrawer, selectedIds, setSelectedIds, toast, globalSearch, setGlobalSearch } =
    useShellStore();
  const pushActivity = useActivityStore((s) => s.push);
  const qc = useQueryClient();
  const saved = useMemo(() => loadSavedView(name), [name]);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(saved?.pageSize ?? 50);
  const [search, setSearch] = useState(globalSearch);
  const [filters, setFilters] = useState<Record<string, string>>(saved?.filters ?? {});
  const [pagination, setPagination] = useState<"offset" | "keyset">(
    saved?.pagination ?? "keyset",
  );
  const [cursor, setCursor] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    action: BulkActionInfo;
    identities: string[];
  } | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    saved?.columnVisibility ?? {},
  );
  const [columnOrder, setColumnOrder] = useState<string[]>(saved?.columnOrder ?? []);

  // Reset resource-local state when switching resources
  useEffect(() => {
    const v = loadSavedView(name);
    setSearch(globalSearch);
    setPage(1);
    setCursor(null);
    setFilters(v?.filters ?? {});
    setPageSize(v?.pageSize ?? 50);
    setPagination(v?.pagination ?? "keyset");
    setColumnVisibility(v?.columnVisibility ?? {});
    setColumnOrder(v?.columnOrder ?? []);
    setSelectedIds([]);
  }, [name]); // eslint-disable-line react-hooks/exhaustive-deps -- intentional resource switch

  useEffect(() => {
    const t = window.setTimeout(() => setGlobalSearch(search), 250);
    return () => window.clearTimeout(t);
  }, [search, setGlobalSearch]);

  // Persist view
  useEffect(() => {
    if (!schema) return;
    saveView(name, {
      filters,
      columnVisibility: columnVisibility as Record<string, boolean>,
      columnOrder,
      pageSize,
      pagination,
    });
  }, [name, schema, filters, columnVisibility, columnOrder, pageSize, pagination]);

  const listQ = useQuery({
    queryKey: ["list", name, page, search, pageSize, filters, pagination, cursor],
    queryFn: () =>
      listRecords(demo, name, {
        page,
        page_size: pageSize,
        search: search || undefined,
        filters: Object.keys(filters).length ? filters : undefined,
        pagination,
        cursor: pagination === "keyset" ? cursor : undefined,
      }),
    enabled: !!schema,
  });

  const actionsQ = useQuery({
    queryKey: ["admin-actions", name],
    queryFn: () => listAdminActions(demo, name),
    enabled: !!schema,
  });

  const delMany = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) await deleteRecord(demo, name, id);
    },
    onSuccess: (_d, ids) => {
      qc.invalidateQueries({ queryKey: ["list", name] });
      setSelectedIds([]);
      setPendingDelete(null);
      toast(`Deleted ${ids.length} record(s)`);
      pushActivity(`Deleted ${ids.length} from ${schema?.label ?? name}`);
    },
    onError: (e: Error) => toast(e.message || "Delete failed", "error"),
  });

  const executeAction = useCallback(
    async (action: BulkActionInfo, identities: string[]) => {
      if (action.client) {
        const kind = action.client || "";
        setActionBusy(true);
        try {
          if (kind === "export:csv") {
            const text = (await exportResource(demo, name, "csv", search || undefined)) as string;
            downloadText(`${name}.csv`, text, "text/csv");
            toast("Exported CSV");
            pushActivity(`Exported ${name} CSV`);
          } else if (kind === "export:json") {
            const text = (await exportResource(demo, name, "json", search || undefined)) as string;
            downloadText(`${name}.json`, text, "application/json");
            toast("Exported JSON");
            pushActivity(`Exported ${name} JSON`);
          } else if (kind === "export:xlsx") {
            const blob = (await exportResource(demo, name, "xlsx", search || undefined)) as Blob;
            downloadBlob(`${name}.xlsx`, blob);
            toast("Exported Excel");
            pushActivity(`Exported ${name} Excel`);
          } else if (kind === "copy:json") {
            const payload = await copyResource(
              demo,
              name,
              "json",
              identities.length ? identities : undefined,
            );
            await navigator.clipboard.writeText(payload);
            toast(identities.length ? "Copied selection JSON" : "Copied JSON");
          } else {
            toast(`Unknown client action ${kind}`, "error");
          }
        } catch (e) {
          toast((e as Error).message, "error");
        } finally {
          setActionBusy(false);
        }
        return;
      }
      setActionBusy(true);
      try {
        const res = await runAdminAction(demo, name, action.name, identities);
        qc.invalidateQueries({ queryKey: ["list", name] });
        setSelectedIds([]);
        setPendingAction(null);
        toast(`${res.action}: ${res.updated ?? 0} updated`);
        pushActivity(`Action ${res.action} on ${schema?.label ?? name}`);
      } catch (e) {
        toast((e as Error).message || "Action failed", "error");
      } finally {
        setActionBusy(false);
      }
    },
    [demo, name, search, toast, pushActivity, qc, schema?.label, setSelectedIds],
  );

  const requestAction = useCallback(
    (action: BulkActionInfo, identities: string[]) => {
      if (action.confirm) setPendingAction({ action, identities });
      else void executeAction(action, identities);
    },
    [executeAction],
  );

  const items = listQ.data?.items ?? [];
  const total = listQ.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasMoreKeyset = Boolean(listQ.data?.has_more);

  const dataCols = useMemo(
    () => (schema?.columns ?? []).filter((c) => !c.hidden).map((c) => c.name),
    [schema],
  );

  const catalog = actionsQ.data ?? [];
  const globalActions = catalog.filter((a) => a.scope === "global");
  const bulkActions = catalog.filter((a) => a.scope === "bulk" && !a.client);
  const bulkClientActions = catalog.filter((a) => a.scope === "bulk" && a.client);
  const rowActions = catalog.filter((a) => a.scope === "row");

  const overflowItems = useMemo(() => {
    if (!schema) return [];
    const moveCol = (col: string, dir: -1 | 1) => {
      setColumnOrder((prev) => {
        const base = prev.length ? [...prev] : [...dataCols];
        for (const c of dataCols) {
          if (!base.includes(c)) base.push(c);
        }
        const i = base.indexOf(col);
        if (i < 0) return base;
        const j = i + dir;
        if (j < 0 || j >= base.length) return base;
        const next = [...base];
        [next[i], next[j]] = [next[j], next[i]];
        return next;
      });
    };
    const items: MenuItem[] = [];
    if (globalActions.length) {
      items.push({ type: "label", label: "Actions" });
      for (const a of globalActions) {
        items.push({
          type: "item",
          label: a.label,
          onClick: () => requestAction(a, []),
        });
      }
      items.push({ type: "sep" });
    }
    items.push({ type: "label", label: "Columns" });
    for (const col of dataCols) {
      items.push({
        type: "item",
        label: `${columnVisibility[col] === false ? "Show" : "Hide"} ${col}`,
        onClick: () =>
          setColumnVisibility((v) => ({
            ...v,
            [col]: v[col] === false ? true : false,
          })),
      });
    }
    items.push({ type: "sep" }, { type: "label", label: "Column order" });
    for (const col of dataCols) {
      items.push({
        type: "item",
        label: `Move left: ${col}`,
        onClick: () => moveCol(col, -1),
      });
    }
    for (const col of dataCols) {
      items.push({
        type: "item",
        label: `Move right: ${col}`,
        onClick: () => moveCol(col, 1),
      });
    }
    items.push(
      { type: "sep" },
      {
        type: "item",
        label: "Reset saved view",
        onClick: () => {
          clearSavedView(name);
          setFilters({});
          setColumnVisibility({});
          setColumnOrder([]);
          setPagination("offset");
          setPageSize(50);
          setCursor(null);
          setPage(1);
          toast("Saved view cleared");
        },
      },
      {
        type: "item",
        label: "Refresh",
        onClick: () => qc.invalidateQueries({ queryKey: ["list", name] }),
      },
    );
    return items;
  }, [schema, name, toast, qc, dataCols, columnVisibility, globalActions, requestAction]);

  if (!schema) {
    return (
      <div className="page">
        <div className="alert error">Unknown resource “{name}”.</div>
      </div>
    );
  }

  return (
    <div className="page" data-testid={`resource-page-${name}`}>
      <div className="page-header">
        <div>
          <h1 data-testid="resource-title">{schema.label}</h1>
          <p className="sub">
            {total} record{total === 1 ? "" : "s"}
            {schema.primary_key.length > 1 ? " · composite primary key" : ""}
            {Object.keys(filters).length ? ` · ${Object.keys(filters).length} filter(s)` : ""}
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn btn-primary"
            data-testid="new-record"
            onClick={() => openDrawer("create", name)}
            disabled={schema.readonly}
          >
            <IconPlus />
            New record
          </button>
          <Menu
            label="More actions"
            trigger={
              <button
                type="button"
                className="btn btn-icon"
                aria-label="More actions"
                data-testid="overflow-menu"
              >
                <IconMore />
              </button>
            }
            items={overflowItems}
          />
        </div>
      </div>

      {listQ.isError && (
        <div className="alert error">
          <span>{(listQ.error as Error).message || "Failed to load"}</span>
          <button type="button" className="btn btn-sm" onClick={() => listQ.refetch()}>
            Retry
          </button>
        </div>
      )}

      <div className="table-panel">
        <div className="table-toolbar">
          <input
            className="search"
            id="resource-search"
            data-testid="resource-search"
            placeholder="Search records…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
              setCursor(null);
            }}
            aria-label="Search records"
          />
          <FilterBar
            schema={schema}
            filters={filters}
            onChange={(next) => {
              setFilters(next);
              setPage(1);
              setCursor(null);
            }}
          />
          <label className="muted toolbar-keyset">
            <input
              type="checkbox"
              data-testid="keyset-toggle"
              checked={pagination === "keyset"}
              onChange={(e) => {
                setPagination(e.target.checked ? "keyset" : "offset");
                setPage(1);
                setCursor(null);
              }}
            />
            Keyset
          </label>
          <span className="muted toolbar-page-meta" data-testid="page-indicator">
            {pagination === "keyset"
              ? hasMoreKeyset
                ? "Keyset · more available"
                : "Keyset · end"
              : `Page ${page} of ${totalPages}`}
          </span>
        </div>

        <ResourceTable
          schema={schema}
          items={items}
          loading={listQ.isLoading}
          columnVisibility={columnVisibility}
          onColumnVisibilityChange={setColumnVisibility}
          columnOrder={columnOrder}
          onColumnOrderChange={setColumnOrder}
          rowActions={rowActions}
          onRowAction={(action, id, row) => {
            if (action.client === "copy:json") {
              void navigator.clipboard
                .writeText(JSON.stringify(row, null, 2))
                .then(() => toast("Row JSON copied"))
                .catch((e: Error) => toast(e.message, "error"));
              return;
            }
            requestAction(action, [id]);
          }}
          onOpenFile={(key) => setPreviewKey(key)}
          onDelete={(id) => setPendingDelete([id])}
          onCopyRow={async (row) => {
            await navigator.clipboard.writeText(JSON.stringify(row, null, 2));
            toast("Row JSON copied");
          }}
        />

        <div className="table-footer">
          <div className="pager">
            <label className="muted">
              Rows{" "}
              <select
                className="input"
                style={{ height: 30, width: 72, marginLeft: 6 }}
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                  setCursor(null);
                }}
              >
                {[25, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="pager">
            {pagination === "keyset" ? (
              <>
                <button
                  type="button"
                  className="btn btn-sm"
                  data-testid="pager-reset"
                  disabled={!cursor}
                  onClick={() => setCursor(null)}
                >
                  First
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  data-testid="pager-next"
                  disabled={!hasMoreKeyset || !listQ.data?.next_cursor}
                  onClick={() => setCursor(listQ.data?.next_cursor ?? null)}
                >
                  Next
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-sm"
                  data-testid="pager-prev"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  data-testid="pager-next"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {selectedIds.length > 0 && (
        <div className="bulk-bar" role="toolbar" aria-label="Bulk actions" data-testid="bulk-bar">
          <strong>{selectedIds.length} selected</strong>
          {actionBusy && (
            <span className="muted" data-testid="action-progress">
              Running…
            </span>
          )}
          {bulkClientActions.map((a) => (
            <button
              key={`c-${a.name}`}
              type="button"
              className="btn btn-sm"
              data-testid={`bulk-action-${a.name}`}
              disabled={actionBusy}
              onClick={() => requestAction(a, selectedIds)}
            >
              {a.label}
            </button>
          ))}
          {bulkActions.map((a) => (
            <button
              key={a.name}
              type="button"
              className={`btn btn-sm${a.danger ? " btn-danger" : ""}`}
              data-testid={`bulk-action-${a.name}`}
              disabled={actionBusy}
              onClick={() => requestAction(a, selectedIds)}
            >
              {a.label}
            </button>
          ))}
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={() => setPendingDelete([...selectedIds])}
          >
            Delete
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setSelectedIds([])}>
            Clear
          </button>
        </div>
      )}

      <RecordDrawer schema={schema} demo={demo} />

      {pendingDelete && (
        <ConfirmDialog
          title={pendingDelete.length > 1 ? "Delete records?" : "Delete record?"}
          body={`This will permanently delete ${pendingDelete.length} record(s) from ${schema.label}.`}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => delMany.mutate(pendingDelete)}
        />
      )}

      {pendingAction && (
        <ConfirmDialog
          title={`Run “${pendingAction.action.label}”?`}
          body={
            pendingAction.action.description ||
            `Apply ${pendingAction.action.label} to ${pendingAction.identities.length || "resource"} target(s).`
          }
          confirmLabel="Confirm"
          danger={Boolean(pendingAction.action.danger)}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => {
            const p = pendingAction;
            setPendingAction(null);
            void executeAction(p.action, p.identities);
          }}
        />
      )}

      {previewKey && (
        <FilePreview fileKey={previewKey} demo={demo} onClose={() => setPreviewKey(null)} />
      )}
    </div>
  );
}
