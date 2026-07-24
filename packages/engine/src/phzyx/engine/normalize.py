"""Normalize live SQL types into Manifest logical types."""

from __future__ import annotations

from phzyx.schema.types import LogicalType


def normalize_sql_type(sql_type: str, *, dialect: str) -> LogicalType:
    """Map a dialect type name (from PRAGMA/information_schema) to LogicalType."""
    t = sql_type.strip().upper()
    # Strip precision: VARCHAR(64), NUMERIC(10,2)
    base = t.split("(", 1)[0].strip()

    # MySQL BOOL/BOOLEAN are TINYINT(1); distinguish when display type carries (1).
    if dialect == "mysql" and base == "TINYINT" and "(1)" in t.replace(" ", ""):
        return LogicalType.BOOL

    if base in {
        "INT",
        "INTEGER",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "MEDIUMINT",
        "SERIAL",
        "BIGSERIAL",
    }:
        return LogicalType.INT
    if base in {"REAL", "FLOAT", "DOUBLE", "DOUBLE PRECISION"}:
        return LogicalType.FLOAT
    if base in {"BOOL", "BOOLEAN"}:
        return LogicalType.BOOL
    if base in {
        "BLOB",
        "BYTEA",
        "BINARY",
        "VARBINARY",
        "TINYBLOB",
        "MEDIUMBLOB",
        "LONGBLOB",
    }:
        return LogicalType.BYTES
    if base in {"UUID"}:
        return LogicalType.UUID
    if base in {"JSONB", "JSON"}:
        return LogicalType.JSON
    if base in {"NUMERIC", "DECIMAL", "DEC", "FIXED"}:
        return LogicalType.DECIMAL
    if base in {"DATE"}:
        return LogicalType.DATE
    if base in {"TIME"}:
        return LogicalType.TIME
    if base in {"TIMESTAMP", "TIMESTAMPTZ", "DATETIME"}:
        return LogicalType.DATETIME
    if base in {
        "TEXT",
        "VARCHAR",
        "CHAR",
        "CHARACTER",
        "NVARCHAR",
        "CLOB",
        "TINYTEXT",
        "MEDIUMTEXT",
        "LONGTEXT",
        "ENUM",
        "SET",
    }:
        # CHAR(36) often stores UUID on MySQL — still LogicalType.STR unless app uses db_type.
        return LogicalType.STR
    # SQLite free-form types often appear as empty or custom.
    if dialect == "sqlite" and not base:
        return LogicalType.STR
    return LogicalType.STR
