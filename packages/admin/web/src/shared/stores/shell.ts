import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  BrandingInfo,
  Density,
  DrawerMode,
  ThemePref,
  ToastItem,
} from "../api/types";
import { parseHash, toHash } from "../lib/hashRoute";
import type { AppRoute } from "../api/types";

export const DEFAULT_BRANDING: BrandingInfo = {
  site_title: "AdminBoard",
  header_title: "AdminBoard",
  header_subtitle: "Phzyx",
  show_powered_by: true,
};

type ShellState = {
  route: AppRoute;
  sidebarCollapsed: boolean;
  themePref: ThemePref;
  reducedTransparency: boolean;
  density: Density;
  demoMode: boolean;
  demoForced: boolean;
  apiVersion: string | null;
  branding: BrandingInfo;
  commandOpen: boolean;
  toasts: ToastItem[];
  drawer: {
    mode: DrawerMode;
    resource: string | null;
    identity: string | null;
    draft: Record<string, string>;
  };
  selectedIds: string[];
  globalSearch: string;
  setRoute: (route: AppRoute) => void;
  syncRouteFromHash: () => void;
  toggleSidebar: () => void;
  setThemePref: (t: ThemePref) => void;
  setReducedTransparency: (v: boolean) => void;
  setDensity: (d: Density) => void;
  setDemoMode: (v: boolean) => void;
  setDemoForced: (v: boolean) => void;
  setApiVersion: (v: string | null) => void;
  setBranding: (b: BrandingInfo) => void;
  setCommandOpen: (v: boolean) => void;
  toast: (message: string, kind?: "ok" | "error") => void;
  dismissToast: (id: string) => void;
  openDrawer: (
    mode: NonNullable<DrawerMode>,
    resource: string,
    identity?: string | null,
    draft?: Record<string, string>,
  ) => void;
  closeDrawer: () => void;
  setDraft: (draft: Record<string, string>) => void;
  setSelectedIds: (ids: string[]) => void;
  setGlobalSearch: (q: string) => void;
};

function resolvedTheme(pref: ThemePref): "stellar-dark" | "magical-white" {
  if (pref === "system-ambient") {
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "magical-white"
      : "stellar-dark";
  }
  return pref;
}

export function applyTheme(pref: ThemePref, reduced: boolean, density: Density) {
  document.documentElement.setAttribute("data-theme", resolvedTheme(pref));
  document.documentElement.classList.toggle("reduced-transparency", reduced);
  document.documentElement.classList.toggle("density-compact", density === "compact");
}

export const useShellStore = create<ShellState>()(
  persist(
    (set, get) => ({
      route: parseHash(typeof window !== "undefined" ? window.location.hash : "#/"),
      sidebarCollapsed: false,
      themePref: "stellar-dark",
      reducedTransparency: false,
      density: "comfortable",
      demoMode: false,
      demoForced: false,
      apiVersion: null,
      branding: DEFAULT_BRANDING,
      commandOpen: false,
      toasts: [],
      drawer: { mode: null, resource: null, identity: null, draft: {} },
      selectedIds: [],
      globalSearch: "",
      setRoute: (route) => {
        const hash = toHash(route);
        if (window.location.hash !== hash) window.location.hash = hash;
        set({ route, selectedIds: [] });
      },
      syncRouteFromHash: () => set({ route: parseHash(window.location.hash) }),
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setThemePref: (themePref) => {
        set({ themePref });
        applyTheme(themePref, get().reducedTransparency, get().density);
      },
      setReducedTransparency: (reducedTransparency) => {
        set({ reducedTransparency });
        applyTheme(get().themePref, reducedTransparency, get().density);
      },
      setDensity: (density) => {
        set({ density });
        applyTheme(get().themePref, get().reducedTransparency, density);
      },
      setDemoMode: (demoMode) => set({ demoMode }),
      setDemoForced: (demoForced) => set({ demoForced }),
      setApiVersion: (apiVersion) => set({ apiVersion }),
      setBranding: (branding) => {
        set({ branding });
        if (typeof document !== "undefined") {
          document.title = branding.site_title;
        }
      },
      setCommandOpen: (commandOpen) => set({ commandOpen }),
      toast: (message, kind = "ok") => {
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        set({ toasts: [...get().toasts, { id, message, kind }] });
        window.setTimeout(() => get().dismissToast(id), 2800);
      },
      dismissToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
      openDrawer: (mode, resource, identity = null, draft = {}) =>
        set({ drawer: { mode, resource, identity, draft } }),
      closeDrawer: () => set({ drawer: { mode: null, resource: null, identity: null, draft: {} } }),
      setDraft: (draft) => set({ drawer: { ...get().drawer, draft } }),
      setSelectedIds: (selectedIds) => set({ selectedIds }),
      setGlobalSearch: (globalSearch) => set({ globalSearch }),
    }),
    {
      name: "phzyx.admin.shell.v2",
      partialize: (s) => ({
        themePref: s.themePref,
        reducedTransparency: s.reducedTransparency,
        density: s.density,
        sidebarCollapsed: s.sidebarCollapsed,
        demoForced: s.demoForced,
      }),
    },
  ),
);

type ActivityState = {
  items: { id: string; at: number; text: string }[];
  push: (text: string) => void;
};

export const useActivityStore = create<ActivityState>((set, get) => ({
  items: [],
  push: (text) => {
    set({ items: [{ id: `${Date.now()}`, at: Date.now(), text }, ...get().items].slice(0, 20) });
  },
}));
