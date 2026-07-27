import { SESSION_MODE } from "../../auth/sessionStore";
import { resolveRequestUrl, interpolateWithEnv, envMap, interpolate } from "./interpolate";
import type {
  Environment,
  ForgeRequest,
  RequestAuth,
  ResponseSnapshot,
} from "./types";

export type GlobalAuth = {
  profile: "session" | "bearer" | "apikey" | "none";
  bearer: string;
  apiKey: string;
  apiKeyHeader: string;
  /** session store */
  authorization: string | null;
  csrfToken: string | null;
};

export type BuiltRequest = {
  url: string;
  method: string;
  headers: Headers;
  body?: string;
  credentials: RequestCredentials;
};

function applyAuth(
  headers: Headers,
  method: string,
  auth: RequestAuth,
  global: GlobalAuth,
  env: Environment | null | undefined,
): RequestCredentials {
  const vars = envMap(env);
  let effective: RequestAuth = auth;
  if (auth.type === "inherit") {
    if (global.profile === "session") effective = { type: "session" };
    else if (global.profile === "bearer")
      effective = { type: "bearer", token: global.bearer || vars.token };
    else if (global.profile === "apikey")
      effective = {
        type: "apikey",
        header: global.apiKeyHeader,
        value: global.apiKey || vars.apiKey,
      };
    else effective = { type: "none" };
  }

  if (effective.type === "session") {
    if (global.authorization && global.authorization !== SESSION_MODE) {
      headers.set("Authorization", global.authorization);
    }
    const m = method.toUpperCase();
    if (
      global.csrfToken &&
      global.authorization === SESSION_MODE &&
      !["GET", "HEAD", "OPTIONS", "TRACE"].includes(m)
    ) {
      headers.set("X-CSRF-Token", global.csrfToken);
    }
    return "same-origin";
  }
  if (effective.type === "bearer") {
    const tok = interpolate(effective.token || global.bearer || vars.token || "", vars);
    if (tok) headers.set("Authorization", `Bearer ${tok}`);
    return "omit";
  }
  if (effective.type === "apikey") {
    const h = effective.header || global.apiKeyHeader || "X-API-Key";
    const v = interpolate(effective.value || global.apiKey || vars.apiKey || "", vars);
    if (v) headers.set(h, v);
    return "omit";
  }
  return "omit";
}

export function buildRequest(
  req: ForgeRequest,
  env: Environment | null | undefined,
  global: GlobalAuth,
): BuiltRequest {
  let path = req.path || req.url;
  const query: string[] = [];
  const headers = new Headers();

  for (const p of req.params) {
    if (!p.enabled || !p.key) continue;
    const val = interpolateWithEnv(p.value, env);
    if (p.in === "path") {
      path = path.replace(`{${p.key}}`, encodeURIComponent(val || p.key));
      // also support :id style
      path = path.replace(`:${p.key}`, encodeURIComponent(val || p.key));
    } else if (p.in === "query" && val !== "") {
      query.push(`${encodeURIComponent(p.key)}=${encodeURIComponent(val)}`);
    } else if (p.in === "header" && val !== "") {
      headers.set(p.key, val);
    }
  }

  for (const h of req.headers) {
    if (!h.enabled || !h.key) continue;
    headers.set(h.key, interpolateWithEnv(h.value, env));
  }

  // Prefer template url with path substitution
  let urlTemplate = req.url.includes("{{") || req.url.startsWith("http")
    ? req.url
    : path;
  // If url still has {param} placeholders, apply path from substituted path
  if (urlTemplate.includes("{")) {
    // replace path segment of url with substituted path
    urlTemplate = req.url.replace(req.path, path);
    if (urlTemplate === req.url && path !== req.path) {
      // path-only template {{baseUrl}}/x/{id}
      urlTemplate = interpolateWithEnv(req.url, env).replace(
        /\{([^}]+)\}/g,
        (_, name: string) => {
          const p = req.params.find((x) => x.key === name && x.in === "path");
          return encodeURIComponent(
            p ? interpolateWithEnv(p.value, env) || name : name,
          );
        },
      );
    }
  }

  let url = resolveRequestUrl(urlTemplate.includes("{") ? path : urlTemplate, env);
  // If we resolved from path only
  if (!req.url.includes("{{") && !/^https?:/i.test(req.url)) {
    url = resolveRequestUrl(path, env);
  } else if (req.url.includes("{{baseUrl}}") || req.url.startsWith("{{")) {
    // re-resolve with path substitution on template
    let tpl = req.url;
    for (const p of req.params.filter((x) => x.in === "path")) {
      const val = interpolateWithEnv(p.value, env);
      tpl = tpl.replace(`{${p.key}}`, encodeURIComponent(val || p.key));
    }
    url = resolveRequestUrl(tpl, env);
  }

  if (query.length) {
    url += (url.includes("?") ? "&" : "?") + query.join("&");
  }

  const credentials = applyAuth(headers, req.method, req.auth, global, env);

  const hasBody =
    ["POST", "PUT", "PATCH"].includes(req.method) &&
    req.body.mode !== "none" &&
    req.body.raw.trim();

  if (hasBody && !headers.has("Content-Type") && req.body.mode === "json") {
    headers.set("Content-Type", "application/json");
  }

  return {
    url,
    method: req.method,
    headers,
    body: hasBody ? interpolateWithEnv(req.body.raw, env) : undefined,
    credentials,
  };
}

export async function executeRequest(
  req: ForgeRequest,
  env: Environment | null | undefined,
  global: GlobalAuth,
  timeoutMs = 30_000,
): Promise<ResponseSnapshot> {
  const built = buildRequest(req, env, global);
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  const t0 = performance.now();
  try {
    const res = await fetch(built.url, {
      method: built.method,
      headers: built.headers,
      credentials: built.credentials,
      body: built.body,
      signal: ctrl.signal,
    });
    const ms = Math.round(performance.now() - t0);
    const text = await res.text();
    const headers: Record<string, string> = {};
    res.headers.forEach((v, k) => {
      headers[k] = v;
    });
    return {
      status: res.status,
      statusText: res.statusText,
      ms,
      headers,
      bodyText: text,
      bodySize: new TextEncoder().encode(text).length,
    };
  } finally {
    window.clearTimeout(timer);
  }
}

export function toCurl(
  req: ForgeRequest,
  env: Environment | null | undefined,
  global: GlobalAuth,
): string {
  const built = buildRequest(req, env, global);
  const parts = [`curl -X ${built.method} '${built.url}'`];
  built.headers.forEach((v, k) => {
    parts.push(`  -H '${k}: ${v.replace(/'/g, "'\\''")}'`);
  });
  if (built.body) {
    parts.push(`  -d '${built.body.replace(/'/g, "'\\''")}'`);
  }
  return parts.join(" \\\n");
}
