"""Versioned SQL migrations: history table, create, apply, status."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from phzyx.engine.apply_ops import render_op
from phzyx.engine.errors import MigrationError
from phzyx.engine.plan import SchemaPlan
from phzyx.schema.types import Dialect

HISTORY_TABLE = "_phzyx_migrations"

_CREATE_HISTORY_SQLITE = f"""
CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  version TEXT NOT NULL UNIQUE,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
)
"""

_CREATE_HISTORY_PG = f"""
CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
  id SERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  checksum TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


@dataclass(frozen=True, slots=True)
class MigrationFile:
    version: str
    path: Path
    sql: str
    checksum: str


@dataclass
class MigrateStatus:
    applied: list[str]
    pending: list[str]


def ensure_history_table(connection: Any, *, dialect: Dialect | str) -> None:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    sql = _CREATE_HISTORY_SQLITE if d is Dialect.SQLITE else _CREATE_HISTORY_PG
    _exec(connection, sql)
    if hasattr(connection, "commit"):
        connection.commit()


def checksum_sql(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def render_upgrade_sql(plan: SchemaPlan, *, dialect: Dialect | str) -> str:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    parts = [
        "-- Phzyx migration upgrade",
        f"-- generated_at: {datetime.now(UTC).isoformat()}",
        f"-- dialect: {d.value}",
        "",
    ]
    if plan.empty:
        parts.append("-- empty plan")
    for op in plan.ops:
        for stmt in render_op(op, dialect=d):
            parts.append(stmt + ";")
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_downgrade_stub(plan: SchemaPlan) -> str:
    """Best-effort stub only — never claims automatic reverse."""
    lines = [
        "-- Phzyx migration downgrade STUB",
        "-- WARNING: reverse is not automatic. Review and write manually.",
        "-- Forward plan was:",
    ]
    for op in plan.ops:
        lines.append(f"--   {op.describe()}")
    lines.append("")
    lines.append("-- TODO: author reverse DDL if needed")
    lines.append("")
    return "\n".join(lines)


def create_migration(
    plan: SchemaPlan,
    migrations_dir: str | Path,
    *,
    dialect: Dialect | str,
    name: str = "auto",
) -> MigrationFile:
    """Write timestamped upgrade.sql (+ downgrade stub) under migrations_dir."""
    root = Path(migrations_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "auto"
    version = f"{stamp}_{safe}"
    folder = root / version
    folder.mkdir(parents=True, exist_ok=False)
    upgrade = render_upgrade_sql(plan, dialect=dialect)
    (folder / "upgrade.sql").write_text(upgrade, encoding="utf-8")
    (folder / "downgrade.sql").write_text(render_downgrade_stub(plan), encoding="utf-8")
    return MigrationFile(
        version=version,
        path=folder / "upgrade.sql",
        sql=upgrade,
        checksum=checksum_sql(upgrade),
    )


def list_migration_files(migrations_dir: str | Path) -> list[MigrationFile]:
    root = Path(migrations_dir)
    if not root.exists():
        return []
    files: list[MigrationFile] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        up = child / "upgrade.sql"
        if not up.exists():
            continue
        sql = up.read_text(encoding="utf-8")
        files.append(
            MigrationFile(
                version=child.name,
                path=up,
                sql=sql,
                checksum=checksum_sql(sql),
            )
        )
    return files


def applied_versions(connection: Any) -> list[str]:
    ensure_history_table(connection, dialect=Dialect.SQLITE)
    try:
        cur = connection.execute(f"SELECT version FROM {HISTORY_TABLE} ORDER BY version")
        return [r[0] for r in cur.fetchall()]
    except Exception:
        # postgres cursor style
        cur = connection.cursor()
        try:
            cur.execute(f"SELECT version FROM {HISTORY_TABLE} ORDER BY version")
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()


def migrate_status(connection: Any, migrations_dir: str | Path) -> MigrateStatus:
    files = list_migration_files(migrations_dir)
    applied = set(applied_versions(connection))
    pending = [f.version for f in files if f.version not in applied]
    return MigrateStatus(applied=sorted(applied), pending=pending)


def migrate_apply(
    connection: Any,
    migrations_dir: str | Path,
    *,
    dialect: Dialect | str,
) -> list[str]:
    """Apply pending migrations idempotently; verify checksums on re-apply."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    ensure_history_table(connection, dialect=d)
    checksums = _load_checksums(connection)
    applied_now: list[str] = []
    for mig in list_migration_files(migrations_dir):
        if mig.version in checksums:
            if checksums[mig.version] != mig.checksum:
                raise MigrationError(
                    f"checksum mismatch for applied migration {mig.version}: "
                    f"history={checksums[mig.version]} file={mig.checksum}"
                )
            continue
        _exec_script(connection, mig.sql, dialect=d)
        _record(connection, mig, dialect=d)
        applied_now.append(mig.version)
    if hasattr(connection, "commit"):
        connection.commit()
    return applied_now


def _load_checksums(connection: Any) -> dict[str, str]:
    try:
        cur = connection.execute(f"SELECT version, checksum FROM {HISTORY_TABLE}")
        return {r[0]: r[1] for r in cur.fetchall()}
    except Exception:
        cur = connection.cursor()
        try:
            cur.execute(f"SELECT version, checksum FROM {HISTORY_TABLE}")
            return {r[0]: r[1] for r in cur.fetchall()}
        finally:
            cur.close()


def _record(connection: Any, mig: MigrationFile, *, dialect: Dialect) -> None:
    now = datetime.now(UTC).isoformat()
    if dialect is Dialect.SQLITE:
        connection.execute(
            f"INSERT INTO {HISTORY_TABLE} (version, checksum, applied_at) VALUES (?, ?, ?)",
            (mig.version, mig.checksum, now),
        )
    else:
        cur = connection.cursor()
        try:
            cur.execute(
                f"INSERT INTO {HISTORY_TABLE} (version, checksum, applied_at) VALUES (%s, %s, %s)",
                (mig.version, mig.checksum, now),
            )
        finally:
            cur.close()


def _exec(connection: Any, sql: str) -> None:
    if hasattr(connection, "execute"):
        connection.execute(sql)
    else:
        cur = connection.cursor()
        try:
            cur.execute(sql)
        finally:
            cur.close()


def _exec_script(connection: Any, sql: str, *, dialect: Dialect) -> None:
    # re-split carefully: keep multi-line
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            parts.append("\n".join(buf).strip().rstrip(";").strip())
            buf = []
    if buf:
        tail = "\n".join(buf).strip().rstrip(";").strip()
        if tail:
            parts.append(tail)
    for stmt in parts:
        if not stmt:
            continue
        if dialect is Dialect.SQLITE:
            connection.execute(stmt)
        else:
            cur = connection.cursor()
            try:
                cur.execute(stmt)
            finally:
                cur.close()
