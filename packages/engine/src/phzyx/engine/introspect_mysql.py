"""MySQL live schema introspection → Manifest IR (PyMySQL).

MariaDB wire-compatible servers work via the same adapter; DSN schemes
``mariadb://`` currently resolve to :attr:`~phzyx.schema.types.Dialect.MYSQL`.
"""

from __future__ import annotations

from typing import Any

from phzyx.engine.capabilities import CapabilitySet, Version, capabilities_for, parse_version
from phzyx.engine.errors import ConnectionError
from phzyx.engine.normalize import normalize_sql_type
from phzyx.schema.manifest import (
    MANIFEST_VERSION,
    ColumnDef,
    Manifest,
    TableDef,
)
from phzyx.schema.types import Dialect


class MySQLAdapter:
    """Minimal DialectAdapter: version, capabilities, tables/columns/PK."""

    dialect = Dialect.MYSQL

    def detect_version(self, connection: Any) -> Version:
        cur = connection.cursor()
        try:
            cur.execute("SELECT VERSION()")
            raw = str(cur.fetchone()[0])
            return parse_version(raw, dialect=Dialect.MYSQL)
        finally:
            cur.close()

    def capabilities(self, version: Version) -> CapabilitySet:
        return capabilities_for(Dialect.MYSQL, version)

    def introspect(self, connection: Any) -> Manifest:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema = DATABASE()
                ORDER BY table_name
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
                meta={"source": "mysql_introspect"},
            )
        finally:
            cur.close()

    def _table(self, connection: Any, schema: str, name: str) -> TableDef:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT column_name, data_type, column_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, name),
            )
            col_rows = cur.fetchall()
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
                """,
                (schema, name),
            )
            pk = tuple(r[0] for r in cur.fetchall())
            columns: list[ColumnDef] = []
            for col_name, data_type, column_type, is_nullable, default in col_rows:
                # Prefer data_type (e.g. "bigint"); fall back to column_type ("bigint(20)").
                type_name = data_type or column_type or "text"
                logical = normalize_sql_type(type_name, dialect="mysql")
                columns.append(
                    ColumnDef(
                        name=col_name,
                        logical_type=logical,
                        nullable=is_nullable == "YES" and col_name not in pk,
                        primary_key=col_name in pk,
                        server_default=str(default) if default is not None else None,
                    )
                )
            return TableDef(
                name=name,
                schema_name=None,  # current DATABASE(); not multi-schema in v1 baseline
                columns=tuple(columns),
                primary_key=pk,
                indexes=(),
                constraints=(),
            )
        finally:
            cur.close()


def require_pymysql() -> Any:
    """Import PyMySQL or raise a helpful ConnectionError."""
    try:
        import pymysql  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ConnectionError("MySQL support requires PyMySQL: uv add pymysql") from exc
    return pymysql
