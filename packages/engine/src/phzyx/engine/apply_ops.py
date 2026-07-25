"""Apply SchemaPlan ops as SQL on a live connection."""

from __future__ import annotations

import time
from typing import Any

from phzyx.engine.ops import SchemaOp
from phzyx.engine.plan import SchemaPlan
from phzyx.schema.ddl import quote_ident, render_create_index, render_create_table
from phzyx.schema.manifest import TableDef
from phzyx.schema.types import Dialect, physical_type


def archive_column_name(column: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    return f"_phzyx_archived_{column}_{ts}"


def apply_plan(
    plan: SchemaPlan,
    connection: Any,
    *,
    dialect: Dialect | str,
) -> list[str]:
    """Execute plan ops; return SQL statements that ran."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    statements: list[str] = []
    for op in plan.ops:
        stmts = render_op(op, dialect=d)
        statements.extend(stmts)
        _exec_many(connection, stmts, dialect=d)
    if hasattr(connection, "commit"):
        connection.commit()
    return statements


def render_op(op: SchemaOp, *, dialect: Dialect) -> list[str]:
    """Render one op to SQL (for push apply and migrate create)."""
    t = quote_ident(op.table, dialect)
    if op.kind == "create_table":
        assert op.table_def is not None
        stmts = [render_create_table(op.table_def, dialect)]
        for idx in op.table_def.indexes:
            stmts.append(render_create_index(op.table_def, idx, dialect))
        return stmts
    if op.kind == "add_column":
        assert op.column is not None
        col = op.column
        phys = physical_type(
            col.logical_type, dialect, db_type=col.db_type, max_length=col.max_length
        )
        # SQL Server rejects indexes on NVARCHAR(MAX); match create-table keying.
        if dialect is Dialect.MSSQL and "MAX" in phys.upper() and (col.unique or col.index):
            phys = f"NVARCHAR({col.max_length or 255})"
        null_sql = "" if col.nullable else " NOT NULL"
        default = ""
        if col.server_default:
            from phzyx.schema.ddl import mysql_timestamp_expr

            expr = mysql_timestamp_expr(col.server_default, phys, dialect)
            default = f" DEFAULT {expr}"
        # T-SQL is ``ADD col`` (no COLUMN keyword); others use ADD COLUMN.
        add_kw = "ADD" if dialect is Dialect.MSSQL else "ADD COLUMN"
        return [
            f"ALTER TABLE {t} {add_kw} {quote_ident(col.name, dialect)} {phys}{null_sql}{default}"
        ]
    if op.kind == "rename_column":
        old_name = op.column_name or ""
        new_name = op.new_column_name or ""
        if dialect is Dialect.MSSQL:
            # sp_rename first arg is 'table.column' (no brackets).
            return [f"EXEC sp_rename '{op.table}.{old_name}', '{new_name}', 'COLUMN'"]
        old = quote_ident(old_name, dialect)
        new = quote_ident(new_name, dialect)
        return [f"ALTER TABLE {t} RENAME COLUMN {old} TO {new}"]
    if op.kind == "archive_column":
        old_name = op.column_name or ""
        new_name = archive_column_name(old_name)
        if dialect is Dialect.MSSQL:
            return [f"EXEC sp_rename '{op.table}.{old_name}', '{new_name}', 'COLUMN'"]
        old = quote_ident(old_name, dialect)
        new = quote_ident(new_name, dialect)
        return [f"ALTER TABLE {t} RENAME COLUMN {old} TO {new}"]
    if op.kind == "drop_column":
        col = quote_ident(op.column_name or "", dialect)
        return [f"ALTER TABLE {t} DROP COLUMN {col}"]
    if op.kind == "add_index":
        assert op.index is not None
        # Minimal table def for the index renderer (name + dialect only).
        td = TableDef(name=op.table, columns=(), primary_key=())
        return [render_create_index(td, op.index, dialect)]
    if op.kind == "drop_index":
        assert op.index is not None
        if dialect is Dialect.MSSQL:
            return [f"DROP INDEX {quote_ident(op.index.name, dialect)} ON {t}"]
        return [f"DROP INDEX {quote_ident(op.index.name, dialect)}"]
    if op.kind == "drop_table":
        if dialect is Dialect.MSSQL:
            return [f"DROP TABLE IF EXISTS {t}"]
        return [f"DROP TABLE {t}"]
    return []


def _exec_many(connection: Any, statements: list[str], *, dialect: Dialect) -> None:
    if not statements:
        return
    # sqlite3
    if hasattr(connection, "executescript") and dialect is Dialect.SQLITE:
        for stmt in statements:
            connection.execute(stmt)
        return
    cur = connection.cursor()
    try:
        for stmt in statements:
            cur.execute(stmt)
    finally:
        cur.close()
