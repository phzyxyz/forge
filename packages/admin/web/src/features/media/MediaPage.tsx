import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ResourceSchema } from "../../shared/api/types";
import { listMediaLibrary, listRecords, uploadFile } from "../resources/api";
import { useShellStore } from "../../shared/stores/shell";
import { FilePreview } from "./FilePreview";
import { API } from "../../shared/api/client";
import { SESSION_MODE, useSessionStore } from "../auth/sessionStore";

type MediaRow = {
  key: string;
  title: string;
  resource: string;
  mode?: string;
  content_type?: string;
  size?: number | null;
};

export function MediaPage({
  resources,
  demo,
}: {
  resources: ResourceSchema[];
  demo: boolean;
}) {
  const toast = useShellStore((s) => s.toast);
  const qc = useQueryClient();
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [folder, setFolder] = useState("uploads");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const fileResources = resources.filter((r) => r.columns.some((c) => c.file_kind));

  const resourceQueries = useQuery({
    queryKey: ["media-from-resources", demo, fileResources.map((r) => r.name).join(",")],
    queryFn: async () => {
      const out: MediaRow[] = [];
      for (const r of fileResources) {
        const data = await listRecords(demo, r.name, { page_size: 100 });
        const col = r.columns.find((c) => c.file_kind)?.name;
        if (!col) continue;
        for (const row of data.items) {
          const key = String(row[col] ?? "");
          if (!key) continue;
          out.push({
            key,
            title: String(row.title ?? row.name ?? key),
            resource: r.label,
          });
        }
      }
      return out;
    },
  });

  const libraryQ = useQuery({
    queryKey: ["media-library", demo, folder],
    queryFn: () => listMediaLibrary(demo, folder),
    enabled: !demo,
  });

  const items: MediaRow[] = useMemo(() => {
    const fromRes = resourceQueries.data ?? [];
    const fromLib = (libraryQ.data?.items ?? []).map((it) => ({
      key: it.key,
      title: it.label || it.key,
      resource: it.folder || "library",
      mode: it.mode,
      content_type: it.content_type,
      size: it.size,
    }));
    const seen = new Set<string>();
    const merged: MediaRow[] = [];
    for (const it of [...fromLib, ...fromRes]) {
      if (seen.has(it.key)) continue;
      seen.add(it.key);
      merged.push(it);
    }
    return merged;
  }, [resourceQueries.data, libraryQ.data]);

  const thumbUrl = useCallback((key: string, mode?: string, contentType?: string) => {
    const isImg =
      mode === "image" ||
      Boolean(contentType?.startsWith("image/")) ||
      /\.(png|jpe?g|gif|webp|svg)$/i.test(key);
    if (!isImg || demo) return null;
    return `${API}/files/download?key=${encodeURIComponent(key)}`;
  }, [demo]);

  async function doUpload(file: File, keyHint?: string) {
    const key = keyHint || `${folder.replace(/\/$/, "")}/${file.name}`.replace(/^\//, "");
    setProgress(0);
    try {
      // XHR for progress (fetch has no upload progress)
      if (demo) {
        await uploadFile(demo, key, file);
      } else {
        await uploadWithProgress(key, file, setProgress);
      }
      toast(`Uploaded ${file.name}`);
      setProgress(null);
      await qc.invalidateQueries({ queryKey: ["media-library"] });
      await qc.invalidateQueries({ queryKey: ["media-from-resources"] });
    } catch (err) {
      setProgress(null);
      toast((err as Error).message, "error");
    }
  }

  return (
    <div className="page" data-testid="media-page">
      <div className="page-header">
        <div>
          <h1>Media</h1>
          <p className="sub">
            Library keys + FileField values (bytes in storage, keys in DB).
          </p>
        </div>
      </div>

      {!demo && (
        <div
          className="table-panel"
          style={{
            padding: 16,
            display: "grid",
            gap: 12,
            marginBottom: 16,
            border: dragging ? "2px dashed var(--phzyx-cyan-400)" : undefined,
            background: dragging ? "color-mix(in srgb, var(--phzyx-cyan-400) 8%, transparent)" : undefined,
          }}
          data-testid="media-dropzone"
          onDragEnter={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragOver={(e) => e.preventDefault()}
          onDragLeave={() => setDragging(false)}
          onDrop={async (e) => {
            e.preventDefault();
            setDragging(false);
            const files = Array.from(e.dataTransfer.files || []);
            for (const f of files) await doUpload(f);
          }}
        >
          <h3 style={{ margin: 0, fontSize: 14 }}>Upload</h3>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Drag & drop files here, or pick below. Folder prefix:
          </p>
          <label className="field">
            <span>Folder</span>
            <input
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              data-testid="media-folder"
            />
          </label>
          <input
            type="file"
            multiple
            data-testid="upload-input"
            onChange={async (e) => {
              const files = Array.from(e.target.files || []);
              for (const f of files) await doUpload(f);
              e.target.value = "";
            }}
          />
          {progress !== null && (
            <div data-testid="upload-progress" style={{ display: "grid", gap: 6 }}>
              <div
                style={{
                  height: 8,
                  borderRadius: 99,
                  background: "var(--phzyx-bg-input)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${progress}%`,
                    height: "100%",
                    background: "var(--phzyx-cyan-400)",
                    transition: "width 0.15s ease",
                  }}
                />
              </div>
              <span className="muted" style={{ fontSize: 12 }}>
                Uploading… {progress}%
              </span>
            </div>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <div className="empty">
          <h3>No media keys yet</h3>
          <p>Upload files or add FileField values on models.</p>
        </div>
      ) : (
        <div className="card-grid" data-testid="media-grid">
          {items.map((it) => {
            const thumb = thumbUrl(it.key, it.mode, it.content_type);
            return (
              <button
                key={`${it.resource}-${it.key}`}
                type="button"
                className="card"
                data-testid="media-card"
                onClick={() => setPreviewKey(it.key)}
                style={{ textAlign: "left", overflow: "hidden" }}
              >
                {thumb ? (
                  <img
                    src={thumb}
                    alt=""
                    data-testid="media-thumb"
                    style={{
                      width: "100%",
                      height: 120,
                      objectFit: "cover",
                      borderRadius: 10,
                      marginBottom: 10,
                      background: "var(--phzyx-bg-input)",
                    }}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div
                    style={{
                      height: 72,
                      borderRadius: 10,
                      marginBottom: 10,
                      display: "grid",
                      placeItems: "center",
                      background: "var(--phzyx-bg-input)",
                      fontSize: 12,
                      color: "var(--phzyx-muted)",
                    }}
                  >
                    {(it.content_type || it.mode || "file").split("/")[0]}
                  </div>
                )}
                <h3 style={{ margin: 0, fontSize: 14 }}>{it.title}</h3>
                <p className="mono" style={{ fontSize: 11, margin: "6px 0 0" }}>
                  {it.key}
                </p>
                <p style={{ marginTop: 8, fontSize: 12 }}>{it.resource}</p>
              </button>
            );
          })}
        </div>
      )}

      {previewKey && (
        <FilePreview fileKey={previewKey} demo={demo} onClose={() => setPreviewKey(null)} />
      )}
    </div>
  );
}

function uploadWithProgress(
  key: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/files/upload`);
    xhr.withCredentials = true;
    const { authorization, csrfToken } = useSessionStore.getState();
    if (authorization && authorization !== SESSION_MODE) {
      xhr.setRequestHeader("Authorization", authorization);
    }
    if (csrfToken && authorization === SESSION_MODE) {
      xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    }
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) {
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Upload network error"));
    const form = new FormData();
    form.append("key", key);
    form.append("file", file);
    xhr.send(form);
  });
}
