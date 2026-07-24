"""Schema / migration status snapshot for AdminBoard (Diamond D8)."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from phzyx.engine.config import load_config
from phzyx.engine.connection import connect
from phzyx.engine.migrate import migrate_status
from phzyx.engine.plan import build_plan
from phzyx.schema.manifest import build_manifest
from phzyx.schema.model import Model


@dataclass
class SchemaStatusService:
    """Read-only view of dialect, migrations, and optional live/desired diff summary."""

    session_factory: Callable[[], Any] | None = None
    models: list[type[Model]] = field(default_factory=list)
    database_url: str | None = None
    migrations_dir: str | None = None

    def snapshot(self) -> dict[str, Any]:
        url = (
            self.database_url
            or os.environ.get("PHZYX_DATABASE_URL")
            or os.environ.get("PHZYX_DEMO_DB")
        )
        cfg = load_config()
        if not url and cfg.database_url:
            url = cfg.database_url
        # demo uses sqlite path without scheme sometimes
        if url and not str(url).startswith("sqlite") and Path(str(url)).suffix == ".db":
            url = f"sqlite:///{url}"
        if not url:
            return {
                "ok": False,
                "error": "no database URL configured",
                "dialect": None,
                "version": None,
                "migrations": {"applied": [], "pending": []},
                "plan_summary": None,
            }
        if str(url).startswith("/") or ("://" not in str(url) and str(url).endswith(".db")):
            url = f"sqlite:///{url}"
        try:
            conn, adapter = connect(str(url))
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "dialect": None,
                "version": None,
                "migrations": {"applied": [], "pending": []},
                "plan_summary": None,
            }
        try:
            ver = adapter.detect_version(conn)
            mig_dir = self.migrations_dir or cfg.migrations_dir
            try:
                st = migrate_status(conn, mig_dir)
                migrations = {"applied": list(st.applied), "pending": list(st.pending)}
            except Exception:
                migrations = {"applied": [], "pending": [], "note": "no history table yet"}
            plan_summary = None
            if self.models:
                try:
                    desired = build_manifest(self.models)
                    live = adapter.introspect(conn)
                    plan = build_plan(desired, live)
                    plan_summary = plan.summary()
                except Exception as exc:
                    plan_summary = f"plan unavailable: {exc}"
            return {
                "ok": True,
                "error": None,
                "dialect": adapter.dialect.value,
                "version": str(ver),
                "capabilities": sorted(adapter.capabilities(ver).features),
                "migrations": migrations,
                "plan_summary": plan_summary,
                "migrations_dir": mig_dir,
            }
        finally:
            conn.close()
