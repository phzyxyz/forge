import { create } from "zustand";
import type { OpenApiSpec } from "../openapiTypes";
import { emptyDocument, newId } from "./defaults";
import { mergeOpenApiCollection, openApiToCollection } from "./openapiImport";
import {
  clearDocumentStorage,
  downloadJson,
  exportDocumentJson,
  loadDocument,
  localStorageHasWorkspace,
  parseImportJson,
  saveDocument,
} from "./storage";
import { normalizeEnvironment, syncPlatformIntoEnv, PLATFORM_ENV_ID } from "./envPlatform";
import type {
  ClientMode,
  ClientUiState,
  Environment,
  ForgeClientDocument,
  ForgeRequest,
  HistoryEntry,
  ResponseSnapshot,
  SavedResponse,
} from "./types";
import { normalizeEnvVariable } from "./types";

type GlobalAuthSlice = {
  authProfile: "session" | "bearer" | "apikey" | "none";
  bearer: string;
  apiKey: string;
  apiKeyHeader: string;
};

type ForgeClientState = {
  doc: ForgeClientDocument;
  ui: ClientUiState;
  auth: GlobalAuthSlice;
  hydrated: boolean;
  /** Isolates storage when multiple apps share host:port */
  appScope: string;

  hydrate: (mode?: ClientMode) => void;
  persist: () => void;
  setAppScope: (scope: string) => void;

  setMode: (mode: ClientMode, opts?: { carryState?: boolean }) => void;
  resetSandbox: () => void;
  clearWorkspace: () => void;

  seedFromOpenApi: (spec: OpenApiSpec, title?: string) => void;
  setHideAdminApis: (hide: boolean) => void;

  setActiveEnvironmentId: (id: string) => void;
  updateEnvironment: (env: Environment) => void;
  /** Refresh platform-bound vars from AdminBoard host meta. */
  syncPlatformEnv: (opts: { baseUrl: string; username?: string | null }) => void;
  addEnvironment: (name: string) => void;
  removeEnvironment: (id: string) => void;

  setSearch: (q: string) => void;
  setReqTab: (tab: ClientUiState["reqTab"]) => void;
  /** Jump to Env tab and highlight a variable (from URL chip). */
  openEnvVar: (key: string) => void;
  selectRequest: (id: string | null) => void;
  updateRequest: (id: string, patch: Partial<ForgeRequest>) => void;
  markRequestEdited: (id: string) => void;

  setAuth: (patch: Partial<GlobalAuthSlice>) => void;

  pushHistory: (entry: Omit<HistoryEntry, "id">) => void;
  setLastResponse: (requestId: string, res: ResponseSnapshot) => void;
  setSending: (v: boolean) => void;
  saveResponse: (name: string, requestId: string, res: ResponseSnapshot) => void;
  deleteSavedResponse: (id: string) => void;

  exportWorkspace: () => void;
  importWorkspace: (text: string) => void;

  findRequest: (id: string | null) => ForgeRequest | null;
  activeEnv: () => Environment | null;
  flatRequests: () => ForgeRequest[];
};

const initialUi = (): ClientUiState => ({
  selectedRequestId: null,
  selectedFolderId: null,
  search: "",
  reqTab: "params",
  lastResponseByRequest: {},
  sending: false,
  envEditorOpen: false,
  focusEnvKey: null,
});

function normalizeDocEnvs(doc: ForgeClientDocument): ForgeClientDocument {
  return {
    ...doc,
    environments: doc.environments.map(normalizeEnvironment),
  };
}

function mapRequest(
  doc: ForgeClientDocument,
  id: string,
  fn: (r: ForgeRequest) => ForgeRequest,
): ForgeClientDocument {
  return {
    ...doc,
    collections: doc.collections.map((c) => ({
      ...c,
      folders: c.folders.map((f) => ({
        ...f,
        requests: f.requests.map((r) => (r.id === id ? fn(r) : r)),
      })),
    })),
  };
}

function withBaseUrl(doc: ForgeClientDocument): ForgeClientDocument {
  const origin =
    typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8000";
  return normalizeDocEnvs({
    ...doc,
    environments: doc.environments.map((e) => {
      if (e.id === PLATFORM_ENV_ID) {
        return syncPlatformIntoEnv(e, { baseUrl: origin, forceBaseUrl: false });
      }
      return {
        ...e,
        variables: e.variables.map((v) => {
          const n = normalizeEnvVariable(v);
          if (n.key === "baseUrl" && !n.value) {
            return { ...n, value: origin };
          }
          return n;
        }),
      };
    }),
  });
}

export const useForgeClientStore = create<ForgeClientState>((set, get) => {
  const scope = () => get().appScope || "default";
  const persistDoc = (doc: ForgeClientDocument) => saveDocument(doc, scope());

  return {
    doc: emptyDocument("sandbox"),
    ui: initialUi(),
    auth: {
      authProfile: "session",
      bearer: "",
      apiKey: "",
      apiKeyHeader: "X-API-Key",
    },
    hydrated: false,
    appScope: "default",

    hydrate: (mode) => {
      const sc = "default";
      const resolved =
        mode ?? (localStorageHasWorkspace(sc) ? "workspace" : "sandbox");
      const doc = withBaseUrl(loadDocument(resolved, sc));
      set({
        doc: { ...doc, mode: resolved },
        ui: initialUi(),
        hydrated: true,
        appScope: sc,
      });
    },

    persist: () => {
      persistDoc(get().doc);
    },

    setAppScope: (nextScope) => {
      const sc = nextScope || "default";
      const prev = get().appScope || "default";
      if (sc === prev) return;
      const mode = get().doc.mode;
      // Persist current app under its own key, then load the target app's slot
      saveDocument(get().doc, prev);
      const loaded = withBaseUrl(loadDocument(mode, sc));
      set({
        appScope: sc,
        doc: { ...loaded, mode },
        ui: initialUi(),
      });
    },

    setMode: (mode, opts) => {
      const { doc } = get();
      if (mode === doc.mode) return;

      const carry = opts?.carryState !== false;

      if (carry) {
        const next: ForgeClientDocument = { ...doc, mode };
        set({ doc: next });
        persistDoc(next);
        return;
      }

      const loaded = loadDocument(mode, scope());
      set({
        doc: loaded,
        ui: {
          ...initialUi(),
          selectedRequestId: get().ui.selectedRequestId,
        },
      });
    },

    resetSandbox: () => {
      clearDocumentStorage("sandbox", scope());
      set({ doc: emptyDocument("sandbox"), ui: initialUi() });
    },

    clearWorkspace: () => {
      clearDocumentStorage("workspace", scope());
      if (get().doc.mode === "workspace") {
        set({ doc: emptyDocument("workspace"), ui: initialUi() });
      }
    },

    seedFromOpenApi: (spec, title) => {
      const { doc } = get();
      const built = openApiToCollection(
        spec,
        doc.settings,
        title || spec.info?.title || "Live OpenAPI",
      );
      const existing = doc.collections.find((c) => c.source === "openapi");
      const merged = mergeOpenApiCollection(existing, built);
      const others = doc.collections.filter((c) => c.source !== "openapi");
      const next: ForgeClientDocument = {
        ...doc,
        collections: [merged, ...others],
      };
      set({ doc: next });
      persistDoc(next);
    },

    setHideAdminApis: (hide) => {
      const next = {
        ...get().doc,
        settings: { ...get().doc.settings, hideAdminApis: hide },
      };
      set({ doc: next });
      persistDoc(next);
    },

    setActiveEnvironmentId: (id) => {
      const next = { ...get().doc, activeEnvironmentId: id };
      set({ doc: next });
      persistDoc(next);
    },

    updateEnvironment: (env) => {
      const doc = get().doc;
      const normalized = normalizeEnvironment(env);
      const next = {
        ...doc,
        environments: doc.environments.map((e) =>
          e.id === normalized.id ? normalized : e,
        ),
      };
      set({ doc: next });
      persistDoc(next);
    },

    syncPlatformEnv: ({ baseUrl, username }) => {
      const doc = get().doc;
      const next = {
        ...doc,
        environments: doc.environments.map((e) =>
          e.id === PLATFORM_ENV_ID
            ? syncPlatformIntoEnv(e, { baseUrl, username, forceBaseUrl: true })
            : e,
        ),
      };
      set({ doc: next });
      persistDoc(next);
    },

    addEnvironment: (name) => {
      const doc = get().doc;
      const origin =
        typeof window !== "undefined" ? window.location.origin : "";
      const env: Environment = normalizeEnvironment({
        id: newId("env"),
        name,
        variables: [
          {
            key: "baseUrl",
            value: origin,
            enabled: true,
            source: "user",
            locked: true,
            editable: true,
            description: "Custom origin (CORS required for other hosts)",
          },
        ],
      });
      const next = { ...doc, environments: [...doc.environments, env] };
      set({ doc: next });
      persistDoc(next);
    },

    removeEnvironment: (id) => {
      const doc = get().doc;
      if (doc.environments.length <= 1) return;
      const environments = doc.environments.filter((e) => e.id !== id);
      const activeEnvironmentId =
        doc.activeEnvironmentId === id
          ? environments[0]!.id
          : doc.activeEnvironmentId;
      const next = { ...doc, environments, activeEnvironmentId };
      set({ doc: next });
      persistDoc(next);
    },

    setSearch: (q) => set({ ui: { ...get().ui, search: q } }),
    setReqTab: (tab) => set({ ui: { ...get().ui, reqTab: tab, focusEnvKey: tab === "env" ? get().ui.focusEnvKey : null } }),
  openEnvVar: (key: string) =>
    set({ ui: { ...get().ui, reqTab: "env", focusEnvKey: key || null } }),

    selectRequest: (id) => {
      set({ ui: { ...get().ui, selectedRequestId: id } });
    },

    updateRequest: (id, patch) => {
      const next = mapRequest(get().doc, id, (r) => ({
        ...r,
        ...patch,
        meta: { ...r.meta, ...(patch.meta || {}), userEdited: true },
        body: patch.body ? { ...r.body, ...patch.body } : r.body,
        docs: patch.docs ? { ...r.docs, ...patch.docs } : r.docs,
      }));
      set({ doc: next });
      persistDoc(next);
    },

    markRequestEdited: (id) => {
      get().updateRequest(id, { meta: { userEdited: true } });
    },

    setAuth: (patch) => set({ auth: { ...get().auth, ...patch } }),

    pushHistory: (entry) => {
      const doc = get().doc;
      const row: HistoryEntry = { ...entry, id: newId("hist") };
      const history = [row, ...doc.history].slice(0, doc.settings.historyLimit);
      const next = { ...doc, history };
      set({ doc: next });
      persistDoc(next);
    },

    setLastResponse: (requestId, res) => {
      set({
        ui: {
          ...get().ui,
          lastResponseByRequest: {
            ...get().ui.lastResponseByRequest,
            [requestId]: res,
          },
        },
      });
    },

    setSending: (v) => set({ ui: { ...get().ui, sending: v } }),

    saveResponse: (name, requestId, res) => {
      const row: SavedResponse = {
        id: newId("saved"),
        name,
        requestId,
        at: new Date().toISOString(),
        response: res,
      };
      const next = {
        ...get().doc,
        savedResponses: [row, ...get().doc.savedResponses],
      };
      set({ doc: next });
      persistDoc(next);
    },

    deleteSavedResponse: (id) => {
      const next = {
        ...get().doc,
        savedResponses: get().doc.savedResponses.filter((s) => s.id !== id),
      };
      set({ doc: next });
      persistDoc(next);
    },

    exportWorkspace: () => {
      const doc = get().doc;
      downloadJson(
        `forge-client-${get().appScope}-${doc.mode}-${new Date().toISOString().slice(0, 10)}.json`,
        JSON.parse(exportDocumentJson(doc)),
      );
    },

    importWorkspace: (text) => {
      const parsed = parseImportJson(text);
      const mode = get().doc.mode;
      const next = { ...parsed, mode };
      set({ doc: next, ui: initialUi() });
      persistDoc(next);
    },

    findRequest: (id) => {
      if (!id) return null;
      for (const c of get().doc.collections) {
        for (const f of c.folders) {
          const r = f.requests.find((x) => x.id === id);
          if (r) return r;
        }
      }
      return null;
    },

    activeEnv: () => {
      const doc = get().doc;
      return doc.environments.find((e) => e.id === doc.activeEnvironmentId) || null;
    },

    flatRequests: () => {
      const out: ForgeRequest[] = [];
      for (const c of get().doc.collections) {
        for (const f of c.folders) out.push(...f.requests);
      }
      return out;
    },
  };
});
