import type { Environment, EnvVariable } from "./types";

const VAR_RE = /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g;

export function envMap(env: Environment | null | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!env) return out;
  for (const v of env.variables) {
    if (!v.enabled || !v.key) continue;
    out[v.key] = v.value ?? "";
  }
  return out;
}

/** Replace {{var}} using enabled env variables. Unresolved tokens stay as-is. */
export function interpolate(template: string, vars: Record<string, string>): string {
  if (!template) return template;
  return template.replace(VAR_RE, (full, name: string) => {
    if (Object.prototype.hasOwnProperty.call(vars, name)) {
      return vars[name] ?? "";
    }
    return full;
  });
}

export function interpolateWithEnv(
  template: string,
  env: Environment | null | undefined,
): string {
  return interpolate(template, envMap(env));
}

/** Ensure absolute URL: path-only → baseUrl + path */
export function resolveRequestUrl(
  urlOrPath: string,
  env: Environment | null | undefined,
): string {
  const vars = envMap(env);
  let url = interpolate(urlOrPath.trim(), vars);
  if (!url) {
    const base = (vars.baseUrl || "").replace(/\/+$/, "");
    return base || url;
  }
  if (/^https?:\/\//i.test(url)) return url;
  const base = (vars.baseUrl || "").replace(/\/+$/, "");
  if (!base) return url.startsWith("/") ? url : `/${url}`;
  if (url.startsWith("/")) return `${base}${url}`;
  return `${base}/${url}`;
}

export function listUnresolved(template: string, vars: Record<string, string>): string[] {
  const missing: string[] = [];
  const re = new RegExp(VAR_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(template))) {
    const name = m[1]!;
    if (!Object.prototype.hasOwnProperty.call(vars, name) && !missing.includes(name)) {
      missing.push(name);
    }
  }
  return missing;
}

export type EnvToken =
  | { type: "text"; value: string }
  | { type: "var"; name: string; raw: string };

/** Split a template into plain text and `{{var}}` tokens for highlight UI. */
export function parseEnvTokens(template: string): EnvToken[] {
  if (!template) return [];
  const out: EnvToken[] = [];
  const re = new RegExp(VAR_RE.source, "g");
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(template))) {
    if (m.index > last) {
      out.push({ type: "text", value: template.slice(last, m.index) });
    }
    out.push({ type: "var", name: m[1]!, raw: m[0]! });
    last = m.index + m[0]!.length;
  }
  if (last < template.length) {
    out.push({ type: "text", value: template.slice(last) });
  }
  return out;
}

export type EnvVarLookup =
  | { status: "ok"; value: string; secret: boolean }
  | { status: "empty"; value: ""; secret: boolean }
  | { status: "disabled"; value: string; secret: boolean }
  | { status: "missing"; value: ""; secret: false };

/** Resolve how an env var will behave for highlight / hover UI. */
export function lookupEnvVar(
  env: Environment | null | undefined,
  name: string,
): EnvVarLookup {
  if (!env) return { status: "missing", value: "", secret: false };
  const found = env.variables.find((v) => v.key === name);
  if (!found) return { status: "missing", value: "", secret: false };
  const secret = Boolean(found.secret);
  if (!found.enabled) {
    return { status: "disabled", value: found.value ?? "", secret };
  }
  if (!(found.value ?? "").length) {
    return { status: "empty", value: "", secret };
  }
  return { status: "ok", value: found.value, secret };
}

/** Display value in tooltips — mask secrets. */
export function formatEnvVarDisplay(lookup: EnvVarLookup): string {
  if (lookup.status === "missing") return "(not defined)";
  if (lookup.status === "disabled") {
    const v = lookup.secret ? "••••••••" : lookup.value || "(empty)";
    return `${v} · disabled`;
  }
  if (lookup.status === "empty") return "(empty)";
  if (lookup.secret) return "••••••••";
  return lookup.value;
}

export function upsertVariable(
  variables: EnvVariable[],
  key: string,
  value: string,
  opts?: Partial<EnvVariable>,
): EnvVariable[] {
  const i = variables.findIndex((v) => v.key === key);
  if (i >= 0) {
    const next = [...variables];
    next[i] = { ...next[i]!, value, ...opts };
    return next;
  }
  return [
    ...variables,
    {
      key,
      value,
      enabled: true,
      secret: false,
      ...opts,
    },
  ];
}
