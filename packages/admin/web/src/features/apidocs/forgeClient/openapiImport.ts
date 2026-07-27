import type { OpenApiSpec, Operation, Parameter, PathItem } from "../openapiTypes";
import { HTTP_METHODS, listOperations } from "../openapiTypes";
import { newId } from "./defaults";
import type {
  ForgeClientDocument,
  ForgeCollection,
  ForgeFolder,
  ForgeRequest,
  HttpMethod,
  KvRow,
  RequestParam,
} from "./types";

function exampleFromSchema(schema: unknown, depth = 0): unknown {
  if (!schema || typeof schema !== "object" || depth > 6) return null;
  const s = schema as Record<string, unknown>;
  if ("example" in s) return s.example;
  if ("default" in s) return s.default;
  if (Array.isArray(s.examples) && s.examples.length) return s.examples[0];
  if (Array.isArray(s.enum) && s.enum.length) return s.enum[0];

  // $ref not resolved in SPA — leave placeholder
  if (typeof s.$ref === "string") return null;

  const t = s.type;
  if (t === "object" || s.properties) {
    const props = (s.properties || {}) as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(props).slice(0, 16)) {
      out[k] = exampleFromSchema(v, depth + 1);
    }
    return out;
  }
  if (t === "array") {
    const item = exampleFromSchema(s.items, depth + 1);
    return item !== null && item !== undefined ? [item] : [];
  }
  if (t === "integer") return 0;
  if (t === "number") return 0.0;
  if (t === "boolean") return true;
  if (t === "string") {
    const fmt = s.format;
    if (fmt === "date-time") return "2026-01-01T00:00:00Z";
    if (fmt === "date") return "2026-01-01";
    if (fmt === "email") return "user@example.com";
    if (fmt === "uuid") return "00000000-0000-0000-0000-000000000000";
    return "string";
  }
  // oneOf / anyOf — take first
  const alts = (s.oneOf || s.anyOf) as unknown[] | undefined;
  if (Array.isArray(alts) && alts[0]) return exampleFromSchema(alts[0], depth + 1);
  return null;
}

export function sampleBodyFromOperation(op: Operation): string {
  const content = op.requestBody?.content;
  if (!content) return "";
  const media =
    content["application/json"] ||
    content["application/*+json"] ||
    Object.values(content)[0];
  if (!media || typeof media !== "object") return "";
  const m = media as {
    example?: unknown;
    examples?: Record<string, { value?: unknown }> | unknown[];
    schema?: unknown;
  };
  if (m.example !== undefined) {
    return JSON.stringify(m.example, null, 2);
  }
  if (m.examples && typeof m.examples === "object" && !Array.isArray(m.examples)) {
    const first = Object.values(m.examples)[0];
    if (first && typeof first === "object" && "value" in first) {
      return JSON.stringify((first as { value: unknown }).value, null, 2);
    }
  }
  const fromSchema = exampleFromSchema(m.schema);
  if (fromSchema !== null && fromSchema !== undefined) {
    return JSON.stringify(fromSchema, null, 2);
  }
  return "{\n  \n}";
}

function paramDefault(p: Parameter): string {
  const ex = p.example ?? p.schema?.example ?? p.schema?.default;
  if (ex !== undefined && ex !== null) return String(ex);
  if (p.schema?.enum?.length) return String(p.schema.enum[0]);
  return "";
}

function pathMatchesPrefix(path: string, pref: string): boolean {
  const p = pref.endsWith("/") ? pref.slice(0, -1) : pref;
  return path === p || path.startsWith(`${p}/`);
}

function shouldHidePath(
  path: string,
  settings: ForgeClientDocument["settings"],
): boolean {
  if (settings.hideAdminApis) {
    for (const pref of settings.adminPathPrefixes) {
      if (pathMatchesPrefix(path, pref)) return true;
    }
  }
  for (const pref of settings.docsPathPrefixes) {
    if (pathMatchesPrefix(path, pref)) return true;
  }
  return false;
}

function toMethod(m: string): HttpMethod {
  return m.toUpperCase() as HttpMethod;
}

function mergeParams(pathItem: PathItem, op: Operation): Parameter[] {
  return [...(pathItem.parameters || []), ...(op.parameters || [])];
}

export function openApiToCollection(
  spec: OpenApiSpec,
  settings: ForgeClientDocument["settings"],
  collectionName = "Live OpenAPI",
): ForgeCollection {
  const folders = new Map<string, ForgeFolder>();
  const paths = spec.paths || {};

  for (const [path, item] of Object.entries(paths)) {
    if (!item || typeof item !== "object") continue;
    if (shouldHidePath(path, settings)) continue;

    for (const method of HTTP_METHODS) {
      const op = item[method];
      if (!op) continue;
      const tag = (op.tags && op.tags[0]) || "default";
      let folder = folders.get(tag);
      if (!folder) {
        folder = { id: newId("fld"), name: tag, requests: [] };
        folders.set(tag, folder);
      }

      const params: RequestParam[] = mergeParams(item, op).map((p) => ({
        key: p.name || "",
        value: paramDefault(p),
        in: (p.in || "query") as RequestParam["in"],
        enabled: Boolean(p.required) || Boolean(paramDefault(p)),
        required: Boolean(p.required),
        description: p.description || "",
      }));

      const headers: KvRow[] = [];
      const bodyRaw = sampleBodyFromOperation(op);
      if (bodyRaw && ["post", "put", "patch"].includes(method)) {
        headers.push({
          key: "Content-Type",
          value: "application/json",
          enabled: true,
        });
      }

      const responses = Object.entries(op.responses || {}).map(([code, v]) => ({
        code,
        description:
          v && typeof v === "object" && "description" in v
            ? String((v as { description?: string }).description || "")
            : "",
      }));

      const req: ForgeRequest = {
        id: newId("req"),
        name: op.summary || op.operationId || `${method.toUpperCase()} ${path}`,
        method: toMethod(method),
        url: `{{baseUrl}}${path}`,
        path,
        headers,
        params,
        body: {
          mode: bodyRaw ? "json" : "none",
          raw: bodyRaw,
        },
        auth: { type: "inherit" },
        docs: {
          description: op.description || "",
          operationId: op.operationId,
          responses,
        },
        meta: {
          fromOpenApi: true,
          tag,
          deprecated: Boolean(op.deprecated),
          opKey: `${method}:${path}`,
          userEdited: false,
        },
      };
      folder.requests.push(req);
    }
  }

  const sorted = Array.from(folders.values()).sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  for (const f of sorted) {
    f.requests.sort((a, b) => {
      const p = a.path.localeCompare(b.path);
      if (p !== 0) return p;
      return a.method.localeCompare(b.method);
    });
  }

  return {
    id: newId("col"),
    name: collectionName,
    source: "openapi",
    folders: sorted,
  };
}

/** Merge OpenAPI into existing collection, preserving userEdited requests by opKey. */
export function mergeOpenApiCollection(
  existing: ForgeCollection | undefined,
  next: ForgeCollection,
): ForgeCollection {
  if (!existing) return next;
  const byKey = new Map<string, ForgeRequest>();
  for (const f of existing.folders) {
    for (const r of f.requests) {
      if (r.meta.opKey) byKey.set(r.meta.opKey, r);
    }
  }
  const folders = next.folders.map((folder) => ({
    ...folder,
    requests: folder.requests.map((r) => {
      const prev = r.meta.opKey ? byKey.get(r.meta.opKey) : undefined;
      if (prev?.meta.userEdited) {
        return {
          ...prev,
          // keep docs/meta from server for reference
          docs: r.docs,
          meta: { ...prev.meta, fromOpenApi: true, opKey: r.meta.opKey },
        };
      }
      if (prev) {
        return {
          ...r,
          id: prev.id,
          // keep user's runtime param/header tweaks if not marked edited? prefer fresh samples
        };
      }
      return r;
    }),
  }));
  return {
    ...next,
    id: existing.id,
    name: existing.name || next.name,
    folders,
  };
}

export function countVisibleOps(
  spec: OpenApiSpec,
  settings: ForgeClientDocument["settings"],
): number {
  return listOperations(spec).filter((o) => !shouldHidePath(o.path, settings)).length;
}

export { shouldHidePath, exampleFromSchema, pathMatchesPrefix };
