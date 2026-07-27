import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, apiJson } from "../../../shared/api/client";
import { useShellStore } from "../../../shared/stores/shell";
import { useSessionStore } from "../../auth/sessionStore";
import type { OpenApiSpec } from "../openapiTypes";
import { EnvAwareUrlInput, EnvHighlightText } from "./EnvAwareUrlInput";
import { resolveRequestUrl } from "./interpolate";
import { executeRequest, toCurl } from "./sendRequest";
import { useForgeClientStore } from "./store";
import {
  appScopeFromMeta,
  isEnvKeyLocked,
  isEnvValueEditable,
  workspaceStorageKey,
  type EnvVariable,
  type ForgeRequest,
  type HttpMethod,
  type KvRow,
  type RequestParam,
  type ResponseSnapshot,
} from "./types";

function methodClass(m: string): string {
  return `ab-method ab-method-${m.toLowerCase()}`;
}

function pretty(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

async function copyText(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export function ForgeClientPage() {
  const toast = useShellStore((s) => s.toast);
  const { authorization, csrfToken, username } = useSessionStore();
  const fileRef = useRef<HTMLInputElement>(null);

  const doc = useForgeClientStore((s) => s.doc);
  const ui = useForgeClientStore((s) => s.ui);
  const auth = useForgeClientStore((s) => s.auth);
  const hydrated = useForgeClientStore((s) => s.hydrated);
  const hydrate = useForgeClientStore((s) => s.hydrate);
  const appScope = useForgeClientStore((s) => s.appScope);
  const setAppScope = useForgeClientStore((s) => s.setAppScope);
  const seedFromOpenApi = useForgeClientStore((s) => s.seedFromOpenApi);
  const setMode = useForgeClientStore((s) => s.setMode);
  const resetSandbox = useForgeClientStore((s) => s.resetSandbox);
  const setHideAdminApis = useForgeClientStore((s) => s.setHideAdminApis);
  const setActiveEnvironmentId = useForgeClientStore((s) => s.setActiveEnvironmentId);
  const updateEnvironment = useForgeClientStore((s) => s.updateEnvironment);
  const addEnvironment = useForgeClientStore((s) => s.addEnvironment);
  const setSearch = useForgeClientStore((s) => s.setSearch);
  const setReqTab = useForgeClientStore((s) => s.setReqTab);
  const openEnvVar = useForgeClientStore((s) => s.openEnvVar);
  const syncPlatformEnv = useForgeClientStore((s) => s.syncPlatformEnv);
  const selectRequest = useForgeClientStore((s) => s.selectRequest);
  const updateRequest = useForgeClientStore((s) => s.updateRequest);
  const setAuth = useForgeClientStore((s) => s.setAuth);
  const pushHistory = useForgeClientStore((s) => s.pushHistory);
  const setLastResponse = useForgeClientStore((s) => s.setLastResponse);
  const setSending = useForgeClientStore((s) => s.setSending);
  const saveResponse = useForgeClientStore((s) => s.saveResponse);
  const deleteSavedResponse = useForgeClientStore((s) => s.deleteSavedResponse);
  const exportWorkspace = useForgeClientStore((s) => s.exportWorkspace);
  const importWorkspace = useForgeClientStore((s) => s.importWorkspace);
  const findRequest = useForgeClientStore((s) => s.findRequest);
  const activeEnv = useForgeClientStore((s) => s.activeEnv);

  useEffect(() => {
    if (!hydrated) hydrate("sandbox");
  }, [hydrated, hydrate]);

  const specQ = useQuery({
    queryKey: ["forge-openapi", doc.settings.hideAdminApis],
    queryFn: () => apiJson<OpenApiSpec>("/openapi"),
    enabled: hydrated,
  });

  const metaQ = useQuery({
    queryKey: ["forge-openapi-meta"],
    queryFn: () =>
      apiJson<{ title: string; version: string; operations: number; base_url: string }>(
        "/openapi/meta",
      ),
    enabled: hydrated,
  });

  // Scope storage by OpenAPI title@version so two apps on :9100 don't share workspace
  useEffect(() => {
    if (!metaQ.data?.title && !specQ.data?.info?.title) return;
    const scope = appScopeFromMeta({
      title: metaQ.data?.title || specQ.data?.info?.title,
      version: metaQ.data?.version || specQ.data?.info?.version,
    });
    setAppScope(scope);
  }, [metaQ.data?.title, metaQ.data?.version, specQ.data?.info?.title, specQ.data?.info?.version, setAppScope]);

  useEffect(() => {
    if (!specQ.data) return;
    seedFromOpenApi(specQ.data, metaQ.data?.title);
  }, [
    specQ.data,
    metaQ.data?.title,
    seedFromOpenApi,
    doc.settings.hideAdminApis,
    appScope,
    // Re-seed if a mode switch / reset left collections empty
    doc.collections.length,
  ]);

  // Keep platform env coupled to AdminBoard host + session
  useEffect(() => {
    const base = metaQ.data?.base_url || (typeof window !== "undefined" ? window.location.origin : "");
    if (!base || !hydrated) return;
    syncPlatformEnv({ baseUrl: base, username });
  }, [metaQ.data?.base_url, username, hydrated, syncPlatformEnv]);

  const selected = findRequest(ui.selectedRequestId);
  const env = activeEnv();
  const last = selected ? ui.lastResponseByRequest[selected.id] : undefined;

  const previewUrl = useMemo(() => {
    if (!selected) return "";
    try {
      // lightweight preview without full query build
      let tpl = selected.url;
      for (const p of selected.params.filter((x) => x.in === "path")) {
        tpl = tpl.replace(`{${p.key}}`, p.value || `{${p.key}}`);
      }
      return resolveRequestUrl(tpl, env);
    } catch {
      return selected.url;
    }
  }, [selected, env]);

  const filteredFolders = useMemo(() => {
    const q = ui.search.trim().toLowerCase();
    const col = doc.collections[0];
    if (!col) return [];
    return col.folders
      .map((f) => ({
        ...f,
        requests: f.requests.filter((r) => {
          if (!q) return true;
          return (
            r.name.toLowerCase().includes(q) ||
            r.path.toLowerCase().includes(q) ||
            r.method.toLowerCase().includes(q) ||
            (r.meta.tag || "").toLowerCase().includes(q)
          );
        }),
      }))
      .filter((f) => f.requests.length > 0);
  }, [doc.collections, ui.search]);

  const flatVisible = useMemo(
    () => filteredFolders.flatMap((f) => f.requests),
    [filteredFolders],
  );

  const onSend = useCallback(async () => {
    if (!selected) return;
    setSending(true);
    try {
      const res = await executeRequest(
        selected,
        env,
        {
          profile: auth.authProfile,
          bearer: auth.bearer,
          apiKey: auth.apiKey,
          apiKeyHeader: auth.apiKeyHeader,
          authorization,
          csrfToken,
        },
        doc.settings.timeoutMs,
      );
      setLastResponse(selected.id, res);
      pushHistory({
        requestId: selected.id,
        name: selected.name,
        method: selected.method,
        url: previewUrl,
        at: new Date().toISOString(),
        response: res,
      });
    } catch (e) {
      toast(e instanceof Error ? e.message : "Request failed", "error");
    } finally {
      setSending(false);
    }
  }, [
    selected,
    env,
    auth,
    authorization,
    csrfToken,
    doc.settings.timeoutMs,
    previewUrl,
    setSending,
    setLastResponse,
    pushHistory,
    toast,
  ]);

  const onSaveResponse = useCallback(() => {
    if (!selected || !last) {
      toast("Send a request first", "error");
      return;
    }
    const name = window.prompt("Name this response", `${selected.name} · ${last.status}`);
    if (!name) return;
    saveResponse(name, selected.id, last);
    toast("Response saved");
  }, [selected, last, saveResponse, toast]);

  const onCopyCurl = useCallback(async () => {
    if (!selected) return;
    try {
      await copyText(
        toCurl(selected, env, {
          profile: auth.authProfile,
          bearer: auth.bearer,
          apiKey: auth.apiKey,
          apiKeyHeader: auth.apiKeyHeader,
          authorization,
          csrfToken,
        }),
      );
      toast("cURL copied");
    } catch {
      toast("Copy failed", "error");
    }
  }, [selected, env, auth, authorization, csrfToken, toast]);

  const onDownloadOpenapi = useCallback(async () => {
    if (!specQ.data) return;
    const blob = new Blob([JSON.stringify(specQ.data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "openapi.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [specQ.data]);

  const onDownloadCollection = useCallback(async () => {
    try {
      let r = await apiFetch("/openapi/collection");
      if (r.status === 404) r = await apiFetch("/openapi/postman");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "api-collection.json";
      a.click();
      URL.revokeObjectURL(url);
      toast("Collection downloaded");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Export failed", "error");
    }
  }, [toast]);

  const patchSelected = (patch: Partial<ForgeRequest>) => {
    if (!selected) return;
    updateRequest(selected.id, patch);
  };

  if (!hydrated) {
    return (
      <div className="ab-workspace" data-testid="apidocs-page">
        <p className="muted" style={{ margin: 24 }}>
          Loading Forge client…
        </p>
      </div>
    );
  }

  return (
    <div className="ab-workspace" data-testid="apidocs-page">
      {/* ── Sidebar ── */}
      <aside className="ab-sidebar" data-testid="apidocs-op-list">
        <div className="ab-sidebar-head">
          <div className="ab-sidebar-title">
            <strong>Forge client</strong>
            <span className="muted">
              {flatVisible.length} req
              {metaQ.data ? ` · ${metaQ.data.operations} openapi` : ""}
            </span>
          </div>

          <div className="ab-mode-row">
            <button
              type="button"
              className={`ab-mode-btn${doc.mode === "sandbox" ? " is-on" : ""}`}
              onClick={() => setMode("sandbox")}
              title="Tab session only (sessionStorage). Switching modes keeps your API list."
            >
              Sandbox
            </button>
            <button
              type="button"
              className={`ab-mode-btn${doc.mode === "workspace" ? " is-on" : ""}`}
              onClick={() => setMode("workspace")}
              title="Saved in this browser: localStorage key phzyx.forge.client.v1"
            >
              Workspace
            </button>
          </div>
          <p className="ab-storage-hint muted">
            {doc.mode === "workspace" ? (
              <>
                Browser <code className="mono">localStorage</code>
                <span className="ab-storage-key"> {workspaceStorageKey(appScope)}</span>
              </>
            ) : (
              <>
                Tab <code className="mono">sessionStorage</code> · scope{" "}
                <span className="ab-storage-key">{appScope}</span>
              </>
            )}
          </p>

          <div className="ab-env-row">
            <label className="ab-env-label">
              <span className="muted">Env</span>
              <select
                className="input ab-env-select"
                value={doc.activeEnvironmentId}
                onChange={(e) => setActiveEnvironmentId(e.target.value)}
                data-testid="forge-env"
              >
                {doc.environments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                const name = window.prompt("Environment name", "Staging");
                if (name) addEnvironment(name);
              }}
            >
              +
            </button>
          </div>

          <input
            className="input ab-sidebar-search"
            placeholder="Filter requests…"
            value={ui.search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="apidocs-search"
          />

          <label className="ab-toggle-row">
            <input
              type="checkbox"
              checked={doc.settings.hideAdminApis}
              onChange={(e) => setHideAdminApis(e.target.checked)}
            />
            <span>Hide AdminBoard APIs</span>
          </label>
        </div>

        <div className="ab-folder-tree">
          {specQ.isLoading && <p className="muted ab-sidebar-empty">Loading OpenAPI…</p>}
          {specQ.isError && (
            <p className="muted ab-sidebar-empty">
              OpenAPI failed. Sign in via AdminBoard if required.
            </p>
          )}
          {filteredFolders.map((folder) => (
            <div key={folder.id} className="ab-folder">
              <div className="ab-folder-head static">
                <span className="ab-folder-name">{folder.name}</span>
                <span className="ab-folder-count muted">{folder.requests.length}</span>
              </div>
              <ul className="ab-req-list">
                {folder.requests.map((op) => {
                  const on = ui.selectedRequestId === op.id;
                  const ran = ui.lastResponseByRequest[op.id];
                  return (
                    <li key={op.id}>
                      <button
                        type="button"
                        className={`ab-req-item${on ? " is-active" : ""}${op.meta.deprecated ? " is-deprecated" : ""}`}
                        onClick={() => selectRequest(op.id)}
                        data-testid={`apidocs-op-${op.method.toLowerCase()}-${op.path.replace(/\W+/g, "-")}`}
                      >
                        <span className={methodClass(op.method)}>{op.method}</span>
                        <span className="ab-req-label">{op.name}</span>
                        {ran && (
                          <span
                            className={`ab-req-status ${
                              ran.status < 300 ? "ok" : ran.status < 400 ? "redirect" : "err"
                            }`}
                          >
                            {ran.status}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {!specQ.isLoading && !filteredFolders.length && (
            <p className="muted ab-sidebar-empty">No requests match.</p>
          )}

          {doc.history.length > 0 && (
            <div className="ab-history-block">
              <div className="ab-folder-head static">
                <span className="ab-folder-name">History</span>
                <span className="ab-folder-count muted">{doc.history.length}</span>
              </div>
              <ul className="ab-req-list">
                {doc.history.slice(0, 12).map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      className="ab-req-item"
                      onClick={() => selectRequest(h.requestId)}
                      title={h.url}
                    >
                      <span className={methodClass(h.method)}>{h.method}</span>
                      <span className="ab-req-label">{h.name}</span>
                      <span
                        className={`ab-req-status ${
                          h.response.status < 300
                            ? "ok"
                            : h.response.status < 400
                              ? "redirect"
                              : "err"
                        }`}
                      >
                        {h.response.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {doc.savedResponses.length > 0 && (
            <div className="ab-history-block">
              <div className="ab-folder-head static">
                <span className="ab-folder-name">Saved responses</span>
                <span className="ab-folder-count muted">{doc.savedResponses.length}</span>
              </div>
              <ul className="ab-req-list">
                {doc.savedResponses.map((s) => (
                  <li key={s.id} className="ab-saved-row">
                    <button
                      type="button"
                      className="ab-req-item"
                      onClick={() => {
                        selectRequest(s.requestId);
                        setLastResponse(s.requestId, s.response);
                      }}
                    >
                      <span className="ab-req-label">{s.name}</span>
                      <span
                        className={`ab-req-status ${
                          s.response.status < 300 ? "ok" : "err"
                        }`}
                      >
                        {s.response.status}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm ab-saved-del"
                      onClick={() => deleteSavedResponse(s.id)}
                      title="Delete"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="ab-sidebar-foot">
          <button type="button" className="btn btn-sm" onClick={exportWorkspace}>
            Export JSON
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => fileRef.current?.click()}
          >
            Import
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              void f.text().then((t) => {
                try {
                  importWorkspace(t);
                  toast("Workspace imported");
                } catch (err) {
                  toast(err instanceof Error ? err.message : "Import failed", "error");
                }
              });
              e.target.value = "";
            }}
          />
          <button type="button" className="btn btn-sm" onClick={onDownloadOpenapi} disabled={!specQ.data}>
            OpenAPI
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => void onDownloadCollection()}>
            Collection
          </button>
          {doc.mode === "sandbox" && (
            <button type="button" className="btn btn-sm" onClick={resetSandbox}>
              Reset
            </button>
          )}
        </div>
      </aside>

      {/* ── Console ── */}
      <main className="ab-console">
        {!selected ? (
          <div className="ab-empty-console">
            <div className="ab-empty-inner">
              <p className="ab-kicker">Forge API Client</p>
              <h2>Pick a request</h2>
              <p className="sub">
                Live OpenAPI from this server ·{" "}
                <strong>{doc.mode === "sandbox" ? "Sandbox" : "Workspace"}</strong> mode · env{" "}
                <strong>{env?.name || "—"}</strong>
                {doc.settings.hideAdminApis ? " · AdminBoard APIs hidden" : ""}.
                Sample bodies are generated from schemas. Export the whole client as JSON anytime.
              </p>
              {username && (
                <p className="muted" style={{ fontSize: 13 }}>
                  Signed in as {username} — session auth available on Send.
                </p>
              )}
              <div className="ab-card-grid" data-testid="apidocs-card-grid">
                {flatVisible.slice(0, 18).map((op) => (
                  <button
                    key={op.id}
                    type="button"
                    className={`ab-op-card${op.meta.deprecated ? " is-deprecated" : ""}`}
                    onClick={() => selectRequest(op.id)}
                  >
                    <div className="ab-op-card-top">
                      <span className={methodClass(op.method)}>{op.method}</span>
                      <span className="ab-op-card-tag muted">{op.meta.tag}</span>
                    </div>
                    <code className="ab-op-card-path mono">{op.path}</code>
                    <span className="ab-op-card-sum">{op.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="ab-urlbar" data-testid="apidocs-detail">
              <select
                className={`input ab-method-select ${methodClass(selected.method)}`}
                value={selected.method}
                onChange={(e) =>
                  patchSelected({ method: e.target.value as HttpMethod })
                }
              >
                {(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] as const).map(
                  (m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ),
                )}
              </select>
              <EnvAwareUrlInput
                value={selected.url}
                onChange={(url) => patchSelected({ url })}
                env={env}
                onOpenEnv={openEnvVar}
                data-testid="apidocs-url"
              />
              <button
                type="button"
                className="btn btn-primary ab-send"
                disabled={ui.sending}
                onClick={() => void onSend()}
                data-testid="apidocs-send"
              >
                {ui.sending ? "…" : "Send"}
              </button>
              <button type="button" className="btn btn-sm" onClick={() => void onCopyCurl()}>
                cURL
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={!last}
                onClick={onSaveResponse}
              >
                Save resp
              </button>
            </div>

            <div className="ab-req-meta">
              <h1 className="ab-req-title">{selected.name}</h1>
              <code className="mono muted ab-req-path">
                <EnvHighlightText text={selected.url} env={env} onOpenEnv={openEnvVar} />
                {previewUrl && previewUrl !== selected.url && (
                  <span className="ab-req-resolved" title="Resolved URL">
                    {" → "}
                    {previewUrl}
                  </span>
                )}
              </code>
              {selected.meta.userEdited && (
                <span className="ab-pill">Edited</span>
              )}
              {selected.meta.deprecated && (
                <span className="ab-pill ab-pill-warn">Deprecated</span>
              )}
            </div>

            <div className="ab-tabs" role="tablist">
              {(
                [
                  ["params", "Params"],
                  ["headers", "Headers"],
                  ["body", "Body"],
                  ["auth", "Auth"],
                  ["env", "Env"],
                  ["docs", "Docs"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  className={`ab-tab${ui.reqTab === id ? " is-on" : ""}`}
                  onClick={() => setReqTab(id)}
                >
                  {label}
                  {id === "params" && selected.params.length > 0 && (
                    <span className="ab-tab-badge">{selected.params.length}</span>
                  )}
                  {id === "body" && selected.body.mode !== "none" && (
                    <span className="ab-tab-badge">JSON</span>
                  )}
                </button>
              ))}
            </div>

            <div className="ab-tab-panel">
              {ui.reqTab === "params" && (
                <ParamTable
                  rows={selected.params}
                  onChange={(params) => patchSelected({ params })}
                />
              )}
              {ui.reqTab === "headers" && (
                <KvTable
                  rows={selected.headers}
                  onChange={(headers) => patchSelected({ headers })}
                  emptyHint="No headers. Add Content-Type or custom keys."
                />
              )}
              {ui.reqTab === "body" && (
                <div className="ab-body-tab">
                  <div className="ab-body-toolbar">
                    <select
                      className="input"
                      style={{ width: "auto", height: 32 }}
                      value={selected.body.mode}
                      onChange={(e) =>
                        patchSelected({
                          body: {
                            ...selected.body,
                            mode: e.target.value as "none" | "json" | "raw",
                          },
                        })
                      }
                    >
                      <option value="none">none</option>
                      <option value="json">raw · JSON</option>
                      <option value="raw">raw · text</option>
                    </select>
                    <span className="muted">Supports {"{{variables}}"}</span>
                  </div>
                  {selected.body.mode !== "none" ? (
                    <textarea
                      className="input ab-body mono"
                      value={selected.body.raw}
                      onChange={(e) =>
                        patchSelected({
                          body: { ...selected.body, raw: e.target.value },
                        })
                      }
                      rows={14}
                      spellCheck={false}
                      data-testid="apidocs-body"
                    />
                  ) : (
                    <p className="muted ab-tab-empty">No body for this request.</p>
                  )}
                </div>
              )}
              {ui.reqTab === "auth" && (
                <div className="ab-auth-tab" data-testid="apiboard-auth">
                  <div className="ab-auth-grid">
                    <label className="field">
                      <span>Workspace auth (inherit)</span>
                      <select
                        className="input"
                        value={auth.authProfile}
                        onChange={(e) =>
                          setAuth({
                            authProfile: e.target.value as typeof auth.authProfile,
                          })
                        }
                        data-testid="apidocs-auth-profile"
                      >
                        <option value="session">Admin session</option>
                        <option value="bearer">Bearer (token / {"{{token}}"})</option>
                        <option value="apikey">API key</option>
                        <option value="none">None</option>
                      </select>
                    </label>
                    {auth.authProfile === "bearer" && (
                      <label className="field">
                        <span>Bearer token</span>
                        <input
                          className="input"
                          value={auth.bearer}
                          onChange={(e) => setAuth({ bearer: e.target.value })}
                          placeholder="or set env token"
                          autoComplete="off"
                        />
                      </label>
                    )}
                    {auth.authProfile === "apikey" && (
                      <>
                        <label className="field">
                          <span>Header</span>
                          <input
                            className="input"
                            value={auth.apiKeyHeader}
                            onChange={(e) => setAuth({ apiKeyHeader: e.target.value })}
                          />
                        </label>
                        <label className="field">
                          <span>Key</span>
                          <input
                            className="input"
                            value={auth.apiKey}
                            onChange={(e) => setAuth({ apiKey: e.target.value })}
                            autoComplete="off"
                          />
                        </label>
                      </>
                    )}
                    <label className="field">
                      <span>Request auth override</span>
                      <select
                        className="input"
                        value={selected.auth.type}
                        onChange={(e) => {
                          const t = e.target.value as ForgeRequest["auth"]["type"];
                          if (t === "bearer") patchSelected({ auth: { type: "bearer", token: "" } });
                          else if (t === "apikey")
                            patchSelected({
                              auth: { type: "apikey", header: "X-API-Key", value: "" },
                            });
                          else patchSelected({ auth: { type: t as "inherit" | "none" | "session" } });
                        }}
                      >
                        <option value="inherit">Inherit workspace</option>
                        <option value="session">Session</option>
                        <option value="bearer">Bearer</option>
                        <option value="apikey">API key</option>
                        <option value="none">None</option>
                      </select>
                    </label>
                  </div>
                  {username && (
                    <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
                      Signed in as {username}
                    </p>
                  )}
                </div>
              )}
              {ui.reqTab === "env" && env && (
                <EnvEditor
                  variables={env.variables}
                  focusKey={ui.focusEnvKey}
                  envName={env.name}
                  onChange={(variables) => updateEnvironment({ ...env, variables })}
                />
              )}
              {ui.reqTab === "docs" && (
                <div className="ab-docs-tab">
                  {selected.docs.description && (
                    <p className="ab-desc">{selected.docs.description}</p>
                  )}
                  {selected.docs.operationId && (
                    <p className="muted mono ab-opid">
                      operationId: {selected.docs.operationId}
                    </p>
                  )}
                  {selected.docs.responses && selected.docs.responses.length > 0 && (
                    <div className="ab-block">
                      <h3>Documented responses</h3>
                      <ul className="ab-responses-doc">
                        {selected.docs.responses.map((r) => (
                          <li key={r.code}>
                            <code className="ab-code-status">{r.code}</code>
                            <span>{r.description || "—"}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {!selected.docs.description &&
                    !(selected.docs.responses && selected.docs.responses.length) && (
                      <p className="muted ab-tab-empty">No docs for this operation.</p>
                    )}
                </div>
              )}
            </div>

            <ResponsePane last={last} />
          </>
        )}
      </main>
    </div>
  );
}

function ParamTable({
  rows,
  onChange,
}: {
  rows: RequestParam[];
  onChange: (rows: RequestParam[]) => void;
}) {
  if (!rows.length) {
    return <p className="muted ab-tab-empty">No path or query parameters.</p>;
  }
  return (
    <table className="ab-param-table">
      <thead>
        <tr>
          <th></th>
          <th>Key</th>
          <th>Value</th>
          <th>In</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => (
          <tr key={`${p.in}:${p.key}:${i}`}>
            <td>
              <input
                type="checkbox"
                checked={p.enabled}
                onChange={(e) => {
                  const next = [...rows];
                  next[i] = { ...p, enabled: e.target.checked };
                  onChange(next);
                }}
              />
            </td>
            <td>
              <code className="mono">
                {p.key}
                {p.required ? <span className="ab-req">*</span> : null}
              </code>
            </td>
            <td>
              <input
                className="input ab-cell-input"
                value={p.value}
                onChange={(e) => {
                  const next = [...rows];
                  next[i] = { ...p, value: e.target.value, enabled: true };
                  onChange(next);
                }}
                placeholder={p.required ? "required" : "optional"}
              />
            </td>
            <td className="muted">{p.in}</td>
            <td className="muted ab-param-desc-cell">{p.description || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KvTable({
  rows,
  onChange,
  emptyHint,
}: {
  rows: KvRow[];
  onChange: (rows: KvRow[]) => void;
  emptyHint: string;
}) {
  return (
    <div>
      <table className="ab-param-table">
        <thead>
          <tr>
            <th></th>
            <th>Key</th>
            <th>Value</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>
                <input
                  type="checkbox"
                  checked={r.enabled}
                  onChange={(e) => {
                    const next = [...rows];
                    next[i] = { ...r, enabled: e.target.checked };
                    onChange(next);
                  }}
                />
              </td>
              <td>
                <input
                  className="input ab-cell-input"
                  value={r.key}
                  onChange={(e) => {
                    const next = [...rows];
                    next[i] = { ...r, key: e.target.value };
                    onChange(next);
                  }}
                />
              </td>
              <td>
                <input
                  className="input ab-cell-input"
                  value={r.value}
                  onChange={(e) => {
                    const next = [...rows];
                    next[i] = { ...r, value: e.target.value };
                    onChange(next);
                  }}
                />
              </td>
              <td>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => onChange(rows.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted ab-tab-empty">{emptyHint}</p>}
      <button
        type="button"
        className="btn btn-sm"
        style={{ marginTop: 8 }}
        onClick={() =>
          onChange([...rows, { key: "", value: "", enabled: true }])
        }
      >
        Add header
      </button>
    </div>
  );
}

function EnvEditor({
  variables,
  onChange,
  focusKey,
  envName,
}: {
  variables: EnvVariable[];
  onChange: (v: EnvVariable[]) => void;
  focusKey?: string | null;
  envName?: string;
}) {
  const focusRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!focusKey) return;
    const t = window.setTimeout(() => {
      focusRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      focusRef.current?.focus();
    }, 50);
    return () => window.clearTimeout(t);
  }, [focusKey]);

  const patch = (i: number, next: EnvVariable) => {
    const copy = [...variables];
    copy[i] = next;
    onChange(copy);
  };

  return (
    <div className="ab-env-editor" data-testid="forge-env-editor">
      <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        Environment <strong>{envName || "active"}</strong>. Use{" "}
        <code className="mono">{"{{baseUrl}}"}</code>, <code className="mono">{"{{token}}"}</code> in
        URL, headers, and body. Platform rows are bound to this AdminBoard server and stay
        read-only. Hover a highlighted var in the URL bar to preview its value; click it to jump
        here.
      </p>
      <table className="ab-param-table">
        <thead>
          <tr>
            <th></th>
            <th>Variable</th>
            <th>Value</th>
            <th>Secret</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {variables.map((v, i) => {
            const keyLocked = isEnvKeyLocked(v);
            const valueEditable = isEnvValueEditable(v);
            const isPlatform = v.source === "platform";
            const focused = focusKey === v.key;
            return (
              <tr
                key={`${v.key}-${i}`}
                className={
                  focused
                    ? "ab-env-row is-focus"
                    : isPlatform
                      ? "ab-env-row is-platform"
                      : "ab-env-row"
                }
                data-env-key={v.key}
              >
                <td>
                  <input
                    type="checkbox"
                    checked={v.enabled}
                    disabled={keyLocked && isPlatform}
                    title={
                      keyLocked && isPlatform
                        ? "Platform variables stay enabled"
                        : "Include in resolution"
                    }
                    onChange={(e) => patch(i, { ...v, enabled: e.target.checked })}
                  />
                </td>
                <td>
                  <div className="ab-env-key-cell">
                    <input
                      className="input ab-cell-input mono"
                      value={v.key}
                      disabled={keyLocked}
                      readOnly={keyLocked}
                      title={keyLocked ? "Key is locked" : "Variable name"}
                      onChange={(e) => {
                        if (keyLocked) return;
                        patch(i, { ...v, key: e.target.value });
                      }}
                    />
                    {isPlatform && <span className="ab-env-src-badge">platform</span>}
                    {!valueEditable && !isPlatform && (
                      <span className="ab-env-src-badge ab-env-src-badge-muted">read-only</span>
                    )}
                  </div>
                </td>
                <td>
                  {valueEditable ? (
                    <input
                      ref={focused ? focusRef : undefined}
                      className="input ab-cell-input mono"
                      type={v.secret ? "password" : "text"}
                      value={v.value}
                      placeholder={v.description || ""}
                      onChange={(e) => patch(i, { ...v, value: e.target.value })}
                    />
                  ) : (
                    <div
                      ref={focused ? (el) => {
                        focusRef.current = el as unknown as HTMLInputElement;
                      } : undefined}
                      className="ab-env-readonly mono"
                      title={v.description || "Platform-bound value"}
                      tabIndex={focused ? 0 : -1}
                    >
                      {v.secret && v.value ? "••••••••" : v.value || "—"}
                    </div>
                  )}
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={Boolean(v.secret)}
                    disabled={keyLocked && isPlatform}
                    onChange={(e) => {
                      if (keyLocked && isPlatform) return;
                      patch(i, { ...v, secret: e.target.checked });
                    }}
                  />
                </td>
                <td>
                  {!keyLocked && (
                    <button
                      type="button"
                      className="btn btn-sm"
                      title="Remove variable"
                      onClick={() => onChange(variables.filter((_, j) => j !== i))}
                    >
                      ×
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button
        type="button"
        className="btn btn-sm"
        style={{ marginTop: 8 }}
        onClick={() =>
          onChange([
            ...variables,
            {
              key: "",
              value: "",
              enabled: true,
              source: "user",
              locked: false,
              editable: true,
            },
          ])
        }
      >
        Add variable
      </button>
    </div>
  );
}

function ResponsePane({ last }: { last?: ResponseSnapshot }) {
  const toast = useShellStore((s) => s.toast);
  return (
    <div className="ab-response-pane" data-testid="apidocs-response">
      <div className="ab-response-head">
        <h3>Response</h3>
        {last ? (
          <>
            <span
              className={`ab-status ${
                last.status < 300 ? "ok" : last.status < 400 ? "redirect" : "err"
              }`}
            >
              {last.status} {last.statusText}
            </span>
            <span className="muted">{last.ms} ms</span>
            <span className="muted">{last.bodySize.toLocaleString()} B</span>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() =>
                void copyText(last.bodyText).then(() => toast("Copied"))
              }
            >
              Copy
            </button>
          </>
        ) : (
          <span className="muted">Hit Send to see a response</span>
        )}
      </div>
      {last && (
        <>
          <details className="ab-headers-details">
            <summary className="muted">
              Headers ({Object.keys(last.headers).length})
            </summary>
            <pre className="ab-pre mono">
              {Object.entries(last.headers)
                .map(([k, v]) => `${k}: ${v}`)
                .join("\n") || "(none)"}
            </pre>
          </details>
          <pre className="ab-pre mono ab-response-body">
            {pretty(last.bodyText) || "(empty)"}
          </pre>
        </>
      )}
    </div>
  );
}
