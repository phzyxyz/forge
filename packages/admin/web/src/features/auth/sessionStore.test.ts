import { beforeEach, describe, expect, it, vi } from "vitest";

// jsdom sessionStorage
beforeEach(() => {
  sessionStorage.clear();
  vi.resetModules();
});

describe("sessionStore diamond D1", () => {
  it("setSession persists and logout clears", async () => {
    const { useSessionStore, SESSION_MODE } = await import("./sessionStore");
    useSessionStore.getState().setSession("admin", "csrf-token-demo");
    expect(useSessionStore.getState().authorization).toBe(SESSION_MODE);
    expect(useSessionStore.getState().username).toBe("admin");
    expect(useSessionStore.getState().csrfToken).toBe("csrf-token-demo");
    useSessionStore.getState().logout();
    expect(useSessionStore.getState().authorization).toBeNull();
    expect(sessionStorage.getItem("phzyx.admin.auth")).toBeNull();
  });

  it("login helper marks session mode", async () => {
    const { useSessionStore, SESSION_MODE } = await import("./sessionStore");
    useSessionStore.getState().login("admin", "phzyx");
    expect(useSessionStore.getState().authorization).toBe(SESSION_MODE);
  });

  it("emitSessionExpired only fires once for parallel 401s", async () => {
    const { useSessionStore, emitSessionExpired, SESSION_EXPIRED } = await import("./sessionStore");
    useSessionStore.getState().setSession("admin", "x");
    let count = 0;
    const handler = () => {
      count += 1;
    };
    window.addEventListener(SESSION_EXPIRED, handler);
    emitSessionExpired();
    emitSessionExpired();
    emitSessionExpired();
    expect(count).toBe(1);
    expect(useSessionStore.getState().authorization).toBeNull();
    window.removeEventListener(SESSION_EXPIRED, handler);
  });

  it("emitSessionExpired no-ops without session", async () => {
    const { emitSessionExpired, SESSION_EXPIRED, useSessionStore } = await import("./sessionStore");
    useSessionStore.getState().logout();
    let count = 0;
    window.addEventListener(SESSION_EXPIRED, () => {
      count += 1;
    });
    emitSessionExpired();
    expect(count).toBe(0);
  });
});
