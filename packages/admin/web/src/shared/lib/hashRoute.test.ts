import { describe, expect, it } from "vitest";
import { parseHash, toHash } from "./hashRoute";

describe("hashRoute", () => {
  it("round-trips routes", () => {
    const routes = [
      { page: "overview" as const },
      { page: "media" as const },
      { page: "settings" as const },
      { page: "login" as const },
      { page: "resource" as const, name: "users" },
    ];
    for (const r of routes) {
      expect(parseHash(toHash(r))).toEqual(r);
    }
  });
});
