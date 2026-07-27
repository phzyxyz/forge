import { beforeEach, describe, expect, it } from "vitest";
import { emptyDocument, newId } from "./defaults";
import { useForgeClientStore } from "./store";
import type { ForgeCollection } from "./types";

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

const sampleCollection = (): ForgeCollection => ({
  id: newId("col"),
  name: "Live",
  source: "openapi",
  folders: [
    {
      id: newId("fld"),
      name: "orders",
      requests: [
        {
          id: newId("req"),
          name: "List",
          method: "GET",
          url: "{{baseUrl}}/orders",
          path: "/orders",
          headers: [],
          params: [],
          body: { mode: "none", raw: "" },
          auth: { type: "inherit" },
          docs: {},
          meta: { fromOpenApi: true, opKey: "get:/orders" },
        },
      ],
    },
  ],
});

beforeEach(() => {
  installMemoryStorage();
  useForgeClientStore.setState({
    doc: { ...emptyDocument("sandbox"), collections: [sampleCollection()] },
    ui: {
      selectedRequestId: null,
      selectedFolderId: null,
      search: "",
      reqTab: "params",
      lastResponseByRequest: {},
      sending: false,
      envEditorOpen: false,
      focusEnvKey: null,
    },
    hydrated: true,
  });
});

describe("setMode preserves collection", () => {
  it("sandbox → workspace keeps requests", () => {
    const before = useForgeClientStore.getState().doc.collections[0]!.folders[0]!.requests.length;
    expect(before).toBe(1);
    useForgeClientStore.getState().setMode("workspace");
    const doc = useForgeClientStore.getState().doc;
    expect(doc.mode).toBe("workspace");
    expect(doc.collections[0]!.folders[0]!.requests).toHaveLength(1);
    expect(localStorage.getItem("phzyx.forge.client.v1")).toBeTruthy();
  });

  it("workspace → sandbox keeps requests", () => {
    useForgeClientStore.getState().setMode("workspace");
    useForgeClientStore.getState().setMode("sandbox");
    const doc = useForgeClientStore.getState().doc;
    expect(doc.mode).toBe("sandbox");
    expect(doc.collections[0]!.folders[0]!.requests).toHaveLength(1);
  });
});
