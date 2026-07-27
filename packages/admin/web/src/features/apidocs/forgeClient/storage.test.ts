import { beforeEach, describe, expect, it } from "vitest";
import { emptyDocument } from "./defaults";
import {
  clearDocumentStorage,
  loadDocument,
  parseImportJson,
  saveDocument,
} from "./storage";
import {
  FORGE_CLIENT_FORMAT,
  SANDBOX_STORAGE_KEY,
  WORKSPACE_STORAGE_KEY,
} from "./types";

function installMemoryStorage() {
  const make = () => {
    const map = new Map<string, string>();
    return {
      getItem: (k: string) => map.get(k) ?? null,
      setItem: (k: string, v: string) => {
        map.set(k, String(v));
      },
      removeItem: (k: string) => {
        map.delete(k);
      },
      clear: () => map.clear(),
      get length() {
        return map.size;
      },
      key: (i: number) => [...map.keys()][i] ?? null,
    };
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: make(),
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    value: make(),
    configurable: true,
    writable: true,
  });
}

beforeEach(() => {
  installMemoryStorage();
});

describe("forge client storage", () => {
  it("sandbox never writes workspace key", () => {
    const doc = emptyDocument("sandbox");
    doc.history = [
      {
        id: "h1",
        requestId: "r1",
        name: "x",
        method: "GET",
        url: "http://x",
        at: new Date().toISOString(),
        response: {
          status: 200,
          statusText: "OK",
          ms: 1,
          headers: {},
          bodyText: "{}",
          bodySize: 2,
        },
      },
    ];
    saveDocument(doc, "default");
    expect(localStorage.getItem(WORKSPACE_STORAGE_KEY)).toBeNull();
    expect(sessionStorage.getItem(SANDBOX_STORAGE_KEY)).toBeTruthy();
    const loaded = loadDocument("sandbox", "default");
    expect(loaded.history).toHaveLength(1);
  });

  it("workspace round-trips JSON in localStorage", () => {
    const doc = emptyDocument("workspace");
    doc.savedResponses = [
      {
        id: "s1",
        name: "sample",
        requestId: "r1",
        at: new Date().toISOString(),
        response: {
          status: 201,
          statusText: "Created",
          ms: 12,
          headers: { "content-type": "application/json" },
          bodyText: '{"ok":true}',
          bodySize: 11,
        },
      },
    ];
    saveDocument(doc, "default");
    expect(sessionStorage.getItem(SANDBOX_STORAGE_KEY)).toBeNull();
    const loaded = loadDocument("workspace", "default");
    expect(loaded.format).toBe(FORGE_CLIENT_FORMAT);
    expect(loaded.savedResponses[0]?.name).toBe("sample");
  });

  it("different app scopes do not overwrite each other", () => {
    const a = emptyDocument("workspace");
    a.savedResponses = [
      {
        id: "s1",
        name: "app-a",
        requestId: "r",
        at: new Date().toISOString(),
        response: {
          status: 200,
          statusText: "OK",
          ms: 1,
          headers: {},
          bodyText: "a",
          bodySize: 1,
        },
      },
    ];
    const b = emptyDocument("workspace");
    b.savedResponses = [
      {
        id: "s2",
        name: "app-b",
        requestId: "r",
        at: new Date().toISOString(),
        response: {
          status: 200,
          statusText: "OK",
          ms: 1,
          headers: {},
          bodyText: "b",
          bodySize: 1,
        },
      },
    ];
    saveDocument(a, "shop@1");
    saveDocument(b, "blog@2");
    expect(loadDocument("workspace", "shop@1").savedResponses[0]?.name).toBe("app-a");
    expect(loadDocument("workspace", "blog@2").savedResponses[0]?.name).toBe("app-b");
  });

  it("parseImportJson validates format", () => {
    expect(() => parseImportJson("{}")).toThrow(/valid/);
    const raw = JSON.stringify(emptyDocument("workspace"));
    const d = parseImportJson(raw);
    expect(d.mode).toBe("workspace");
  });

  it("clearDocumentStorage drops keys", () => {
    saveDocument(emptyDocument("workspace"), "default");
    saveDocument(emptyDocument("sandbox"), "default");
    clearDocumentStorage("workspace", "default");
    expect(localStorage.getItem(WORKSPACE_STORAGE_KEY)).toBeNull();
    clearDocumentStorage("sandbox", "default");
    expect(sessionStorage.getItem(SANDBOX_STORAGE_KEY)).toBeNull();
  });
});
