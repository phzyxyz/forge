import { useEffect, useState } from "react";
import { downloadFile, openMeta } from "../resources/api";
import { useShellStore } from "../../shared/stores/shell";
import { IconX } from "../../shared/ui/Icons";

export function FilePreview({
  fileKey,
  demo,
  onClose,
}: {
  fileKey: string;
  demo: boolean;
  onClose: () => void;
}) {
  const toast = useShellStore((s) => s.toast);
  const [meta, setMeta] = useState<{
    mode: string;
    content_type: string;
    label: string;
    key: string;
  } | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textBody, setTextBody] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setTextBody(null);
      try {
        const m = await openMeta(demo, fileKey);
        if (cancelled) return;
        setMeta(m);
        if (demo) {
          setLoading(false);
          return;
        }
        const blob = await downloadFile(demo, fileKey);
        if (!blob) throw new Error("Empty file");
        const url = URL.createObjectURL(blob);
        revoked = url;
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        setBlobUrl(url);
        const isText =
          m.mode === "text" ||
          m.content_type?.startsWith("text/") ||
          ["application/json", "application/xml"].includes(m.content_type || "");
        if (isText) {
          setTextBody(await blob.text());
        }
      } catch (e) {
        if (!cancelled) {
          const msg = (e as Error).message || "Could not open file";
          setError(msg);
          toast(msg, "error");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [fileKey, demo, toast]);

  const isImage =
    meta?.mode === "image" ||
    Boolean(meta?.content_type?.startsWith("image/")) ||
    /\.(png|jpe?g|gif|webp|svg)$/i.test(fileKey);
  const isPdf =
    meta?.mode === "pdf" ||
    meta?.content_type === "application/pdf" ||
    /\.pdf$/i.test(fileKey);
  const isText = textBody !== null;

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="File preview"
        data-testid="file-preview"
        style={{ width: "min(720px, calc(100vw - 32px))", maxHeight: "85vh", overflow: "auto" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0 }}>{meta?.label || fileKey.split("/").pop() || "File"}</h3>
            <p className="mono muted" style={{ margin: "6px 0 0", fontSize: 12 }}>
              {fileKey}
            </p>
          </div>
          <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close">
            <IconX />
          </button>
        </div>

        {loading && <p className="muted">Loading…</p>}
        {error && <div className="alert error">{error}</div>}

        {!loading && !error && blobUrl && isImage && (
          <img
            src={blobUrl}
            alt={meta?.label || fileKey}
            data-testid="file-preview-img"
            style={{
              maxWidth: "100%",
              maxHeight: "55vh",
              borderRadius: 12,
              border: "1px solid var(--phzyx-border)",
              display: "block",
              margin: "0 auto",
              background: "var(--phzyx-bg-input)",
            }}
          />
        )}

        {!loading && !error && blobUrl && isPdf && (
          <iframe
            title="PDF preview"
            src={blobUrl}
            data-testid="file-preview-pdf"
            style={{
              width: "100%",
              height: "55vh",
              border: "1px solid var(--phzyx-border)",
              borderRadius: 12,
            }}
          />
        )}

        {!loading && !error && isText && (
          <pre
            className="mono"
            data-testid="file-preview-text"
            style={{
              whiteSpace: "pre-wrap",
              fontSize: 12,
              maxHeight: "55vh",
              overflow: "auto",
              padding: 12,
              borderRadius: 12,
              background: "var(--phzyx-bg-input)",
              border: "1px solid var(--phzyx-border)",
            }}
          >
            {textBody}
          </pre>
        )}

        {!loading && !error && blobUrl && !isImage && !isPdf && !isText && (
          <p className="muted">
            Preview not available for this type ({meta?.content_type || "unknown"}). Use download.
          </p>
        )}

        {!loading && !error && demo && (
          <p className="muted">Demo mode has no binary storage — key metadata only.</p>
        )}

        <div className="modal-actions" style={{ marginTop: 16 }}>
          {blobUrl && (
            <a className="btn" href={blobUrl} download={meta?.label || "file"}>
              Download
            </a>
          )}
          <button type="button" className="btn btn-primary" data-testid="file-preview-close" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </>
  );
}
