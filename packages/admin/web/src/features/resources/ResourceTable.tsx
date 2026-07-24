import { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnSizingState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import type { BulkActionInfo, ResourceSchema } from "../../shared/api/types";
import { cellDisplay, rowToDraft } from "../../shared/lib/format";
import { useShellStore } from "../../shared/stores/shell";
import { IconMore } from "../../shared/ui/Icons";
import { Menu } from "../../shared/ui/Menu";

function isStatusValue(v: unknown): boolean {
  return typeof v === "boolean" || v === "true" || v === "false";
}

export function ResourceTable({
  schema,
  items,
  loading,
  columnVisibility,
  onColumnVisibilityChange,
  columnOrder = [],
  onColumnOrderChange,
  rowActions = [],
  onRowAction,
  onOpenFile,
  onDelete,
  onCopyRow,
}: {
  schema: ResourceSchema;
  items: Record<string, unknown>[];
  loading?: boolean;
  columnVisibility: VisibilityState;
  onColumnVisibilityChange: (v: VisibilityState) => void;
  columnOrder?: string[];
  onColumnOrderChange?: (order: string[]) => void;
  rowActions?: BulkActionInfo[];
  onRowAction?: (
    action: BulkActionInfo,
    identity: string,
    row: Record<string, unknown>,
  ) => void;
  onOpenFile: (key: string) => void;
  onDelete: (id: string) => void;
  onCopyRow: (row: Record<string, unknown>) => void;
}) {
  const { selectedIds, setSelectedIds, openDrawer } = useShellStore();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});

  const dataColNames = useMemo(
    () => schema.columns.filter((x) => !x.hidden).map((c) => c.name),
    [schema],
  );

  const orderedDataCols = useMemo(() => {
    if (!columnOrder.length) return dataColNames;
    const seen = new Set<string>();
    const out: string[] = [];
    for (const id of columnOrder) {
      if (dataColNames.includes(id) && !seen.has(id)) {
        out.push(id);
        seen.add(id);
      }
    }
    for (const id of dataColNames) {
      if (!seen.has(id)) out.push(id);
    }
    return out;
  }, [columnOrder, dataColNames]);

  const columns = useMemo<ColumnDef<Record<string, unknown>>[]>(() => {
    const cols: ColumnDef<Record<string, unknown>>[] = [
      {
        id: "_select",
        size: 44,
        minSize: 44,
        maxSize: 44,
        enableResizing: false,
        enableSorting: false,
        enableHiding: false,
        header: ({ table }) => (
          <input
            type="checkbox"
            aria-label="Select all"
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label="Select row"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
          />
        ),
      },
    ];
    const byName = new Map(schema.columns.map((c) => [c.name, c]));
    for (const colName of orderedDataCols) {
      const c = byName.get(colName);
      if (!c || c.hidden) continue;
      const isStatusCol = c.name === "active" || c.name === "enabled" || c.name === "is_active";
      cols.push({
        id: c.name,
        accessorFn: (row) => row[c.name],
        header: c.label,
        enableHiding: true,
        enableResizing: true,
        size: isStatusCol ? 100 : c.file_kind ? 200 : 160,
        minSize: isStatusCol ? 88 : 80,
        maxSize: 640,
        meta: { status: isStatusCol, file: Boolean(c.file_kind) },
        cell: ({ getValue }) => {
          const v = getValue();
          if (c.file_kind) {
            return (
              <button
                type="button"
                className="file-link"
                data-testid="file-link"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenFile(String(v ?? ""));
                }}
              >
                {cellDisplay(v)}
              </button>
            );
          }
          if (isStatusValue(v) || isStatusCol) {
            const on = v === true || v === "true";
            return (
              <span className={`status-pill ${on ? "status-pill-on" : "status-pill-off"}`}>
                <span className="status-dot" aria-hidden />
                {on ? "Active" : "Off"}
              </span>
            );
          }
          return <span className="cell-text">{cellDisplay(v)}</span>;
        },
      });
    }
    cols.push({
      id: "_actions",
      size: 52,
      minSize: 52,
      maxSize: 52,
      enableResizing: false,
      enableSorting: false,
      enableHiding: false,
      header: "",
      cell: ({ row }) => {
        const id = String(row.original._identity ?? "");
        const regItems = rowActions.map((a) => ({
          type: "item" as const,
          label: a.label,
          danger: Boolean(a.danger),
          onClick: () => onRowAction?.(a, id, row.original),
        }));
        return (
          <Menu
            label="Row actions"
            trigger={
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                aria-label="Row actions"
                data-testid="row-actions"
              >
                <IconMore />
              </button>
            }
            items={[
              {
                type: "item" as const,
                label: "View",
                onClick: () => openDrawer("view", schema.name, id, rowToDraft(row.original)),
              },
              {
                type: "item" as const,
                label: "Edit",
                onClick: () => openDrawer("edit", schema.name, id, rowToDraft(row.original)),
              },
              { type: "sep" as const },
              ...(regItems.length
                ? regItems
                : [
                    {
                      type: "item" as const,
                      label: "Copy JSON",
                      onClick: () => onCopyRow(row.original),
                    },
                  ]),
              { type: "sep" as const },
              {
                type: "item" as const,
                label: "Delete",
                danger: true,
                onClick: () => onDelete(id),
              },
            ]}
          />
        );
      },
    });
    return cols;
  }, [
    schema,
    orderedDataCols,
    openDrawer,
    onOpenFile,
    onDelete,
    onCopyRow,
    rowActions,
    onRowAction,
  ]);

  const rowSelection = useMemo(() => {
    const o: Record<string, boolean> = {};
    for (const id of selectedIds) o[id] = true;
    return o;
  }, [selectedIds]);

  const tanstackOrder = useMemo(
    () => ["_select", ...orderedDataCols, "_actions"],
    [orderedDataCols],
  );

  const table = useReactTable({
    data: items,
    columns,
    state: {
      sorting,
      columnVisibility,
      rowSelection,
      columnSizing,
      columnOrder: tanstackOrder,
    },
    onSortingChange: setSorting,
    onColumnSizingChange: setColumnSizing,
    onColumnOrderChange: (u) => {
      if (!onColumnOrderChange) return;
      const next = typeof u === "function" ? u(tanstackOrder) : u;
      onColumnOrderChange(next.filter((id) => id !== "_select" && id !== "_actions"));
    },
    columnResizeMode: "onChange",
    enableColumnResizing: true,
    onColumnVisibilityChange: (u) => {
      const next = typeof u === "function" ? u(columnVisibility) : u;
      onColumnVisibilityChange(next);
    },
    onRowSelectionChange: (updater) => {
      const next = typeof updater === "function" ? updater(rowSelection) : updater;
      setSelectedIds(Object.keys(next).filter((k) => next[k]));
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row) => String(row._identity ?? ""),
    enableRowSelection: true,
    defaultColumn: {
      minSize: 80,
      size: 160,
      maxSize: 640,
    },
  });

  if (loading) {
    return (
      <div className="table-scroll" style={{ padding: 16, display: "grid", gap: 10 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 36 }} />
        ))}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="empty" style={{ margin: 16 }} data-testid="table-empty">
        <h3>No records yet</h3>
        <p>Create the first {schema.label.toLowerCase()} to populate this table.</p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => openDrawer("create", schema.name)}
        >
          New record
        </button>
      </div>
    );
  }

  const totalWidth = table.getTotalSize();

  return (
    <div className="table-scroll" data-testid="resource-table">
      <table className="data-table" style={{ width: totalWidth, minWidth: "100%" }}>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const canSort =
                  h.column.getCanSort() && h.id !== "_select" && h.id !== "_actions";
                const canResize = h.column.getCanResize();
                return (
                  <th
                    key={h.id}
                    className={[
                      canSort ? "sortable" : "",
                      h.id === "_select" ? "col-check" : "",
                      h.id === "_actions" ? "col-actions" : "",
                      (h.column.columnDef.meta as { status?: boolean } | undefined)?.status
                        ? "col-status"
                        : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{ width: h.getSize(), position: "relative" }}
                  >
                    <div
                      className="th-inner"
                      onClick={canSort ? h.column.getToggleSortingHandler() : undefined}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {{ asc: " ↑", desc: " ↓" }[h.column.getIsSorted() as string] ?? null}
                    </div>
                    {canResize && (
                      <div
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize ${String(h.column.columnDef.header ?? h.id)} column`}
                        onMouseDown={h.getResizeHandler()}
                        onTouchStart={h.getResizeHandler()}
                        onDoubleClick={() => h.column.resetSize()}
                        className={`col-resizer${h.column.getIsResizing() ? " is-resizing" : ""}`}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={row.getIsSelected() ? "checked" : ""}
              data-testid="table-row"
              onClick={() => openDrawer("view", schema.name, row.id, rowToDraft(row.original))}
            >
              {row.getVisibleCells().map((cell) => {
                const meta = cell.column.columnDef.meta as { status?: boolean } | undefined;
                return (
                  <td
                    key={cell.id}
                    className={[
                      cell.column.id === "_actions" ? "col-actions" : "",
                      cell.column.id === "_select" ? "col-check" : "",
                      meta?.status ? "col-status" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{ width: cell.column.getSize() }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
