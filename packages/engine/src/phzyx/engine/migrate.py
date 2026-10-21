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
from phzyx.engine.ops import SchemaOp
from phzyx.engine.plan import SchemaPlan
from phzyx.engine.sql_split import split_statements
from phzyx.schema.ddl import quote_ident
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

_CREATE_HISTORY_MYSQL = f"""
CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  version VARCHAR(255) NOT NULL,
  checksum VARCHAR(64) NOT NULL,
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_phzyx_mig_version (version)
)
"""

_CREATE_HISTORY_MSSQL = f"""
IF OBJECT_ID(N'dbo.{HISTORY_TABLE}', N'U') IS NULL
CREATE TABLE dbo.[{HISTORY_TABLE}] (
  id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  version NVARCHAR(255) NOT NULL,
  checksum NVARCHAR(64) NOT NULL,
  applied_at DATETIME2 NOT NULL CONSTRAINT DF_phzyx_mig_applied DEFAULT (SYSUTCDATETIME()),
  CONSTRAINT uq_phzyx_mig_version UNIQUE (version)
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
    if d is Dialect.SQLITE:
        sql = _CREATE_HISTORY_SQLITE
    elif d is Dialect.MYSQL:
        sql = _CREATE_HISTORY_MYSQL
    elif d is Dialect.MSSQL:
        sql = _CREATE_HISTORY_MSSQL
    else:
        sql = _CREATE_HISTORY_PG
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


def render_downgrade_sql(plan: SchemaPlan, *, dialect: Dialect | str = Dialect.SQLITE) -> str:
    """Reverse of a Forge-generated plan, as SQL.

    Creating a table, adding a column, adding an index, or renaming a
    column has a mechanical reverse. Those statements are real DDL, in
    the opposite order from the upgrade.

    A forward drop of a table, column, or index throws the definition
    away. This file cannot put that data back. Those operations are
    listed as comments, not as pretend ``UNDO`` statements.
    """
    resolved = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    statements: list[str] = []
    not_reversible: list[str] = []
    for operation in reversed(plan.ops):
        statement, reason = _reverse_operation(operation, dialect=resolved)
        if statement is not None:
            statements.append(statement)
        if reason is not None:
            not_reversible.append(reason)

    lines = [
        "-- Phzyx migration downgrade",
        "-- Reverses create, add, and rename operations from the forward plan.",
        "-- A dropped table, column, or index is not recovered here.",
        "",
    ]
    for reason in not_reversible:
        lines.append(f"-- not reversible: {reason}")
    if not_reversible:
        lines.append("")
    if not statements and not not_reversible:
        lines.append("-- empty plan")
        lines.append("")
    for statement in statements:
        lines.append(statement + ";")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_downgrade_stub(plan: SchemaPlan, *, dialect: Dialect | str = Dialect.SQLITE) -> str:
    """Old name for :func:`render_downgrade_sql`.

    Callers that still say "stub" get the reverse SQL, not a comment file.
    """
    return render_downgrade_sql(plan, dialect=dialect)


def _reverse_operation(operation: SchemaOp, *, dialect: Dialect) -> tuple[str | None, str | None]:
    """Return ``(sql, why_not)``. One of the two is None."""
    table_name = quote_ident(operation.table, dialect)
    if operation.kind == "create_table":
        return f"DROP TABLE {table_name}", None
    if operation.kind == "add_column" and operation.column is not None:
        column_name = quote_ident(operation.column.name, dialect)
        return f"ALTER TABLE {table_name} DROP COLUMN {column_name}", None
    if operation.kind == "add_index" and operation.index is not None:
        index_name = quote_ident(operation.index.name, dialect)
        if dialect is Dialect.MSSQL:
            return f"DROP INDEX {index_name} ON {table_name}", None
        return f"DROP INDEX {index_name}", None
    if operation.kind == "rename_column" and operation.column_name and operation.new_column_name:
        current_name = quote_ident(operation.new_column_name, dialect)
        original_name = quote_ident(operation.column_name, dialect)
        if dialect is Dialect.MSSQL:
            # sp_rename wants the raw name inside a string. quote_ident
            # still rejects a table name that is not a plain identifier.
            quote_ident(operation.table, dialect)
            return (
                f"EXEC sp_rename '{operation.table}.{operation.new_column_name}', "
                f"'{operation.column_name}', 'COLUMN'",
                None,
            )
        return f"ALTER TABLE {table_name} RENAME COLUMN {current_name} TO {original_name}", None
    if operation.kind in {"drop_table", "drop_column", "drop_index", "archive_column"}:
        return None, operation.describe()
    if operation.kind == "add_foreign_key":
        return None, operation.describe() + " (the forward plan does not record the constraint name)"
    return None, operation.describe()


def create_migration(
    plan: SchemaPlan,
    migrations_dir: str | Path,
    *,
    dialect: Dialect | str,
    name: str = "auto",
) -> MigrationFile:
    """Write timestamped upgrade.sql and downgrade.sql under migrations_dir."""
    root = Path(migrations_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "auto"
    version = f"{stamp}_{safe}"
    folder = root / version
    folder.mkdir(parents=True, exist_ok=False)
    upgrade = render_upgrade_sql(plan, dialect=dialect)
    (folder / "upgrade.sql").write_text(upgrade, encoding="utf-8")
    (folder / "downgrade.sql").write_text(
        render_downgrade_sql(plan, dialect=dialect),
        encoding="utf-8",
    )
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


def applied_versions(
    connection: Any,
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> list[str]:
    ensure_history_table(connection, dialect=dialect)
    try:
        cur = connection.execute(f"SELECT version FROM {HISTORY_TABLE} ORDER BY version")
        return [r[0] for r in cur.fetchall()]
    except Exception:
        # postgres / mysql cursor style
        cur = connection.cursor()
        try:
            cur.execute(f"SELECT version FROM {HISTORY_TABLE} ORDER BY version")
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()


def migrate_status(
    connection: Any,
    migrations_dir: str | Path,
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> MigrateStatus:
    files = list_migration_files(migrations_dir)
    applied = set(applied_versions(connection, dialect=dialect))
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
    # SQLite/Postgres accept ISO text; MySQL/MSSQL reject "+00:00" tz suffixes.
    if dialect in {Dialect.MYSQL, Dialect.MSSQL}:
        now = datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    else:
        now = datetime.now(UTC).isoformat()
    if dialect is Dialect.SQLITE:
        connection.execute(
            f"INSERT INTO {HISTORY_TABLE} (version, checksum, applied_at) VALUES (?, ?, ?)",
            (mig.version, mig.checksum, now),
        )
    else:
        cur = connection.cursor()
        try:
            table = f"[{HISTORY_TABLE}]" if dialect is Dialect.MSSQL else HISTORY_TABLE
            cur.execute(
                f"INSERT INTO {table} (version, checksum, applied_at) VALUES (%s, %s, %s)",
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
    """Run one migration file statement by statement.

    Semicolons inside strings, quoted identifiers, comments, and
    dollar-quoted function bodies do not end a statement.
    """
    for stmt in split_statements(sql):
        if not stmt.strip():
            continue
        if dialect is Dialect.SQLITE:
            connection.execute(stmt)
        else:
            cur = connection.cursor()
            try:
                cur.execute(stmt)
            finally:
                cur.close()
