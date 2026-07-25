import { apiBlob, apiFetch, apiJson, apiText } from "../../shared/api/client";
import type {
  AutocompleteOption,
  BulkActionInfo,
  ListResult,
  MetaInfo,
  ResourceSchema,
} from "../../shared/api/types";
import {
  DEMO_META,
  DEMO_RESOURCES,
  demoAutocomplete,
  demoBulkAction,
  demoCreate,
  demoDelete,
  demoExport,
  demoGet,
  demoList,
  demoListActions,
  demoListRelation,
  demoUpdate,
} from "./mockSeed";

export type ListOpts = {
  page?: number;
  page_size?: number;
  search?: string;
  filters?: Record<string, string>;
  pagination?: "offset" | "keyset";
  cursor?: string | null;
};

export async function probeMode(forceDemo: boolean): Promise<{
  demo: boolean;
  meta: MetaInfo;
  needsAuth: boolean;
}> {
  if (forceDemo || new URLSearchParams(location.search).get("demo") === "1") {
    return { demo: true, meta: DEMO_META, needsAuth: false };
  }
  try {
    const meta = await apiJson<MetaInfo>("/meta");
    return { demo: false, meta, needsAuth: true };
  } catch (e) {
    const status = (e as { status?: number }).status;
    if (status === 401 || status === 403) {
      return { demo: false, meta: DEMO_META, needsAuth: true };
    }
    return { demo: true, meta: DEMO_META, needsAuth: false };
  }
}

export async function fetchResources(demo: boolean): Promise<ResourceSchema[]> {
  if (demo) return DEMO_RESOURCES;
  return apiJson<ResourceSchema[]>("/resources");
}

export type DashboardWidget = {
  id?: string;
  resource: string;
  label?: string;
  title?: string;
  value: number;
  kind?: string;
};

export async function fetchDashboardWidgets(
  demo: boolean,
  resources: ResourceSchema[],
): Promise<DashboardWidget[]> {
  if (demo) {
    // Approximate with list totals in demo mode.
    const out: DashboardWidget[] = [];
    for (const r of resources) {
      const list = await demoList(r.name, { page: 1, page_size: 1 });
      out.push({
        resource: r.name,
        label: r.label,
        value: list.total,
        kind: "count",
      });
    }
    return out;
  }
  const data = await apiJson<{ items: DashboardWidget[] }>("/widgets");
  return data.items ?? [];
}

export async function fetchI18nCatalog(
  demo: boolean,
  locale = "en",
): Promise<Record<string, string>> {
  if (demo) {
    return {
      "app.title": "AdminBoard",
      "nav.resources": "Resources",
      "nav.settings": "Settings",
      "action.create": "Create",
      "action.save": "Save",
      "action.delete": "Delete",
      "action.export": "Export",
      "action.search": "Search",
      "empty.no_results": "No results",
    };
  }
  const data = await apiJson<{ catalog: Record<string, string> }>(
    `/i18n?locale=${encodeURIComponent(locale)}`,
  );
  return data.catalog ?? {};
}

export async function listRecords(
  demo: boolean,
  name: string,
  opts: ListOpts = {},
): Promise<ListResult> {
  if (demo) return demoList(name, opts);
  const q = new URLSearchParams();
  q.set("page", String(opts.page ?? 1));
  q.set("page_size", String(opts.page_size ?? 50));
  if (opts.search) q.set("search", opts.search);
  if (opts.pagination) q.set("pagination", opts.pagination);
  if (opts.cursor) q.set("cursor", opts.cursor);
  if (opts.filters) {
    for (const [k, v] of Object.entries(opts.filters)) {
      if (v !== "") q.set(`filter.${k}`, v);
    }
  }
  return apiJson<ListResult>(`/resources/${name}/records?${q}`);
}

export async function listBulkActions(
  demo: boolean,
  name: string,
): Promise<BulkActionInfo[]> {
  if (demo) return demoListActions(name, "bulk");
  return apiJson<BulkActionInfo[]>(`/resources/${name}/actions?scope=bulk`);
}

export async function listAdminActions(
  demo: boolean,
  name: string,
  scope?: "row" | "bulk" | "global",
): Promise<BulkActionInfo[]> {
  if (demo) return demoListActions(name, scope);
  const q = scope ? `?scope=${scope}` : "";
  return apiJson<BulkActionInfo[]>(`/resources/${name}/actions${q}`);
}

export async function autocompleteResource(
  demo: boolean,
  name: string,
  opts: { q?: string; limit?: number } = {},
): Promise<AutocompleteOption[]> {
  if (demo) return demoAutocomplete(name, opts);
  const q = new URLSearchParams();
  if (opts.q) q.set("q", opts.q);
  q.set("limit", String(opts.limit ?? 20));
  return apiJson<AutocompleteOption[]>(`/resources/${name}/autocomplete?${q}`);
}

export async function listRelation(
  demo: boolean,
  parent: string,
  identity: string,
  relation: string,
  opts: { page?: number; page_size?: number } = {},
): Promise<ListResult & { relation?: string; kind?: string }> {
  if (demo) return demoListRelation(parent, identity, relation, opts);
  const q = new URLSearchParams();
  q.set("page", String(opts.page ?? 1));
  q.set("page_size", String(opts.page_size ?? 50));
  return apiJson(
    `/resources/${parent}/records/${encodeURIComponent(identity)}/relations/${encodeURIComponent(relation)}?${q}`,
  );
}

export async function getM2mIds(
  demo: boolean,
  parent: string,
  identity: string,
  relation: string,
): Promise<{ relation: string; ids: string[] }> {
  if (demo) return { relation, ids: [] };
  return apiJson(
    `/resources/${parent}/records/${encodeURIComponent(identity)}/m2m/${encodeURIComponent(relation)}`,
  );
}

export async function setM2mIds(
  demo: boolean,
  parent: string,
  identity: string,
  relation: string,
  ids: string[],
): Promise<{ ok: boolean; ids: string[]; count: number }> {
  if (demo) return { ok: true, ids, count: ids.length };
  return apiJson(
    `/resources/${parent}/records/${encodeURIComponent(identity)}/m2m/${encodeURIComponent(relation)}`,
    { method: "PUT", body: JSON.stringify({ ids }) },
  );
}

export async function runBulkAction(
  demo: boolean,
  name: string,
  action: string,
  identities: string[],
): Promise<{ action: string; updated: number; ok?: boolean }> {
  if (demo) return demoBulkAction(name, action, identities);
  return apiJson(`/resources/${name}/bulk`, {
    method: "POST",
    body: JSON.stringify({ action, identities }),
  });
}

export async function runAdminAction(
  demo: boolean,
  name: string,
  action: string,
  identities: string[],
): Promise<{ action: string; updated: number; ok?: boolean }> {
  if (demo) return demoBulkAction(name, action, identities);
  return apiJson(`/resources/${name}/actions/run`, {
    method: "POST",
    body: JSON.stringify({ action, identities }),
  });
}

export async function createRecord(
  demo: boolean,
  name: string,
  body: Record<string, unknown>,
) {
  if (demo) return demoCreate(name, body);
  return apiJson<Record<string, unknown>>(`/resources/${name}/records`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateRecord(
  demo: boolean,
  name: string,
  identity: string,
  body: Record<string, unknown>,
) {
  if (demo) return demoUpdate(name, identity, body);
  return apiJson<Record<string, unknown>>(
    `/resources/${name}/records/${encodeURIComponent(identity)}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export async function deleteRecord(demo: boolean, name: string, identity: string) {
  if (demo) {
    demoDelete(name, identity);
    return;
  }
  await apiJson(`/resources/${name}/records/${encodeURIComponent(identity)}`, {
    method: "DELETE",
  });
}

export async function exportResource(
  demo: boolean,
  name: string,
  fmt: "csv" | "json" | "xlsx",
  search?: string,
): Promise<string | Blob> {
  if (demo) {
    if (fmt === "xlsx") throw new Error("Excel export unavailable in offline demo");
    return demoExport(name, fmt, search);
  }
  const q = new URLSearchParams({ fmt });
  if (search) q.set("search", search);
  if (fmt === "xlsx") {
    return apiBlob(`/resources/${name}/export?${q}&stream=true`);
  }
  return apiText(`/resources/${name}/export?${q}`);
}

export async function copyResource(
  demo: boolean,
  name: string,
  fmt: "csv" | "json",
  identities?: string[],
) {
  if (demo) {
    if (identities?.length) {
      const rows = identities.map((id) => demoGet(name, id));
      return fmt === "json"
        ? JSON.stringify(rows, null, 2)
        : rows.map((r) => JSON.stringify(r)).join("\n");
    }
    return demoExport(name, fmt);
  }
  const data = await apiJson<{ payload: string }>(`/resources/${name}/copy`, {
    method: "POST",
    body: JSON.stringify({ fmt, identities }),
  });
  return data.payload;
}

export async function openMeta(demo: boolean, key: string) {
  if (demo) {
    return {
      key,
      mode: /\.(svg|png|jpe?g|gif|webp)$/i.test(key) ? "image" : "download",
      content_type: "application/octet-stream",
      label: key.split("/").pop() || key,
    };
  }
  return apiJson<{ mode: string; content_type: string; label: string; key: string }>(
    `/files/open-meta?key=${encodeURIComponent(key)}`,
  );
}

export async function downloadFile(demo: boolean, key: string): Promise<Blob | null> {
  if (demo) return null;
  return apiBlob(`/files/download?key=${encodeURIComponent(key)}`);
}

export type MediaLibraryItem = {
  key: string;
  folder: string;
  content_type: string;
  size: number | null;
  mode: string;
  label: string;
  thumb_url: string | null;
};

export async function listMediaLibrary(
  demo: boolean,
  folder = "",
): Promise<{ folder: string; items: MediaLibraryItem[]; total: number }> {
  if (demo) return { folder, items: [], total: 0 };
  const q = folder ? `?folder=${encodeURIComponent(folder)}` : "";
  return apiJson(`/files/library${q}`);
}

export async function uploadFile(demo: boolean, key: string, file: File) {
  if (demo) throw new Error("Upload unavailable in offline demo");
  const form = new FormData();
  form.set("key", key);
  form.set("file", file);
  const r = await apiFetch("/files/upload", { method: "POST", body: form });
  if (!r.ok) throw new Error(`Upload failed (${r.status})`);
  return r.json();
}
