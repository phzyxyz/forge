import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Environment } from "./types";
import { isEnvValueEditable, normalizeEnvVariable } from "./types";
import {
  formatEnvVarDisplay,
  lookupEnvVar,
  parseEnvTokens,
  type EnvVarLookup,
} from "./interpolate";

type Props = {
  value: string;
  onChange: (next: string) => void;
  env: Environment | null | undefined;
  className?: string;
  "data-testid"?: string;
  placeholder?: string;
  /** Open Env tab and focus this variable (chip click / tip action). */
  onOpenEnv?: (varName: string) => void;
};

function statusClass(status: EnvVarLookup["status"]): string {
  if (status === "ok") return "is-ok";
  if (status === "empty") return "is-empty";
  if (status === "disabled") return "is-disabled";
  return "is-missing";
}

type TipState = {
  name: string;
  raw: string;
  left: number;
  top: number;
  place: "above" | "below";
};

function EnvVarChip({
  name,
  raw,
  env,
  onOpenEnv,
  onShowTip,
  onHideTip,
}: {
  name: string;
  raw: string;
  env: Environment | null | undefined;
  onOpenEnv?: (varName: string) => void;
  onShowTip: (tip: TipState, el: HTMLElement) => void;
  onHideTip: () => void;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const lookup = lookupEnvVar(env, name);

  const show = () => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const place: "above" | "below" = r.top < 96 ? "below" : "above";
    onShowTip(
      {
        name,
        raw,
        left: r.left + r.width / 2,
        top: place === "above" ? r.top : r.bottom,
        place,
      },
      el,
    );
  };

  return (
    <span
      ref={ref}
      className={`ab-env-chip ${statusClass(lookup.status)}`}
      data-env-var={name}
      data-env-status={lookup.status}
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={onHideTip}
      onFocus={show}
      onBlur={onHideTip}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onOpenEnv?.(name);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onOpenEnv?.(name);
        }
      }}
      title=""
    >
      <span className="ab-env-chip-text">{raw}</span>
    </span>
  );
}

function EnvVarTipPortal({
  tip,
  env,
  onOpenEnv,
  onMouseEnter,
  onMouseLeave,
}: {
  tip: TipState;
  env: Environment | null | undefined;
  onOpenEnv?: (varName: string) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const lookup = lookupEnvVar(env, tip.name);
  const display = formatEnvVarDisplay(lookup);
  const found = env?.variables.find((v) => v.key === tip.name);
  const normalized = found ? normalizeEnvVariable(found) : null;
  const valueEditable = found ? isEnvValueEditable(found) : true;
  const isPlatform = normalized?.source === "platform";

  return createPortal(
    <div
      className={`ab-env-tip-portal ab-env-tip-portal--${tip.place}`}
      style={{
        left: tip.left,
        top: tip.top,
      }}
      role="tooltip"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="ab-env-tip-portal-inner">
        <div className="ab-env-tip-row">
          <span className="ab-env-tip-key">{tip.name}</span>
          {isPlatform && <span className="ab-env-tip-badge">platform</span>}
          {!valueEditable && found && (
            <span className="ab-env-tip-badge ab-env-tip-badge-muted">read-only</span>
          )}
        </div>
        <code className="ab-env-tip-val mono">{display}</code>
        {lookup.status === "missing" && (
          <span className="ab-env-tip-hint">Not defined — add it under Env</span>
        )}
        {lookup.status === "disabled" && (
          <span className="ab-env-tip-hint">Disabled — enable under Env</span>
        )}
        {lookup.status === "empty" && valueEditable && (
          <span className="ab-env-tip-hint">Empty — set a value under Env</span>
        )}
        {isPlatform && !valueEditable && (
          <span className="ab-env-tip-hint">Bound to this AdminBoard server</span>
        )}
        <button
          type="button"
          className="btn btn-sm ab-env-tip-action"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onOpenEnv?.(tip.name);
          }}
        >
          {valueEditable || lookup.status === "missing" ? "Open Env to edit" : "Open Env"}
        </button>
      </div>
    </div>,
    document.body,
  );
}

/** Highlighted, editable URL with hover boxes for {{env}} values. */
export function EnvAwareUrlInput({
  value,
  onChange,
  env,
  className = "",
  "data-testid": testId,
  placeholder = "{{baseUrl}}/path",
  onOpenEnv,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [tip, setTip] = useState<TipState | null>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const clearHide = () => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  };

  const scheduleHide = () => {
    clearHide();
    hideTimer.current = setTimeout(() => setTip(null), 120);
  };

  useEffect(() => () => clearHide(), []);

  useEffect(() => {
    if (editing) {
      setTip(null);
      inputRef.current?.focus();
    }
  }, [editing]);

  // Keep tip pinned on scroll/resize
  useLayoutEffect(() => {
    if (!tip) return;
    const onMove = () => setTip(null);
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [tip]);

  const tokens = parseEnvTokens(value);
  const hasVars = tokens.some((t) => t.type === "var");

  const chipHandlers = {
    onOpenEnv,
    onShowTip: (t: TipState) => {
      clearHide();
      setTip(t);
    },
    onHideTip: scheduleHide,
  };

  if (editing || !hasVars) {
    return (
      <input
        ref={inputRef}
        className={`input ab-url-input mono ${className}`.trim()}
        value={value}
        placeholder={placeholder}
        spellCheck={false}
        autoComplete="off"
        data-testid={testId}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setEditing(true)}
        onBlur={() => setEditing(false)}
      />
    );
  }

  return (
    <>
      <div
        className={`ab-url-highlight mono ${className}`.trim()}
        role="textbox"
        tabIndex={0}
        data-testid={testId}
        aria-label="Request URL"
        onClick={(e) => {
          // Chip handles its own click; plain area enters edit
          if ((e.target as HTMLElement).closest(".ab-env-chip")) return;
          setEditing(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " " || e.key.length === 1) {
            if ((e.target as HTMLElement).closest(".ab-env-chip")) return;
            e.preventDefault();
            setEditing(true);
          }
        }}
      >
        {tokens.map((t, i) =>
          t.type === "text" ? (
            <span key={i} className="ab-url-plain">
              {t.value}
            </span>
          ) : (
            <EnvVarChip key={i} name={t.name} raw={t.raw} env={env} {...chipHandlers} />
          ),
        )}
        {!value && <span className="ab-url-placeholder muted">{placeholder}</span>}
      </div>
      {tip && (
        <EnvVarTipPortal
          tip={tip}
          env={env}
          onOpenEnv={onOpenEnv}
          onMouseEnter={clearHide}
          onMouseLeave={scheduleHide}
        />
      )}
    </>
  );
}

/** Read-only highlight of {{vars}} (e.g. path preview under title). */
export function EnvHighlightText({
  text,
  env,
  className = "",
  onOpenEnv,
}: {
  text: string;
  env: Environment | null | undefined;
  className?: string;
  onOpenEnv?: (varName: string) => void;
}) {
  const [tip, setTip] = useState<TipState | null>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHide = () => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  };
  const scheduleHide = () => {
    clearHide();
    hideTimer.current = setTimeout(() => setTip(null), 120);
  };

  useEffect(() => () => clearHide(), []);

  const tokens = parseEnvTokens(text);
  if (!tokens.some((t) => t.type === "var")) {
    return <span className={className}>{text}</span>;
  }
  return (
    <>
      <span className={`ab-env-inline ${className}`.trim()}>
        {tokens.map((t, i) =>
          t.type === "text" ? (
            <span key={i}>{t.value}</span>
          ) : (
            <EnvVarChip
              key={i}
              name={t.name}
              raw={t.raw}
              env={env}
              onOpenEnv={onOpenEnv}
              onShowTip={(tp) => {
                clearHide();
                setTip(tp);
              }}
              onHideTip={scheduleHide}
            />
          ),
        )}
      </span>
      {tip && (
        <EnvVarTipPortal
          tip={tip}
          env={env}
          onOpenEnv={onOpenEnv}
          onMouseEnter={clearHide}
          onMouseLeave={scheduleHide}
        />
      )}
    </>
  );
}
