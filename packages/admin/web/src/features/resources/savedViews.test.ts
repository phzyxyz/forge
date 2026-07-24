import { beforeEach, describe, expect, it } from "vitest";

function installMemoryStorage() {
  const map = new Map<string, string>();
  const storage = {
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
  Object.defineProperty(globalThis, "localStorage", {
    value: storage,
    configurable: true,
    writable: true,
  });
}

beforeEach(() => {
  installMemoryStorage();
});

describe("savedViews diamond D2", () => {
  it("round-trips filters and column order", async () => {
    const { saveView, loadSavedView } = await import("./savedViews");
    saveView("users", {
      filters: { active: "true" },
      columnVisibility: { email: false },
      columnOrder: ["name", "email", "id"],
      pageSize: 25,
      pagination: "keyset",
    });
    const v = loadSavedView("users");
    expect(v).not.toBeNull();
    expect(v!.filters).toEqual({ active: "true" });
    expect(v!.columnVisibility.email).toBe(false);
    expect(v!.columnOrder).toEqual(["name", "email", "id"]);
    expect(v!.pageSize).toBe(25);
    expect(v!.pagination).toBe("keyset");
  });

  it("clear removes view", async () => {
    const { saveView, loadSavedView, clearSavedView } = await import("./savedViews");
    saveView("users", {
      filters: {},
      columnVisibility: {},
      columnOrder: [],
      pageSize: 50,
      pagination: "offset",
    });
    clearSavedView("users");
    expect(loadSavedView("users")).toBeNull();
  });
});
