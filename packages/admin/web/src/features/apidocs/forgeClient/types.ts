/**
 * Canonical Forge API Client document — `phzyx.forge.client` v1.
 * Everything durable is this JSON shape (localStorage / import / export).
 */

export const FORGE_CLIENT_FORMAT = "phzyx.forge.client" as const;
export const FORGE_CLIENT_VERSION = 1 as const;

/** Legacy unscoped keys (pre multi-app). Migrated once when a scope is known. */
export const WORKSPACE_STORAGE_KEY = "phzyx.forge.client.v1";
export const SANDBOX_STORAGE_KEY = "phzyx.forge.client.sandbox.v1";

/** Build origin-local keys namespaced by app so same port ≠ shared workspace. */
export function workspaceStorageKey(scope: string): string {
  const s = normalizeStorageScope(scope);
  return s === "default" ? WORKSPACE_STORAGE_KEY : `${WORKSPACE_STORAGE_KEY}::${s}`;
}

export function sandboxStorageKey(scope: string): string {
  const s = normalizeStorageScope(scope);
  return s === "default" ? SANDBOX_STORAGE_KEY : `${SANDBOX_STORAGE_KEY}::${s}`;
}

export function normalizeStorageScope(scope: string): string {
  const raw = (scope || "default").trim().toLowerCase();
  const slug = raw.replace(/[^a-z0-9._@-]+/g, "-").replace(/^-+|-+$/g, "");
  return slug.slice(0, 80) || "default";
}

/** Stable id from OpenAPI meta — different apps on :9100 get different keys. */
export function appScopeFromMeta(meta: {
  title?: string;
  version?: string;
}): string {
  const title = (meta.title || "api")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "api";
  const ver = (meta.version || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "");
  return normalizeStorageScope(ver ? `${title}@${ver}` : title);
}

export type ClientMode = "sandbox" | "workspace";

export type HttpMethod =
  | "GET"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE"
  | "HEAD"
  | "OPTIONS";

export type KvRow = {
  key: string;
  value: string;
  enabled: boolean;
  secret?: boolean;
  description?: string;
};

/** Platform = bound to AdminBoard/server; user = free-form client vars. */
export type EnvVarSource = "platform" | "user";

export type EnvVariable = KvRow & {
  /** Where this var comes from. Platform vars stay coupled to the host app. */
  source?: EnvVarSource;
  /**
   * Key locked: cannot rename or delete (and usually not disable).
   * Defaults true for `baseUrl` and any `source: "platform"`.
   */
  locked?: boolean;
  /**
   * Value editable. Platform-bound values (e.g. This-server baseUrl) are false.
   * Defaults true.
   */
  editable?: boolean;
};

export type Environment = {
  id: string;
  name: string;
  variables: EnvVariable[];
};

/** Normalize flags for older workspace JSON. */
export function normalizeEnvVariable(v: EnvVariable): EnvVariable {
  const key = (v.key || "").trim();
  const source: EnvVarSource = v.source ?? "user";
  const locked = v.locked ?? (source === "platform" || key === "baseUrl");
  // Default editable; only false when explicitly set (platform-bound values).
  const editable = v.editable !== false;
  return {
    ...v,
    key,
    source,
    locked,
    editable,
  };
}

export function isEnvKeyLocked(v: EnvVariable): boolean {
  const n = normalizeEnvVariable(v);
  return Boolean(n.locked) || n.source === "platform" || n.key === "baseUrl";
}

export function isEnvValueEditable(v: EnvVariable): boolean {
  return normalizeEnvVariable(v).editable !== false;
}

export type ParamIn = "query" | "path" | "header" | "cookie";

export type RequestParam = {
  key: string;
  value: string;
  in: ParamIn;
  enabled: boolean;
  required?: boolean;
  description?: string;
};

export type RequestAuth =
  | { type: "inherit" }
  | { type: "none" }
  | { type: "session" }
  | { type: "bearer"; token?: string }
  | { type: "apikey"; header?: string; value?: string };

export type RequestBody = {
  mode: "none" | "json" | "raw";
  raw: string;
};

export type RequestDocs = {
  description?: string;
  operationId?: string;
  responses?: { code: string; description: string }[];
};

export type RequestMeta = {
  fromOpenApi?: boolean;
  tag?: string;
  deprecated?: boolean;
  /** Stable OpenAPI key `method:path` for re-merge */
  opKey?: string;
  userEdited?: boolean;
};

export type ForgeRequest = {
  id: string;
  name: string;
  method: HttpMethod;
  /** May include {{baseUrl}} or be path-only */
  url: string;
  path: string;
  headers: KvRow[];
  params: RequestParam[];
  body: RequestBody;
  auth: RequestAuth;
  docs: RequestDocs;
  meta: RequestMeta;
};

export type ForgeFolder = {
  id: string;
  name: string;
  requests: ForgeRequest[];
};

export type ForgeCollection = {
  id: string;
  name: string;
  source: "openapi" | "manual" | "import";
  folders: ForgeFolder[];
};

export type ResponseSnapshot = {
  status: number;
  statusText: string;
  ms: number;
  headers: Record<string, string>;
  bodyText: string;
  bodySize: number;
};

export type HistoryEntry = {
  id: string;
  requestId: string;
  name: string;
  method: HttpMethod;
  url: string;
  at: string;
  response: ResponseSnapshot;
};

export type SavedResponse = {
  id: string;
  name: string;
  requestId: string;
  at: string;
  response: ResponseSnapshot;
  note?: string;
};

export type ClientSettings = {
  hideAdminApis: boolean;
  adminPathPrefixes: string[];
  docsPathPrefixes: string[];
  historyLimit: number;
  timeoutMs: number;
};

export type ForgeClientDocument = {
  format: typeof FORGE_CLIENT_FORMAT;
  version: typeof FORGE_CLIENT_VERSION;
  mode: ClientMode;
  activeEnvironmentId: string;
  settings: ClientSettings;
  environments: Environment[];
  collections: ForgeCollection[];
  history: HistoryEntry[];
  savedResponses: SavedResponse[];
};

/** UI-only (not in export document) */
export type ClientUiState = {
  selectedRequestId: string | null;
  selectedFolderId: string | null;
  search: string;
  reqTab: "params" | "headers" | "body" | "auth" | "docs" | "env";
  lastResponseByRequest: Record<string, ResponseSnapshot>;
  sending: boolean;
  envEditorOpen: boolean;
  /** Env var key to highlight when opening Env tab from a URL chip. */
  focusEnvKey: string | null;
};
