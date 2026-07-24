export function coerceBody(draft: Record<string, string>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [k, raw] of Object.entries(draft)) {
    const v = raw.trim();
    if (v === "") continue;
    if (v === "true" || v === "True") body[k] = true;
    else if (v === "false" || v === "False") body[k] = false;
    else if (/^-?\d+$/.test(v)) body[k] = Number(v);
    else if (/^-?\d+\.\d+$/.test(v)) body[k] = Number(v);
    else body[k] = v;
  }
  return body;
}

export function rowToDraft(row: Record<string, unknown>): Record<string, string> {
  const d: Record<string, string> = {};
  for (const [k, v] of Object.entries(row)) {
    if (k === "_identity") continue;
    if (typeof v === "boolean") d[k] = v ? "true" : "false";
    else d[k] = v == null ? "" : String(v);
  }
  return d;
}

export function cellDisplay(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

export function downloadText(filename: string, text: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function downloadBlob(filename: string, blob: Blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function relativeTime(ts: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function isBoolField(name: string, value: unknown): boolean {
  return (
    name === "active" ||
    typeof value === "boolean" ||
    value === "true" ||
    value === "false"
  );
}
