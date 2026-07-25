"""Microsoft SQL Server live schema introspection → Manifest IR (pymssql)."""

from __future__ import annotations

from typing import Any

from phzyx.engine.capabilities import CapabilitySet, Version, capabilities_for, parse_version
from phzyx.engine.errors import ConnectionError
from phzyx.engine.normalize import normalize_sql_type
from phzyx.schema.manifest import (
    MANIFEST_VERSION,
    ColumnDef,
    IndexDef,
    Manifest,
    TableDef,
)
from phzyx.schema.types import Dialect


class MssqlAdapter:
    """Dialect adapter for SQL Server: version, capabilities, tables/columns/PK/indexes."""

    dialect = Dialect.MSSQL

    def detect_version(self, connection: Any) -> Version:
        cur = connection.cursor()
        try:
            cur.execute("SELECT @@VERSION")
            raw = str(cur.fetchone()[0])
            return parse_version(raw, dialect=Dialect.MSSQL)
        finally:
            cur.close()

    def capabilities(self, version: Version) -> CapabilitySet:
        return capabilities_for(Dialect.MSSQL, version)

    def introspect(self, connection: Any) -> Manifest:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                  AND TABLE_CATALOG = DB_NAME()
                  AND TABLE_SCHEMA = 'dbo'
                ORDER BY TABLE_NAME
                """
            )
            tables = []
            for schema, name in cur.fetchall():
                if str(name).startswith("_phzyx_"):
                    continue
                tables.append(self._table(connection, schema, name))
            return Manifest(
                tables=tuple(tables),
                manifest_version=MANIFEST_VERSION,
                meta={"source": "mssql_introspect"},
            )
        finally:
            cur.close()

    def _table(self, connection: Any, schema: str, name: str) -> TableDef:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_CATALOG = DB_NAME()
                  AND TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (schema, name),
            )
            col_rows = cur.fetchall()
            cur.execute(
                """
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
                  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                 AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                 AND tc.TABLE_NAME = kcu.TABLE_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                  AND tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s
                ORDER BY kcu.ORDINAL_POSITION
                """,
                (schema, name),
            )
            pk = tuple(r[0] for r in cur.fetchall())

            # Non-primary indexes via sys.indexes (unique + non-unique).
            cur.execute(
                """
                SELECT i.name AS index_name, c.name AS column_name, i.is_unique, ic.key_ordinal
                FROM sys.indexes i
                JOIN sys.index_columns ic
                  ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                JOIN sys.columns c
                  ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                JOIN sys.tables t ON i.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE s.name = %s AND t.name = %s
                  AND i.is_primary_key = 0
                  AND i.name IS NOT NULL
                  AND ic.is_included_column = 0
                ORDER BY i.name, ic.key_ordinal
                """,
                (schema, name),
            )
            idx_map: dict[str, list[Any]] = {}
            for index_name, column_name, is_unique, _ord in cur.fetchall():
                bucket = idx_map.setdefault(index_name, [[], bool(is_unique)])
                bucket[0].append(column_name)
            indexes = tuple(
                IndexDef(
                    name=idx_name,
                    columns=tuple(cols),
                    unique=is_unique,
                )
                for idx_name, (cols, is_unique) in idx_map.items()
            )
            unique_cols = {
                col
                for idx in indexes
                if idx.unique and len(idx.columns) == 1
                for col in idx.columns
            }
            columns: list[ColumnDef] = []
            for col_name, data_type, is_nullable, default in col_rows:
                logical = normalize_sql_type(str(data_type or "nvarchar"), dialect="mssql")
                columns.append(
                    ColumnDef(
                        name=col_name,
                        logical_type=logical,
                        nullable=is_nullable == "YES" and col_name not in pk,
                        primary_key=col_name in pk,
                        unique=col_name in unique_cols,
                        server_default=str(default) if default is not None else None,
                    )
                )
            return TableDef(
                name=name,
                schema_name=None,
                columns=tuple(columns),
                primary_key=pk,
                indexes=indexes,
                constraints=(),
            )
        finally:
            cur.close()


def require_pymssql() -> Any:
    """Import pymssql or raise a helpful ConnectionError."""
    try:
        import pymssql  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ConnectionError(
            "pymssql is required for Microsoft SQL Server: uv add pymssql "
            "(or uv add 'phzyx-engine[mssql]')"
        ) from exc
    return pymssql
