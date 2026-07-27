import type { SavedView } from "../../shared/api/types";

const prefix = "phzyx.admin.view.";

export function loadSavedView(resource: string): SavedView | null {
  try {
    const raw = localStorage.getItem(prefix + resource);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SavedView>;
    return {
      filters: parsed.filters && typeof parsed.filters === "object" ? parsed.filters : {},
      columnVisibility:
        parsed.columnVisibility && typeof parsed.columnVisibility === "object"
          ? parsed.columnVisibility
          : {},
      columnOrder: Array.isArray(parsed.columnOrder) ? parsed.columnOrder : [],
      pageSize: typeof parsed.pageSize === "number" ? parsed.pageSize : 50,
      // Default keyset for large tables; preserve explicit offset choices
      pagination: parsed.pagination === "offset" ? "offset" : "keyset",
    };
  } catch {
    return null;
  }
}

export function saveView(resource: string, view: SavedView): void {
  try {
    localStorage.setItem(prefix + resource, JSON.stringify(view));
  } catch {
    /* quota / private mode */
  }
}

export function clearSavedView(resource: string): void {
  try {
    localStorage.removeItem(prefix + resource);
  } catch {
    /* ignore */
  }
}
