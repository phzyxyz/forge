import { emptyDocument, isForgeClientDocument } from "./defaults";
import {
  SANDBOX_STORAGE_KEY,
  WORKSPACE_STORAGE_KEY,
  sandboxStorageKey,
  workspaceStorageKey,
  type ClientMode,
  type ForgeClientDocument,
} from "./types";

function readJson(storage: Storage, key: string): unknown | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

function writeJson(storage: Storage, key: string, value: unknown): void {
  storage.setItem(key, JSON.stringify(value));
}

/**
 * Load document for mode + app scope.
 * Scope isolates different apps that share the same origin (same host:port).
 */
export function loadDocument(
  mode: ClientMode,
  scope = "default",
): ForgeClientDocument {
  if (typeof window === "undefined") {
    return emptyDocument(mode);
  }
  if (mode === "workspace") {
    const key = workspaceStorageKey(scope);
    let raw = readJson(window.localStorage, key);
    // One-time legacy migrate: unscoped key → first real app scope
    if (!raw && scope !== "default") {
      const legacy = readJson(window.localStorage, WORKSPACE_STORAGE_KEY);
      if (isForgeClientDocument(legacy)) {
        raw = legacy;
        writeJson(window.localStorage, key, legacy);
      }
    }
    if (isForgeClientDocument(raw)) {
      return { ...raw, mode: "workspace" };
    }
    return emptyDocument("workspace");
  }
  const key = sandboxStorageKey(scope);
  let raw = readJson(window.sessionStorage, key);
  if (!raw && scope !== "default") {
    const legacy = readJson(window.sessionStorage, SANDBOX_STORAGE_KEY);
    if (isForgeClientDocument(legacy)) {
      raw = legacy;
      writeJson(window.sessionStorage, key, legacy);
    }
  }
  if (isForgeClientDocument(raw)) {
    return { ...raw, mode: "sandbox" };
  }
  return emptyDocument("sandbox");
}

/** Persist according to mode. Sandbox → sessionStorage; workspace → localStorage. */
export function saveDocument(doc: ForgeClientDocument, scope = "default"): void {
  if (typeof window === "undefined") return;
  const payload: ForgeClientDocument = {
    ...doc,
    format: "phzyx.forge.client",
    version: 1,
  };
  if (doc.mode === "workspace") {
    writeJson(window.localStorage, workspaceStorageKey(scope), payload);
    return;
  }
  writeJson(window.sessionStorage, sandboxStorageKey(scope), {
    ...payload,
    mode: "sandbox",
  });
}

export function clearDocumentStorage(mode: ClientMode, scope = "default"): void {
  if (typeof window === "undefined") return;
  if (mode === "workspace") {
    window.localStorage.removeItem(workspaceStorageKey(scope));
  } else {
    window.sessionStorage.removeItem(sandboxStorageKey(scope));
  }
}

export function exportDocumentJson(doc: ForgeClientDocument): string {
  return JSON.stringify(doc, null, 2);
}

export function parseImportJson(text: string): ForgeClientDocument {
  const raw = JSON.parse(text) as unknown;
  if (!isForgeClientDocument(raw)) {
    throw new Error("Not a valid phzyx.forge.client v1 document");
  }
  return raw;
}

export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function localStorageHasWorkspace(scope = "default"): boolean {
  if (typeof window === "undefined") return false;
  try {
    return Boolean(window.localStorage.getItem(workspaceStorageKey(scope)));
  } catch {
    return false;
  }
}
