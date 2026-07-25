import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ResourceSchema } from "../../shared/api/types";
import { apiJson } from "../../shared/api/client";
import { useShellStore } from "../../shared/stores/shell";

export type SearchHit = {
  resource: string;
  identity: string;
  label: string;
  score?: number;
};

type PaletteItem = {
  key: string;
  kind: "nav" | "record";
  label: string;
  sub: string;
  run: () => void;
};

export function CommandPalette({
  resources,
  demo,
  open,
  onClose,
}: {
  resources: ResourceSchema[];
  demo: boolean;
  open: boolean;
  onClose: () => void;
}) {
  const { globalSearch, setGlobalSearch, setRoute, openDrawer } = useShellStore();
  const [q, setQ] = useState(globalSearch);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (open) {
      setQ(globalSearch);
      setActive(0);
    }
  }, [open, globalSearch]);

  const searchQ = useQuery({
    queryKey: ["global-search", q, demo],
    enabled: open && !demo && q.trim().length >= 1,
    queryFn: async () => {
      const data = await apiJson<{ items: SearchHit[] }>(
        `/search?q=${encodeURIComponent(q.trim())}&limit=5`,
      );
      return data.items ?? [];
    },
    staleTime: 2_000,
  });

  const navItems = useMemo((): PaletteItem[] => {
    const base: PaletteItem[] = [
      {
        key: "nav-overview",
        kind: "nav",
        label: "Overview",
        sub: "Dashboard home",
        run: () => setRoute({ page: "overview" }),
      },
      ...resources.map((r) => ({
        key: `nav-${r.name}`,
        kind: "nav" as const,
        label: r.label,
        sub: `Resource · ${r.name}`,
        run: () => setRoute({ page: "resource", name: r.name }),
      })),
      {
        key: "nav-media",
        kind: "nav",
        label: "Media",
        sub: "File keys",
        run: () => setRoute({ page: "media" }),
      },
      {
        key: "nav-schema",
        kind: "nav",
        label: "Schema",
        sub: "Migrations & plan",
        run: () => setRoute({ page: "schema" }),
      },
      {
        key: "nav-audit",
        kind: "nav",
        label: "Audit",
        sub: "Security events",
        run: () => setRoute({ page: "audit" }),
      },
      {
        key: "nav-settings",
        kind: "nav",
        label: "Settings",
        sub: "Theme & density",
        run: () => setRoute({ page: "settings" }),
      },
    ];
    const needle = q.trim().toLowerCase();
    if (!needle) return base;
    return base.filter(
      (i) =>
        i.label.toLowerCase().includes(needle) || i.sub.toLowerCase().includes(needle),
    );
  }, [resources, q, setRoute]);

  const recordItems = useMemo((): PaletteItem[] => {
    if (demo || !searchQ.data?.length) return [];
    return searchQ.data.map((h) => ({
      key: `rec-${h.resource}-${h.identity}`,
      kind: "record" as const,
      label: h.label,
      sub: `${h.resource} · ${h.identity}`,
      run: () => {
        setRoute({ page: "resource", name: h.resource });
        openDrawer("edit", h.resource, h.identity);
      },
    }));
  }, [demo, searchQ.data, setRoute, openDrawer]);

  const items = useMemo(() => {
    // Records first when query has substance; then navigation.
    if (q.trim().length >= 1 && recordItems.length) {
      return [...recordItems, ...navItems];
    }
    return navItems;
  }, [q, recordItems, navItems]);

  useEffect(() => {
    setActive(0);
  }, [q, items.length]);

  if (!open) return null;

  function pick(item: PaletteItem | undefined) {
    if (!item) return;
    item.run();
    setGlobalSearch("");
    onClose();
  }

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div
        className="palette"
        role="dialog"
        aria-label="Command palette"
        data-testid="command-palette"
      >
        <input
          autoFocus
          placeholder="Search records or jump…  ⌘K"
          value={q}
          data-testid="command-palette-input"
          onChange={(e) => {
            setQ(e.target.value);
            setGlobalSearch(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((i) => Math.min(i + 1, Math.max(0, items.length - 1)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              pick(items[active] ?? items[0]);
            } else if (e.key === "Escape") {
              onClose();
            }
          }}
        />
        <div className="palette-list">
          {!demo && q.trim() && searchQ.isFetching && (
            <div className="palette-hint muted">Searching…</div>
          )}
          {!demo && q.trim() && searchQ.isError && (
            <div className="palette-hint muted">
              Search unavailable — navigation only
            </div>
          )}
          {items.length === 0 ? (
            <div className="palette-hint muted" data-testid="command-palette-empty">
              No matches
            </div>
          ) : (
            items.map((i, idx) => (
              <button
                key={i.key}
                type="button"
                className={`palette-item${idx === active ? " active" : ""}`}
                data-testid={`palette-item-${i.kind}`}
                onMouseEnter={() => setActive(idx)}
                onClick={() => pick(i)}
              >
                {i.kind === "record" ? (
                  <span className="palette-badge">Record</span>
                ) : null}
                {i.label}
                <small>{i.sub}</small>
              </button>
            ))
          )}
        </div>
        {demo && (
          <div className="palette-foot muted">
            Demo mode — navigation only (connect live API for record search)
          </div>
        )}
      </div>
    </>
  );
}
