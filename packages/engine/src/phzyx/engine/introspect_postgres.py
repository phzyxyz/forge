"""Postgres live schema introspection → Manifest IR (psycopg3)."""

from __future__ import annotations

from typing import Any

from phzyx.engine.capabilities import CapabilitySet, Version, capabilities_for, parse_version
from phzyx.engine.errors import ConnectionError
from phzyx.engine.normalize import normalize_sql_type
from phzyx.schema.manifest import (
    MANIFEST_VERSION,
    ColumnDef,
    ConstraintDef,
    IndexDef,
    Manifest,
    TableDef,
)
from phzyx.schema.types import Dialect


class PostgresAdapter:
    dialect = Dialect.POSTGRES

    def detect_version(self, connection: Any) -> Version:
        cur = connection.cursor()
        try:
            cur.execute("SHOW server_version")
            raw = str(cur.fetchone()[0])
            return parse_version(raw, dialect=Dialect.POSTGRES)
        finally:
            cur.close()

    def capabilities(self, version: Version) -> CapabilitySet:
        return capabilities_for(Dialect.POSTGRES, version)

    def introspect(self, connection: Any) -> Manifest:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_name NOT LIKE '\\_phzyx\\_%' ESCAPE '\\'
                ORDER BY table_schema, table_name
                """
            )
            tables = []
            for schema, name in cur.fetchall():
                tables.append(self._table(connection, schema, name))
            return Manifest(
                tables=tuple(tables),
                manifest_version=MANIFEST_VERSION,
                meta={"source": "postgres_introspect"},
            )
        finally:
            cur.close()

    def _table(self, connection: Any, schema: str, name: str) -> TableDef:
        cur = connection.cursor()
        try:
            cur.execute(
                """
                SELECT column_name, data_type, udt_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, name),
            )
            col_rows = cur.fetchall()
            cur.execute(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                JOIN pg_class c ON c.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE i.indisprimary AND n.nspname = %s AND c.relname = %s
                ORDER BY array_position(i.indkey, a.attnum)
                """,
                (schema, name),
            )
            pk = tuple(r[0] for r in cur.fetchall())
            columns: list[ColumnDef] = []
            for col_name, data_type, udt_name, is_nullable, default in col_rows:
                type_name = udt_name or data_type or "text"
                logical = normalize_sql_type(type_name, dialect="postgres")
                columns.append(
                    ColumnDef(
                        name=col_name,
                        logical_type=logical,
                        nullable=is_nullable == "YES" and col_name not in pk,
                        primary_key=col_name in pk,
                        server_default=default,
                    )
                )
            # indexes (non-primary)
            cur.execute(
                """
                SELECT i.relname AS index_name, ix.indisunique, array_agg(a.attname ORDER BY k.n)
                FROM pg_class t
                JOIN pg_namespace ns ON ns.oid = t.relnamespace
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON true
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
                WHERE ns.nspname = %s AND t.relname = %s AND NOT ix.indisprimary
                GROUP BY i.relname, ix.indisunique
                """,
                (schema, name),
            )
            indexes = [
                IndexDef(name=r[0], columns=tuple(r[2]), unique=bool(r[1])) for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT
                  tc.constraint_name,
                  kcu.column_name,
                  ccu.table_name AS foreign_table,
                  ccu.column_name AS foreign_column,
                  rc.delete_rule
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                JOIN information_schema.referential_constraints AS rc
                  ON rc.constraint_name = tc.constraint_name
                 AND rc.constraint_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s AND tc.table_name = %s
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """,
                (schema, name),
            )
            fk_rows = cur.fetchall()
            grouped: dict[str, list[Any]] = {}
            for row in fk_rows:
                grouped.setdefault(row[0], []).append(row)
            constraints: list[ConstraintDef] = []
            for cname, rows in grouped.items():
                constraints.append(
                    ConstraintDef(
                        name=cname,
                        kind="foreign_key",
                        columns=tuple(r[1] for r in rows),
                        ref_table=rows[0][2],
                        ref_columns=tuple(r[3] for r in rows),
                        on_delete=None if rows[0][4] == "NO ACTION" else rows[0][4],
                    )
                )
            return TableDef(
                name=name,
                schema_name=None if schema == "public" else schema,
                columns=tuple(columns),
                primary_key=pk,
                indexes=tuple(indexes),
                constraints=tuple(constraints),
            )
        finally:
            cur.close()


def require_psycopg() -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise ConnectionError(
            "PostgreSQL support requires psycopg: uv add 'psycopg[binary]'"
        ) from exc
    return psycopg
