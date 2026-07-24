import type {
  BulkActionInfo,
  ListResult,
  MetaInfo,
  ResourceSchema,
} from "../../shared/api/types";
import { ApiError } from "../../shared/api/client";

export const DEMO_META: MetaInfo = {
  theme: "stellar-dark",
  themes: ["magical-white", "stellar-dark", "system-ambient"],
  prefix: "/admin",
  version: "0.1.0-demo",
  branding: {
    site_title: "AdminBoard",
    header_title: "AdminBoard",
    header_subtitle: "Phzyx",
    show_powered_by: true,
  },
};

export const DEMO_RESOURCES: ResourceSchema[] = [
  {
    name: "users",
    label: "Users",
    primary_key: ["id"],
    searchable: ["email", "name"],
    filterable: ["email", "name", "active"],
    relations: [
      {
        name: "memberships",
        label: "Memberships",
        resource: "memberships",
        foreign_key: "user_id",
        kind: "has_many",
      },
      {
        name: "posts",
        label: "Posts",
        resource: "posts",
        foreign_key: "author_id",
        kind: "has_many",
      },
    ],
    fieldsets: [
      { name: "identity", label: "Identity", fields: ["id"] },
      {
        name: "details",
        label: "Details",
        fields: ["email", "name", "active", "joined", "notes"],
      },
    ],
    columns: [
      {
        name: "id",
        label: "Id",
        readonly: true,
        sortable: true,
        widget: "number",
        required: true,
      },
      {
        name: "email",
        label: "Email",
        searchable: true,
        sortable: true,
        filterable: true,
        filter_type: "text",
        widget: "text",
        required: true,
      },
      {
        name: "name",
        label: "Name",
        searchable: true,
        sortable: true,
        filterable: true,
        filter_type: "text",
        widget: "text",
        required: true,
      },
      {
        name: "active",
        label: "Active",
        sortable: true,
        filterable: true,
        filter_type: "bool",
        widget: "bool",
      },
      {
        name: "joined",
        label: "Joined",
        sortable: true,
        widget: "date",
      },
      {
        name: "notes",
        label: "Notes",
        widget: "textarea",
      },
    ],
  },
  {
    name: "memberships",
    label: "Memberships",
    primary_key: ["org_id", "user_id"],
    searchable: ["role"],
    filterable: ["role"],
    fieldsets: [
      { name: "identity", label: "Identity", fields: ["org_id", "user_id"] },
      { name: "details", label: "Details", fields: ["role"] },
    ],
    columns: [
      {
        name: "org_id",
        label: "Org",
        readonly: true,
        sortable: true,
        widget: "number",
        required: true,
      },
      {
        name: "user_id",
        label: "User",
        readonly: true,
        sortable: true,
        widget: "fk",
        required: true,
        fk_resource: "users",
        fk_column: "id",
        fk_label_fields: ["name", "email"],
      },
      {
        name: "role",
        label: "Role",
        searchable: true,
        sortable: true,
        filterable: true,
        filter_type: "text",
        widget: "text",
      },
    ],
  },
  {
    name: "assets",
    label: "Assets",
    primary_key: ["id"],
    searchable: ["title", "path"],
    filterable: ["title"],
    fieldsets: [
      { name: "identity", label: "Identity", fields: ["id"] },
      { name: "details", label: "Details", fields: ["title", "path"] },
    ],
    columns: [
      {
        name: "id",
        label: "Id",
        readonly: true,
        sortable: true,
        widget: "number",
        required: true,
      },
      {
        name: "title",
        label: "Title",
        searchable: true,
        sortable: true,
        filterable: true,
        filter_type: "text",
        widget: "text",
        required: true,
      },
      {
        name: "path",
        label: "Path",
        searchable: true,
        file_kind: "file",
        widget: "file",
        required: true,
      },
    ],
  },
  {
    name: "posts",
    label: "Posts",
    primary_key: ["id"],
    searchable: ["title", "body"],
    filterable: ["title"],
    fieldsets: [
      { name: "identity", label: "Identity", fields: ["id"] },
      { name: "details", label: "Details", fields: ["title", "author_id", "body"] },
    ],
    columns: [
      {
        name: "id",
        label: "Id",
        readonly: true,
        sortable: true,
        widget: "number",
        required: true,
      },
      {
        name: "title",
        label: "Title",
        searchable: true,
        sortable: true,
        filterable: true,
        filter_type: "text",
        widget: "text",
        required: true,
      },
      {
        name: "author_id",
        label: "Author",
        widget: "fk",
        required: true,
        fk_resource: "users",
        fk_column: "id",
        fk_label_fields: ["name", "email"],
      },
      {
        name: "body",
        label: "Body",
        widget: "textarea",
      },
    ],
  },
];

function withIdentity(row: Record<string, unknown>, pk: string[]) {
  return { ...row, _identity: pk.map((k) => String(row[k] ?? "")).join("|") };
}

const store: Record<string, Record<string, unknown>[]> = {
  users: [
    {
      id: 1,
      email: "ops@phzyx.xyz",
      name: "Ops",
      active: true,
      joined: "2024-01-15",
      notes: "Operations lead",
    },
    {
      id: 2,
      email: "dev@phzyx.xyz",
      name: "Dev",
      active: true,
      joined: "2024-06-01",
      notes: "",
    },
    {
      id: 3,
      email: "guest@phzyx.xyz",
      name: "Guest",
      active: false,
      joined: null,
      notes: "Inactive guest",
    },
  ].map((r) => withIdentity(r, ["id"])),
  memberships: [
    { org_id: 1, user_id: 1, role: "admin" },
    { org_id: 1, user_id: 2, role: "member" },
  ].map((r) => withIdentity(r, ["org_id", "user_id"])),
  assets: [
    { id: 1, title: "Logo", path: "brand/logo.svg" },
    { id: 2, title: "Hero", path: "marketing/hero.svg" },
  ].map((r) => withIdentity(r, ["id"])),
  posts: [
    { id: 1, title: "Welcome", author_id: 1, body: "Hello AdminBoard" },
    { id: 2, title: "Shipping", author_id: 2, body: "D4 relations" },
  ].map((r) => withIdentity(r, ["id"])),
};

function schema(name: string) {
  const s = DEMO_RESOURCES.find((r) => r.name === name);
  if (!s) throw new Error(`Unknown resource ${name}`);
  return s;
}

function matchFilter(row: Record<string, unknown>, col: string, raw: string): boolean {
  const v = row[col];
  if (typeof v === "boolean") {
    const want = ["1", "true", "yes", "on"].includes(raw.toLowerCase());
    return v === want;
  }
  if (typeof v === "number") {
    return String(v) === raw;
  }
  return String(v ?? "") === raw;
}

export function demoList(
  name: string,
  opts: {
    page?: number;
    page_size?: number;
    search?: string;
    filters?: Record<string, string>;
    pagination?: "offset" | "keyset";
    cursor?: string | null;
  } = {},
): ListResult {
  const page = opts.page ?? 1;
  const page_size = opts.page_size ?? 50;
  const q = (opts.search ?? "").toLowerCase().trim();
  let items = [...(store[name] ?? [])];
  if (q) {
    items = items.filter((row) =>
      Object.values(row).some((v) => String(v ?? "").toLowerCase().includes(q)),
    );
  }
  if (opts.filters) {
    for (const [col, raw] of Object.entries(opts.filters)) {
      if (raw === "") continue;
      items = items.filter((row) => matchFilter(row, col, raw));
    }
  }
  const total = items.length;
  const mode = opts.pagination ?? "offset";
  if (mode === "keyset") {
    let start = 0;
    if (opts.cursor) {
      const idx = items.findIndex((r) => String(r._identity) === opts.cursor);
      start = idx >= 0 ? idx + 1 : 0;
    }
    const slice = items.slice(start, start + page_size);
    const has_more = start + page_size < total;
    return {
      items: slice,
      total,
      page: 1,
      page_size,
      next_cursor: has_more ? String(slice[slice.length - 1]?._identity ?? "") : null,
      prev_cursor: null,
      has_more,
      pagination: "keyset",
      filters: opts.filters ?? {},
    };
  }
  const start = (page - 1) * page_size;
  return {
    items: items.slice(start, start + page_size),
    total,
    page,
    page_size,
    next_cursor: null,
    prev_cursor: null,
    has_more: start + page_size < total,
    pagination: "offset",
    filters: opts.filters ?? {},
  };
}

export function demoListActions(
  name: string,
  scope?: "row" | "bulk" | "global" | string,
): BulkActionInfo[] {
  const s = schema(name);
  const hasActive = s.columns.some((c) => c.name === "active");
  const all: BulkActionInfo[] = [
    {
      name: "export_csv",
      label: "Export CSV",
      scope: "global",
      client: "export:csv",
    },
    {
      name: "export_json",
      label: "Export JSON",
      scope: "global",
      client: "export:json",
    },
    {
      name: "export_xlsx",
      label: "Export Excel",
      scope: "global",
      client: "export:xlsx",
    },
    {
      name: "copy_json",
      label: "Copy JSON",
      scope: "bulk",
      client: "copy:json",
    },
    {
      name: "copy_row_json",
      label: "Copy JSON",
      scope: "row",
      client: "copy:json",
    },
  ];
  if (hasActive) {
    all.push(
      {
        name: "deactivate",
        label: "Deactivate",
        scope: "bulk",
        confirm: true,
      },
      {
        name: "activate",
        label: "Activate",
        scope: "bulk",
        confirm: true,
      },
      {
        name: "deactivate",
        label: "Deactivate",
        scope: "row",
        confirm: true,
      },
      {
        name: "activate",
        label: "Activate",
        scope: "row",
        confirm: true,
      },
    );
  }
  if (scope) return all.filter((a) => a.scope === scope);
  return all;
}

export function demoBulkAction(
  name: string,
  action: string,
  identities: string[],
): { action: string; updated: number; ok?: boolean } {
  if (action !== "deactivate" && action !== "activate") {
    throw new Error(`unknown action ${action}`);
  }
  const active = action === "activate";
  let updated = 0;
  const rows = store[name] ?? [];
  store[name] = rows.map((r) => {
    if (identities.includes(String(r._identity)) && "active" in r) {
      updated += 1;
      return { ...r, active };
    }
    return r;
  });
  return { action, updated, ok: true };
}

export function demoGet(name: string, identity: string) {
  const row = (store[name] ?? []).find((r) => String(r._identity) === identity);
  if (!row) throw new Error("Not found");
  return row;
}

function validateDemo(name: string, body: Record<string, unknown>, partial: boolean) {
  const s = schema(name);
  const fields: Record<string, string> = {};
  for (const c of s.columns) {
    if (!c.required || c.hidden) continue;
    if (partial && !(c.name in body)) continue;
    const v = body[c.name];
    if (v === undefined || v === null || v === "") {
      fields[c.name] = "Field required";
    }
  }
  if (Object.keys(fields).length) {
    throw new ApiError("Validation failed", 422, { fields });
  }
}

export function demoCreate(name: string, body: Record<string, unknown>) {
  validateDemo(name, body, false);
  const s = schema(name);
  const row = withIdentity({ ...body }, s.primary_key);
  store[name] = [...(store[name] ?? []), row];
  return row;
}

export function demoUpdate(name: string, identity: string, body: Record<string, unknown>) {
  validateDemo(name, body, true);
  const s = schema(name);
  const rows = store[name] ?? [];
  const idx = rows.findIndex((r) => String(r._identity) === identity);
  if (idx < 0) throw new Error("Not found");
  const next = withIdentity({ ...rows[idx], ...body }, s.primary_key);
  store[name] = rows.map((r, i) => (i === idx ? next : r));
  return next;
}

export function demoDelete(name: string, identity: string) {
  store[name] = (store[name] ?? []).filter((r) => String(r._identity) !== identity);
}

export function demoExport(name: string, fmt: "csv" | "json", search?: string) {
  const { items } = demoList(name, { search, page_size: 10000 });
  if (fmt === "json") return JSON.stringify(items, null, 2);
  if (!items.length) return "";
  const cols = Object.keys(items[0]).filter((k) => k !== "_identity");
  return [
    cols.join(","),
    ...items.map((row) => cols.map((c) => JSON.stringify(row[c] ?? "")).join(",")),
  ].join("\n");
}

export function demoAutocomplete(
  name: string,
  opts: { q?: string; limit?: number } = {},
) {
  const limit = opts.limit ?? 20;
  const listed = demoList(name, { search: opts.q, page_size: limit });
  const s = schema(name);
  const labelFields = s.searchable?.length
    ? s.searchable
    : s.columns.filter((c) => !s.primary_key.includes(c.name)).map((c) => c.name).slice(0, 3);
  return listed.items.map((item) => {
    const value =
      s.primary_key.length === 1 ? (item[s.primary_key[0]] as string | number) : item._identity;
    const parts = labelFields
      .map((f) => item[f])
      .filter((v) => v != null && v !== "")
      .map(String);
    return {
      value: value as string | number,
      label: parts.length ? parts.join(" · ") : String(value),
      identity: String(item._identity),
      record: item,
    };
  });
}

export function demoListRelation(
  parent: string,
  identity: string,
  relation: string,
  opts: { page?: number; page_size?: number } = {},
): ListResult & { relation?: string } {
  const s = schema(parent);
  const rel = s.relations?.find((r) => r.name === relation);
  if (!rel) throw new Error(`Unknown relation ${relation}`);
  const parentRow = demoGet(parent, identity);
  const fkVal =
    s.primary_key.length === 1
      ? parentRow[s.primary_key[0]]
      : parentRow[s.primary_key[0]];
  const listed = demoList(rel.resource, {
    page: opts.page,
    page_size: opts.page_size,
    filters: { [rel.foreign_key]: String(fkVal) },
  });
  return { ...listed, relation };
}
