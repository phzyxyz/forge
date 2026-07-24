import type { AppRoute } from "../api/types";

/** Parse location.hash into AppRoute (TanStack-style paths without full router dep complexity). */
export function parseHash(hash: string): AppRoute {
  const raw = hash.replace(/^#\/?/, "").replace(/^\//, "");
  const [path, qs] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "login") return { page: "login" };
  if (parts[0] === "media") return { page: "media" };
  if (parts[0] === "schema") return { page: "schema" };
  if (parts[0] === "audit") return { page: "audit" };
  if (parts[0] === "settings") return { page: "settings" };
  if (parts[0] === "resources" && parts[1]) {
    return { page: "resource", name: decodeURIComponent(parts[1]) };
  }
  if (parts[0] === "overview" || parts.length === 0) return { page: "overview" };
  void qs;
  return { page: "overview" };
}

export function toHash(route: AppRoute): string {
  switch (route.page) {
    case "login":
      return "#/login";
    case "media":
      return "#/media";
    case "schema":
      return "#/schema";
    case "audit":
      return "#/audit";
    case "settings":
      return "#/settings";
    case "resource":
      return `#/resources/${encodeURIComponent(route.name)}`;
    default:
      return "#/";
  }
}

export function parseSearchParam(hash: string, key: string): string {
  const raw = hash.replace(/^#\/?/, "");
  const q = raw.includes("?") ? raw.split("?")[1] : "";
  return new URLSearchParams(q).get(key) ?? "";
}
