/** Global 403 presentation for Diamond D7 Trust. */

export function ForbiddenBanner({
  message,
  action,
  resource,
  onDismiss,
}: {
  message: string;
  action?: string;
  resource?: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="alert error" data-testid="forbidden-banner" role="alert">
      <strong>Access denied</strong>
      <p style={{ margin: "6px 0 0" }}>{message}</p>
      {(action || resource) && (
        <p className="mono muted" style={{ margin: "8px 0 0", fontSize: 12 }}>
          {action ? `action=${action}` : ""}
          {action && resource ? " · " : ""}
          {resource ? `resource=${resource}` : ""}
        </p>
      )}
      {onDismiss && (
        <button
          type="button"
          className="btn btn-sm"
          style={{ marginTop: 10 }}
          onClick={onDismiss}
        >
          Dismiss
        </button>
      )}
    </div>
  );
}
