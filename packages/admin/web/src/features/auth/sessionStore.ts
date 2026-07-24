import { create } from "zustand";

const KEY = "phzyx.admin.auth";

/** Cookie-session marker (no password in storage). Optional Bearer for API clients. */
export const SESSION_MODE = "session";

type Stored = {
  username: string | null;
  authorization: string | null;
  csrfToken: string | null;
};

type SessionState = {
  username: string | null;
  /** "session" | "Bearer …" | legacy "Basic …" — truthy means signed in. */
  authorization: string | null;
  csrfToken: string | null;
  /** Prevents toast spam when many parallel requests 401. */
  expiredNotified: boolean;
  /** Mark SPA session after successful /auth/login (cookie set by server). */
  setSession: (username: string, csrfToken: string | null) => void;
  /** @deprecated prefer setSession — kept for unit tests of store shape. */
  login: (username: string, password: string) => void;
  logout: () => void;
  hydrate: () => void;
  markExpiredNotified: () => boolean;
  clearExpiredFlag: () => void;
};

function load(): Stored {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return { username: null, authorization: null, csrfToken: null };
    const data = JSON.parse(raw) as Stored;
    return {
      username: data.username ?? null,
      authorization: data.authorization ?? null,
      csrfToken: data.csrfToken ?? null,
    };
  } catch {
    return { username: null, authorization: null, csrfToken: null };
  }
}

function persist(s: Stored) {
  sessionStorage.setItem(
    KEY,
    JSON.stringify({
      username: s.username,
      authorization: s.authorization,
      csrfToken: s.csrfToken,
    }),
  );
}

export const useSessionStore = create<SessionState>((set, get) => ({
  username: null,
  authorization: null,
  csrfToken: null,
  expiredNotified: false,
  hydrate: () => set({ ...load(), expiredNotified: false }),
  setSession: (username, csrfToken) => {
    const payload = {
      username,
      authorization: SESSION_MODE,
      csrfToken,
      expiredNotified: false,
    };
    persist(payload);
    set(payload);
  },
  login: (username, _password) => {
    // Legacy helper used only by unit tests — real SPA uses setSession after /auth/login.
    get().setSession(username, null);
  },
  logout: () => {
    sessionStorage.removeItem(KEY);
    set({
      username: null,
      authorization: null,
      csrfToken: null,
      expiredNotified: false,
    });
  },
  /** @returns true if this call should show toast / handle UI (first 401 only). */
  markExpiredNotified: () => {
    if (get().expiredNotified) return false;
    set({ expiredNotified: true });
    return true;
  },
  clearExpiredFlag: () => set({ expiredNotified: false }),
}));

/** Event for 401 → force login */
export const SESSION_EXPIRED = "phzyx:session-expired";

export function emitSessionExpired() {
  const auth = useSessionStore.getState().authorization;
  if (!auth) return;
  // Only the first parallel 401 triggers UI handling
  if (!useSessionStore.getState().markExpiredNotified()) return;
  useSessionStore.getState().logout();
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED));
}
