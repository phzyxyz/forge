/** Minimal OpenAPI 3 shapes used by API Board. */

export type OpenApiSpec = {
  openapi?: string;
  info?: { title?: string; version?: string; description?: string };
  servers?: { url?: string }[];
  paths?: Record<string, PathItem>;
  components?: { securitySchemes?: Record<string, SecurityScheme> };
};

export type PathItem = {
  parameters?: Parameter[];
  summary?: string;
  description?: string;
} & Partial<Record<HttpMethod, Operation>>;

export type HttpMethod =
  | "get"
  | "post"
  | "put"
  | "patch"
  | "delete"
  | "head"
  | "options";

export type Operation = {
  tags?: string[];
  summary?: string;
  description?: string;
  operationId?: string;
  parameters?: Parameter[];
  requestBody?: {
    required?: boolean;
    description?: string;
    content?: Record<string, { schema?: unknown; example?: unknown; examples?: unknown }>;
  };
  security?: Record<string, string[]>[];
  responses?: Record<string, { description?: string; content?: unknown }>;
  deprecated?: boolean;
};

export type Parameter = {
  name?: string;
  in?: "query" | "path" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: {
    type?: string;
    default?: unknown;
    example?: unknown;
    enum?: unknown[];
    format?: string;
  };
  example?: unknown;
};

export type SecurityScheme = {
  type?: string;
  scheme?: string;
  name?: string;
  in?: string;
  description?: string;
};

export type OpRef = {
  id: string;
  method: HttpMethod;
  path: string;
  tag: string;
  summary: string;
  operation: Operation;
  pathItem: PathItem;
};

export type TagSection = {
  tag: string;
  ops: OpRef[];
};

export const HTTP_METHODS: HttpMethod[] = [
  "get",
  "post",
  "put",
  "patch",
  "delete",
  "head",
  "options",
];

export function listOperations(spec: OpenApiSpec): OpRef[] {
  const out: OpRef[] = [];
  const paths = spec.paths || {};
  for (const [path, item] of Object.entries(paths)) {
    if (!item || typeof item !== "object") continue;
    for (const method of HTTP_METHODS) {
      const op = item[method];
      if (!op) continue;
      const tag = (op.tags && op.tags[0]) || "default";
      out.push({
        id: `${method}:${path}`,
        method,
        path,
        tag,
        summary: op.summary || op.operationId || `${method.toUpperCase()} ${path}`,
        operation: op,
        pathItem: item,
      });
    }
  }
  out.sort((a, b) => {
    const t = a.tag.localeCompare(b.tag);
    if (t !== 0) return t;
    const p = a.path.localeCompare(b.path);
    if (p !== 0) return p;
    return a.method.localeCompare(b.method);
  });
  return out;
}

export function groupByTag(ops: OpRef[]): TagSection[] {
  const map = new Map<string, OpRef[]>();
  for (const o of ops) {
    const list = map.get(o.tag) || [];
    list.push(o);
    map.set(o.tag, list);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([tag, tagOps]) => ({ tag, ops: tagOps }));
}

export function mergeParams(op: OpRef): Parameter[] {
  const base = op.pathItem.parameters || [];
  const own = op.operation.parameters || [];
  return [...base, ...own];
}

function exampleFromSchema(schema: unknown, depth = 0): unknown {
  if (!schema || typeof schema !== "object" || depth > 6) return null;
  const s = schema as Record<string, unknown>;
  if ("example" in s) return s.example;
  if ("default" in s) return s.default;
  if (Array.isArray(s.examples) && s.examples.length) return s.examples[0];
  if (Array.isArray(s.enum) && s.enum.length) return s.enum[0];
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
  if (t === "string") return "string";
  const alts = (s.oneOf || s.anyOf) as unknown[] | undefined;
  if (Array.isArray(alts) && alts[0]) return exampleFromSchema(alts[0], depth + 1);
  return null;
}

export function exampleBody(op: Operation): string {
  const rb = op.requestBody?.content;
  if (!rb) return "";
  const json = rb["application/json"] || Object.values(rb)[0];
  if (!json) return "";
  if (json.example !== undefined) {
    return JSON.stringify(json.example, null, 2);
  }
  const media = json as { schema?: unknown; examples?: Record<string, { value?: unknown }> };
  if (media.examples && typeof media.examples === "object") {
    const first = Object.values(media.examples)[0];
    if (first && "value" in first) return JSON.stringify(first.value, null, 2);
  }
  const fromSchema = exampleFromSchema(media.schema);
  if (fromSchema !== null && fromSchema !== undefined) {
    return JSON.stringify(fromSchema, null, 2);
  }
  return "{\n  \n}";
}

export function responseCodes(op: Operation): { code: string; description: string }[] {
  const res = op.responses || {};
  return Object.entries(res)
    .map(([code, v]) => ({
      code,
      description:
        v && typeof v === "object" && "description" in v
          ? String((v as { description?: string }).description || "")
          : "",
    }))
    .sort((a, b) => a.code.localeCompare(b.code));
}

export function hasJsonBody(op: Operation): boolean {
  return Boolean(op.requestBody?.content);
}

export function securitySchemesList(spec: OpenApiSpec): { name: string; scheme: SecurityScheme }[] {
  const schemes = spec.components?.securitySchemes || {};
  return Object.entries(schemes).map(([name, scheme]) => ({ name, scheme }));
}
