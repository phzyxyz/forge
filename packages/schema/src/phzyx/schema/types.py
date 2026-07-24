"""Logical column types and dialect physical mappings."""

from __future__ import annotations

import types
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any, Union, get_args, get_origin
from uuid import UUID

from phzyx.schema.errors import SchemaError


class LogicalType(StrEnum):
    """Portable column types used in the Manifest IR."""

    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    BYTES = "bytes"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    UUID = "uuid"
    DECIMAL = "decimal"
    JSON = "json"


class Dialect(StrEnum):
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    MYSQL = "mysql"


# Postgres physical types for each logical type.
POSTGRES_TYPES: dict[LogicalType, str] = {
    LogicalType.STR: "TEXT",
    LogicalType.INT: "BIGINT",
    LogicalType.FLOAT: "DOUBLE PRECISION",
    LogicalType.BOOL: "BOOLEAN",
    LogicalType.BYTES: "BYTEA",
    LogicalType.DATETIME: "TIMESTAMPTZ",
    LogicalType.DATE: "DATE",
    LogicalType.TIME: "TIME",
    LogicalType.UUID: "UUID",
    LogicalType.DECIMAL: "NUMERIC",
    LogicalType.JSON: "JSONB",
}

# SQLite affinity / declared types (documented limits apply).
SQLITE_TYPES: dict[LogicalType, str] = {
    LogicalType.STR: "TEXT",
    LogicalType.INT: "INTEGER",
    LogicalType.FLOAT: "REAL",
    LogicalType.BOOL: "INTEGER",  # 0/1
    LogicalType.BYTES: "BLOB",
    LogicalType.DATETIME: "TEXT",  # ISO-8601
    LogicalType.DATE: "TEXT",
    LogicalType.TIME: "TEXT",
    LogicalType.UUID: "TEXT",
    LogicalType.DECIMAL: "TEXT",
    LogicalType.JSON: "TEXT",
}

# MySQL / MariaDB physical types (baseline; MariaDB DSN aliases to mysql for now).
MYSQL_TYPES: dict[LogicalType, str] = {
    LogicalType.STR: "TEXT",
    LogicalType.INT: "BIGINT",
    LogicalType.FLOAT: "DOUBLE",
    LogicalType.BOOL: "TINYINT(1)",
    LogicalType.BYTES: "BLOB",
    LogicalType.DATETIME: "DATETIME(6)",
    LogicalType.DATE: "DATE",
    LogicalType.TIME: "TIME(6)",
    LogicalType.UUID: "CHAR(36)",
    LogicalType.DECIMAL: "DECIMAL(38, 9)",
    LogicalType.JSON: "JSON",
}

SQLITE_LIMITS = (
    "SQLite has no native BOOLEAN/UUID/JSONB/DECIMAL; Phzyx stores BOOL as INTEGER, "
    "UUID/DECIMAL/JSON/datetime families as TEXT (ISO for dates), and BYTES as BLOB."
)

MYSQL_LIMITS = (
    "MySQL has no native UUID type; Phzyx stores UUID as CHAR(36). "
    "BOOL is TINYINT(1). JSON is native (5.7+/8.0+). MariaDB DSNs map to Dialect.MYSQL for now."
)


def infer_logical_type(annotation: Any) -> LogicalType:
    """Map a Python typing annotation to a :class:`LogicalType`."""
    ann = _unwrap_optional(annotation)
    origin = get_origin(ann)

    if ann is str or ann is Any:
        return LogicalType.STR if ann is str else LogicalType.JSON
    if ann is int:
        return LogicalType.INT
    if ann is float:
        return LogicalType.FLOAT
    if ann is bool:
        return LogicalType.BOOL
    if ann is bytes:
        return LogicalType.BYTES
    if ann is datetime:
        return LogicalType.DATETIME
    if ann is date:
        return LogicalType.DATE
    if ann is time:
        return LogicalType.TIME
    if ann is UUID:
        return LogicalType.UUID
    if ann is Decimal:
        return LogicalType.DECIMAL
    if ann is dict or origin is dict:
        return LogicalType.JSON
    if ann is list or origin is list:
        return LogicalType.JSON

    # ForwardRef / string annotations often remain strings on models.
    if isinstance(ann, str):
        return _from_name(ann)

    name = getattr(ann, "__name__", None) or str(ann)
    return _from_name(name)


def physical_type(
    logical: LogicalType,
    dialect: Dialect | str,
    *,
    db_type: str | None = None,
) -> str:
    """Resolve physical SQL type; ``db_type`` overrides the dialect map."""
    if db_type:
        return db_type
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if d is Dialect.POSTGRES:
        return POSTGRES_TYPES[logical]
    if d is Dialect.SQLITE:
        return SQLITE_TYPES[logical]
    if d is Dialect.MYSQL:
        return MYSQL_TYPES[logical]
    raise SchemaError(f"unknown dialect: {dialect!r}")


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _from_name(name: str) -> LogicalType:
    key = name.rsplit(".", 1)[-1].lower()
    mapping = {
        "str": LogicalType.STR,
        "string": LogicalType.STR,
        "int": LogicalType.INT,
        "float": LogicalType.FLOAT,
        "bool": LogicalType.BOOL,
        "bytes": LogicalType.BYTES,
        "datetime": LogicalType.DATETIME,
        "date": LogicalType.DATE,
        "time": LogicalType.TIME,
        "uuid": LogicalType.UUID,
        "decimal": LogicalType.DECIMAL,
        "dict": LogicalType.JSON,
        "list": LogicalType.JSON,
        "any": LogicalType.JSON,
    }
    if key in mapping:
        return mapping[key]
    raise SchemaError(
        f"unsupported field annotation {name!r}; use a supported scalar or set "
        f"Field(db_type=...) with an explicit physical type after using a mapped type"
    )
