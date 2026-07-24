"""SQLite live schema introspection → Manifest IR."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from phzyx.engine.capabilities import CapabilitySet, Version, capabilities_for, parse_version
from phzyx.engine.normalize import normalize_sql_type
from phzyx.schema.manifest import (
    MANIFEST_VERSION,
    ColumnDef,
    ConstraintDef,
    IndexDef,
    Manifest,
    TableDef,
)
from phzyx.schema.types import Dialect, LogicalType

_SYSTEM = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}


class SQLiteAdapter:
    dialect = Dialect.SQLITE

    def detect_version(self, connection: Any) -> Version:
        cur = connection.execute("SELECT sqlite_version()")
        raw = str(cur.fetchone()[0])
        return parse_version(raw, dialect=Dialect.SQLITE)

    def capabilities(self, version: Version) -> CapabilitySet:
        return capabilities_for(Dialect.SQLITE, version)

    def introspect(self, connection: Any) -> Manifest:
        cur = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables: list[TableDef] = []
        for (name,) in cur.fetchall():
            if name in _SYSTEM or name.startswith("_phzyx_"):
                continue
            tables.append(self._table(connection, name))
        return Manifest(
            tables=tuple(tables),
            manifest_version=MANIFEST_VERSION,
            meta={"source": "sqlite_introspect"},
        )

    def _table(self, connection: sqlite3.Connection, name: str) -> TableDef:
        cols_cur = connection.execute(f'PRAGMA table_info("{name}")')
        # cid, name, type, notnull, dflt_value, pk
        rows = cols_cur.fetchall()
        pk_order: list[tuple[int, str]] = []
        columns: list[ColumnDef] = []
        for _cid, col_name, col_type, notnull, dflt, pk in rows:
            logical = normalize_sql_type(col_type or "TEXT", dialect="sqlite")
            if pk:
                pk_order.append((int(pk), col_name))
            columns.append(
                ColumnDef(
                    name=col_name,
                    logical_type=logical,
                    nullable=not bool(notnull) and not bool(pk),
                    primary_key=bool(pk),
                    server_default=str(dflt) if dflt is not None else None,
                )
            )
        pk_order.sort(key=lambda x: x[0])
        primary_key = tuple(c for _, c in pk_order)

        indexes = self._indexes(connection, name)
        constraints = self._foreign_keys(connection, name)
        return TableDef(
            name=name,
            columns=tuple(columns),
            primary_key=primary_key,
            indexes=tuple(indexes),
            constraints=tuple(constraints),
        )

    def _indexes(self, connection: sqlite3.Connection, table: str) -> list[IndexDef]:
        out: list[IndexDef] = []
        cur = connection.execute(f'PRAGMA index_list("{table}")')
        for _seq, idx_name, unique, origin, _partial in cur.fetchall():
            if origin == "pk":
                continue
            # autoindexes for UNIQUE constraints
            cols_cur = connection.execute(f'PRAGMA index_info("{idx_name}")')
            cols = tuple(r[2] for r in cols_cur.fetchall())
            out.append(IndexDef(name=idx_name, columns=cols, unique=bool(unique)))
        return out

    def _foreign_keys(self, connection: sqlite3.Connection, table: str) -> list[ConstraintDef]:
        out: list[ConstraintDef] = []
        cur = connection.execute(f'PRAGMA foreign_key_list("{table}")')
        # id, seq, table, from, to, on_update, on_delete, match
        grouped: dict[int, list[Any]] = {}
        for row in cur.fetchall():
            grouped.setdefault(int(row[0]), []).append(row)
        for fk_id, rows in grouped.items():
            rows.sort(key=lambda r: int(r[1]))
            ref_table = rows[0][2]
            cols = tuple(r[3] for r in rows)
            ref_cols = tuple(r[4] for r in rows)
            on_delete = rows[0][6]
            if on_delete and str(on_delete).upper() == "NO ACTION":
                on_delete = None
            out.append(
                ConstraintDef(
                    name=f"fk_{table}_{fk_id}",
                    kind="foreign_key",
                    columns=cols,
                    ref_table=ref_table,
                    ref_columns=ref_cols,
                    on_delete=str(on_delete).upper().replace("_", " ") if on_delete else None,
                )
            )
        return out


def sqlite_type_affinity(declared: str) -> LogicalType:
    """SQLite type affinity rules (simplified)."""
    u = declared.upper()
    if re.search(r"INT", u):
        return LogicalType.INT
    if re.search(r"CHAR|CLOB|TEXT", u):
        return LogicalType.STR
    if re.search(r"BLOB", u) or not u:
        return LogicalType.BYTES if "BLOB" in u else LogicalType.STR
    if re.search(r"REAL|FLOA|DOUB", u):
        return LogicalType.FLOAT
    return LogicalType.STR
