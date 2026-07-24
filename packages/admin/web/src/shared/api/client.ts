import {
  emitSessionExpired,
  SESSION_MODE,
  useSessionStore,
} from "../../features/auth/sessionStore";

export const API = "/admin/api/v1";

export class ApiError extends Error {
  status: number;
  details: Record<string, unknown>;
  fields: Record<string, string>;

  constructor(
    message: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.status = status;
    this.details = details;
    const raw = details.fields;
    this.fields =
      raw && typeof raw === "object" && !Array.isArray(raw)
        ? Object.fromEntries(
            Object.entries(raw as Record<string, unknown>).map(([k, v]) => [k, String(v)]),
          )
        : {};
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const { authorization, csrfToken } = useSessionStore.getState();
  if (authorization && authorization !== SESSION_MODE) {
    headers.set("Authorization", authorization);
  }
  const method = (init.method || "GET").toUpperCase();
  if (
    csrfToken &&
    authorization === SESSION_MODE &&
    !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)
  ) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (res.status === 401 && authorization) {
    emitSessionExpired();
  }
  return res;
}

/** Event for 403 Forbidden — Trust UI can subscribe. */
export const FORBIDDEN_EVENT = "phzyx:forbidden";

export function emitForbidden(error: ApiError) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(FORBIDDEN_EVENT, {
      detail: {
        message: error.message,
        action: error.details?.action,
        resource: error.details?.resource,
        status: error.status,
      },
    }),
  );
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await apiFetch(path, init);
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    let details: Record<string, unknown> = {};
    try {
      const body = await r.json();
      msg = body?.error?.message || body?.detail || msg;
      details = body?.error?.details || {};
    } catch {
      /* ignore */
    }
    const err = new ApiError(msg, r.status, details);
    if (r.status === 403) {
      emitForbidden(err);
    }
    throw err;
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export async function apiText(path: string, init?: RequestInit): Promise<string> {
  const r = await apiFetch(path, init);
  if (!r.ok) throw new ApiError(`Request failed (${r.status})`, r.status);
  return r.text();
}

export async function apiBlob(path: string, init?: RequestInit): Promise<Blob> {
  const r = await apiFetch(path, init);
  if (!r.ok) throw new ApiError(`Request failed (${r.status})`, r.status);
  return r.blob();
}
