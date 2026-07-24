"""CREATE TABLE / index / FK SQL emit (create-only) and apply helper."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from typing import Any

from phzyx.schema.errors import SchemaError
from phzyx.schema.manifest import ConstraintDef, IndexDef, Manifest, TableDef
from phzyx.schema.types import Dialect, physical_type

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str, dialect: Dialect | str) -> str:
    """Quote an identifier for the dialect (validates simple names)."""
    if not _IDENT.match(name):
        raise SchemaError(f"unsafe or invalid SQL identifier: {name!r}")
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if d is Dialect.MYSQL:
        return f"`{name}`"
    # Postgres and SQLite use double quotes.
    return f'"{name}"'


def render_create_table(table: TableDef, dialect: Dialect | str) -> str:
    """Render CREATE TABLE including composite PRIMARY KEY."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    col_sql: list[str] = []
    for col in table.columns:
        phys = physical_type(col.logical_type, d, db_type=col.db_type)
        parts = [quote_ident(col.name, d), phys]
        if not col.nullable:
            parts.append("NOT NULL")
        if col.server_default is not None:
            parts.append(f"DEFAULT {col.server_default}")
        # Single-column PK can be inline; composite uses table constraint.
        if col.primary_key and len(table.primary_key) == 1:
            parts.append("PRIMARY KEY")
        col_sql.append(" ".join(parts))

    if len(table.primary_key) > 1:
        pk_cols = ", ".join(quote_ident(c, d) for c in table.primary_key)
        col_sql.append(f"PRIMARY KEY ({pk_cols})")

    for fk in table.constraints:
        if fk.kind == "foreign_key":
            col_sql.append(_render_fk_clause(fk, d))

    cols_block = ",\n  ".join(col_sql)
    table_name = _qualified_table(table, d)
    return f"CREATE TABLE {table_name} (\n  {cols_block}\n)"


def render_create_index(table: TableDef, index: IndexDef, dialect: Dialect | str) -> str:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    unique = "UNIQUE " if index.unique else ""
    cols = ", ".join(quote_ident(c, d) for c in index.columns)
    table_name = _qualified_table(table, d)
    return f"CREATE {unique}INDEX {quote_ident(index.name, d)} ON {table_name} ({cols})"


def render_table_ddl(table: TableDef, dialect: Dialect | str) -> list[str]:
    """CREATE TABLE plus secondary indexes for one table."""
    stmts = [render_create_table(table, dialect)]
    for index in table.indexes:
        stmts.append(render_create_index(table, index, dialect))
    return stmts


def render_manifest_ddl(manifest: Manifest, dialect: Dialect | str) -> list[str]:
    """All CREATE statements for a manifest (tables in name order)."""
    stmts: list[str] = []
    for table in manifest.tables:
        stmts.extend(render_table_ddl(table, dialect))
    return stmts


def apply_sql(
    statements: Sequence[str],
    connection: Any,
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> None:
    """Execute DDL statements on a DB-API connection (thin helper).

    Works with ``sqlite3.Connection``. Postgres drivers that implement
    DB-API ``cursor().execute`` are accepted the same way.
    """
    _ = dialect  # reserved for dialect-specific batching later
    cur = connection.cursor()
    try:
        for stmt in statements:
            cur.execute(stmt)
        if hasattr(connection, "commit"):
            connection.commit()
    finally:
        cur.close()


def apply_manifest_sqlite(manifest: Manifest, path: str = ":memory:") -> sqlite3.Connection:
    """Convenience: create tables from manifest on SQLite and return connection."""
    conn = sqlite3.connect(path)
    apply_sql(render_manifest_ddl(manifest, Dialect.SQLITE), conn, dialect=Dialect.SQLITE)
    return conn


def _render_fk_clause(fk: ConstraintDef, dialect: Dialect) -> str:
    cols = ", ".join(quote_ident(c, dialect) for c in fk.columns)
    ref_cols = ", ".join(quote_ident(c, dialect) for c in fk.ref_columns)
    ref_table = quote_ident(fk.ref_table, dialect)
    clause = (
        f"CONSTRAINT {quote_ident(fk.name, dialect)} "
        f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})"
    )
    if fk.on_delete:
        clause += f" ON DELETE {fk.on_delete}"
    return clause


def _qualified_table(table: TableDef, dialect: Dialect) -> str:
    if table.schema_name:
        if dialect is Dialect.SQLITE:
            # SQLite attaches schemas differently; emit bare name for create-only v1.
            return quote_ident(table.name, dialect)
        return f"{quote_ident(table.schema_name, dialect)}.{quote_ident(table.name, dialect)}"
    return quote_ident(table.name, dialect)


def iter_statements(statements: Iterable[str]) -> list[str]:
    return list(statements)
