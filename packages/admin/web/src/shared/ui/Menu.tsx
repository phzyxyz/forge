import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export type MenuItem =
  | { type: "item"; label: string; onClick: () => void; danger?: boolean; disabled?: boolean }
  | { type: "sep" }
  | { type: "label"; label: string };

const MENU_MIN_WIDTH = 200;
const VIEW_PAD = 8;

export function Menu({
  trigger,
  items,
  align = "right",
  label = "Menu",
}: {
  trigger: ReactNode;
  items: MenuItem[];
  align?: "left" | "right";
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<CSSProperties | null>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  const placeMenu = useCallback(() => {
    const el = anchorRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const menuH = menuRef.current?.offsetHeight ?? 240;
    const menuW = Math.max(menuRef.current?.offsetWidth ?? MENU_MIN_WIDTH, MENU_MIN_WIDTH);
    const spaceBelow = window.innerHeight - r.bottom - VIEW_PAD;
    const openUp = spaceBelow < menuH && r.top > spaceBelow;
    const top = openUp
      ? Math.max(VIEW_PAD, r.top - menuH - 6)
      : Math.min(r.bottom + 6, window.innerHeight - menuH - VIEW_PAD);

    let left: number;
    if (align === "right") {
      left = r.right - menuW;
    } else {
      left = r.left;
    }
    left = Math.min(Math.max(VIEW_PAD, left), window.innerWidth - menuW - VIEW_PAD);

    setCoords({
      position: "fixed",
      top,
      left,
      minWidth: MENU_MIN_WIDTH,
      zIndex: 80,
    });
  }, [align]);

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    placeMenu();
    // Second pass after menu measures itself
    const id = window.requestAnimationFrame(() => placeMenu());
    return () => window.cancelAnimationFrame(id);
  }, [open, placeMenu, items.length]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onReposition = () => placeMenu();
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open, placeMenu]);

  const menu =
    open &&
    createPortal(
      <div
        ref={menuRef}
        id={menuId}
        className="menu menu-portal"
        role="menu"
        aria-label={label}
        data-testid="menu-panel"
        style={coords ?? { position: "fixed", visibility: "hidden", top: 0, left: 0 }}
      >
        {items.map((it, i) => {
          if (it.type === "sep") return <div key={i} className="menu-sep" />;
          if (it.type === "label")
            return (
              <div key={i} className="menu-label">
                {it.label}
              </div>
            );
          return (
            <button
              key={i}
              type="button"
              className={`menu-item${it.danger ? " danger" : ""}`}
              disabled={it.disabled}
              role="menuitem"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                it.onClick();
              }}
            >
              {it.label}
            </button>
          );
        })}
      </div>,
      document.body,
    );

  return (
    <div className="menu-anchor" ref={anchorRef}>
      <span
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.stopPropagation();
            e.preventDefault();
            setOpen((v) => !v);
          }
        }}
      >
        {trigger}
      </span>
      {menu}
    </div>
  );
}
