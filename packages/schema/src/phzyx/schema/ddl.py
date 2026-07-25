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
    if d is Dialect.MSSQL:
        return f"[{name}]"
    # Postgres and SQLite use double quotes.
    return f'"{name}"'


def render_create_table(table: TableDef, dialect: Dialect | str) -> str:
    """Render CREATE TABLE including composite PRIMARY KEY and int identity."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    # Columns that appear in UNIQUE constraints need key-safe MySQL types too.
    unique_cols: set[str] = set()
    for c in table.constraints:
        if c.kind == "unique" and c.columns:
            unique_cols.update(c.columns)
    for idx in table.indexes:
        if idx.unique:
            unique_cols.update(idx.columns)

    col_sql: list[str] = []
    for col in table.columns:
        single_ai_pk = (
            col.primary_key
            and col.autoincrement
            and len(table.primary_key) == 1
            and col.db_type is None
        )
        qname = quote_ident(col.name, d)
        if single_ai_pk:
            col_sql.append(_render_autoincrement_pk(qname, d))
            continue

        # Postgres named ENUM type (created via render_enum_ddl)
        if col.pg_enum_name and col.enum_values and d is Dialect.POSTGRES:
            phys = quote_ident(col.pg_enum_name, d)
        else:
            phys = physical_type(
                col.logical_type,
                d,
                db_type=col.db_type,
                max_length=col.max_length,
            )
            # MySQL/MariaDB refuse UNIQUE / KEY on unbounded TEXT/BLOB without a
            # prefix length. Indexed string columns fall back to VARCHAR(255).
            if d is Dialect.MYSQL and _mysql_needs_varchar_key(
                col, phys, forced=col.name in unique_cols
            ):
                phys = f"VARCHAR({col.max_length or 255})"
            # SQL Server: cannot index NVARCHAR(MAX); use NVARCHAR(255) for keys.
            if d is Dialect.MSSQL and _mssql_needs_nvarchar_key(
                col, phys, forced=col.name in unique_cols
            ):
                phys = f"NVARCHAR({col.max_length or 255})"
        parts = [qname, phys]
        if col.generated:
            # PG/MySQL stored generated; SQLite 3.31+
            parts.append(f"GENERATED ALWAYS AS ({col.generated}) STORED")
        else:
            if not col.nullable:
                parts.append("NOT NULL")
            if col.server_default is not None:
                default = mysql_timestamp_expr(col.server_default, phys, d)
                parts.append(f"DEFAULT {default}")
            if col.on_update and d is Dialect.MYSQL:
                on_upd = mysql_timestamp_expr(col.on_update, phys, d)
                parts.append(f"ON UPDATE {on_upd}")
        # Single-column PK can be inline; composite uses table constraint.
        if col.primary_key and len(table.primary_key) == 1 and not col.autoincrement:
            parts.append("PRIMARY KEY")
        col_sql.append(" ".join(parts))

    if len(table.primary_key) > 1:
        pk_cols = ", ".join(quote_ident(c, d) for c in table.primary_key)
        col_sql.append(f"PRIMARY KEY ({pk_cols})")

    # Skip CHECK-on-enum when Postgres native ENUM type is used for that column.
    pg_enum_cols = {
        col.name
        for col in table.columns
        if col.pg_enum_name and col.enum_values and d is Dialect.POSTGRES
    }
    for c in table.constraints:
        if c.kind == "foreign_key":
            col_sql.append(_render_fk_clause(c, d))
        elif c.kind == "check" and c.expression:
            if c.columns and c.columns[0] in pg_enum_cols and "_enum" in c.name:
                continue
            col_sql.append(f"CONSTRAINT {quote_ident(c.name, d)} CHECK ({c.expression})")
        elif c.kind == "unique" and c.columns:
            cols = ", ".join(quote_ident(x, d) for x in c.columns)
            col_sql.append(f"CONSTRAINT {quote_ident(c.name, d)} UNIQUE ({cols})")

    cols_block = ",\n  ".join(col_sql)
    table_name = _qualified_table(table, d)
    return f"CREATE TABLE {table_name} (\n  {cols_block}\n)"


def _render_autoincrement_pk(quoted_name: str, dialect: Dialect) -> str:
    """Dialect-native single integer identity primary key column."""
    if dialect is Dialect.SQLITE:
        # INTEGER PRIMARY KEY is a rowid alias; omit NOT NULL (implied).
        return f"{quoted_name} INTEGER PRIMARY KEY"
    if dialect is Dialect.POSTGRES:
        return f"{quoted_name} BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
    if dialect is Dialect.MYSQL:
        return f"{quoted_name} BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY"
    if dialect is Dialect.MSSQL:
        # IDENTITY is always "always" for inserts unless SET IDENTITY_INSERT ON.
        return f"{quoted_name} BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY"
    raise SchemaError(f"unsupported dialect for autoincrement PK: {dialect}")


def _mssql_needs_nvarchar_key(col: Any, physical: str, *, forced: bool = False) -> bool:
    """True when SQL Server would refuse an index on NVARCHAR(MAX)/VARBINARY(MAX)."""
    upper = physical.upper().replace(" ", "")
    if "MAX" not in upper:
        return False
    return bool(forced or col.unique or col.index or col.primary_key)


def _mysql_needs_varchar_key(col: Any, physical: str, *, forced: bool = False) -> bool:
    """True when MySQL would reject an index on this physical type."""
    upper = physical.upper()
    if not upper.startswith("TEXT") and not upper.startswith("BLOB"):
        return False
    return bool(forced or col.unique or col.index or col.primary_key)


def mysql_timestamp_expr(expr: str, physical_type: str, dialect: Dialect | str) -> str:
    """MySQL requires CURRENT_TIMESTAMP(6) when the column is DATETIME(6)/TIME(6).

    Bare ``CURRENT_TIMESTAMP`` with a fractional-seconds type raises
    ``ERROR 1067 Invalid default value``.
    """
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if d is not Dialect.MYSQL:
        return expr
    upper = expr.strip().upper()
    if upper != "CURRENT_TIMESTAMP":
        return expr
    # Match DATETIME(6), TIMESTAMP(6), TIME(6)
    if "(6)" in physical_type.upper():
        return "CURRENT_TIMESTAMP(6)"
    return expr


def render_create_index(table: TableDef, index: IndexDef, dialect: Dialect | str) -> str:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    unique = "UNIQUE " if index.unique else ""
    if index.expressions:
        cols = ", ".join(index.expressions)
    else:
        cols = ", ".join(quote_ident(c, d) for c in index.columns)
    table_name = _qualified_table(table, d)
    using = ""
    if index.using and d is Dialect.POSTGRES:
        using = f" USING {index.using}"
    sql = f"CREATE {unique}INDEX {quote_ident(index.name, d)} ON {table_name}{using} ({cols})"
    if index.where and d is not Dialect.MSSQL:
        # Filtered indexes exist on MSSQL but use different WHERE syntax; skip for v1.
        sql += f" WHERE {index.where}"
    return sql


def render_enum_ddl(manifest: Manifest, dialect: Dialect | str) -> list[str]:
    """Postgres CREATE TYPE … AS ENUM for columns with enum_values."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if d is not Dialect.POSTGRES:
        return []
    stmts: list[str] = []
    seen: set[str] = set()
    for table in manifest.tables:
        for col in table.columns:
            if not col.pg_enum_name or not col.enum_values:
                continue
            if col.pg_enum_name in seen:
                continue
            seen.add(col.pg_enum_name)
            vals = ", ".join("'" + str(v).replace("'", "''") + "'" for v in col.enum_values)
            stmts.append(f"CREATE TYPE {quote_ident(col.pg_enum_name, d)} AS ENUM ({vals})")
    return stmts


def render_table_ddl(table: TableDef, dialect: Dialect | str) -> list[str]:
    """CREATE TABLE plus secondary indexes for one table."""
    stmts = [render_create_table(table, dialect)]
    for index in table.indexes:
        stmts.append(render_create_index(table, index, dialect))
    return stmts


def render_manifest_ddl(manifest: Manifest, dialect: Dialect | str) -> list[str]:
    """All CREATE statements for a manifest (enums then tables)."""
    stmts: list[str] = []
    stmts.extend(render_enum_ddl(manifest, dialect))
    for table in manifest.tables:
        stmts.extend(render_table_ddl(table, dialect))
    return stmts


def render_identity_migration_sql(
    table: str,
    column: str = "id",
    *,
    dialect: Dialect | str = Dialect.POSTGRES,
) -> list[str]:
    """Best-effort SQL to convert a bare int PK to identity (greenfield ops).

    For existing data on Postgres: attach a sequence as identity.
    SQLite cannot ALTER to identity — recreate table (not automated here).
    MySQL: MODIFY … AUTO_INCREMENT.
    """
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    t = quote_ident(table, d)
    c = quote_ident(column, d)
    if d is Dialect.POSTGRES:
        seq = quote_ident(f"{table}_{column}_seq", d)
        return [
            f"CREATE SEQUENCE IF NOT EXISTS {seq}",
            f"ALTER TABLE {t} ALTER COLUMN {c} SET DEFAULT nextval('{table}_{column}_seq')",
            f"ALTER SEQUENCE {seq} OWNED BY {t}.{c}",
            (f"SELECT setval('{table}_{column}_seq', COALESCE((SELECT MAX({c}) FROM {t}), 1))"),
        ]
    if d is Dialect.MYSQL:
        return [f"ALTER TABLE {t} MODIFY {c} BIGINT NOT NULL AUTO_INCREMENT"]
    if d is Dialect.SQLITE:
        return [
            f"-- SQLite: recreate {table} with INTEGER PRIMARY KEY; "
            f"copy data; rename (manual / migration file)"
        ]
    raise SchemaError(f"unsupported dialect: {d}")


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
