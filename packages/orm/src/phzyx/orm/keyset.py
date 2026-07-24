"""Opaque keyset cursors for deep pagination (prefer over OFFSET)."""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from phzyx.orm.expr import OrderBy
from phzyx.schema.ddl import quote_ident
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect


@dataclass(frozen=True, slots=True)
class KeysetPage:
    """One page of keyset results plus next/prev cursors."""

    items: list[Any]
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool


def encode_cursor(values: dict[str, Any]) -> str:
    raw = json.dumps(values, separators=(",", ":"), sort_keys=True, default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + pad)
    data = json.loads(raw.decode())
    if not isinstance(data, dict):
        raise ValueError("cursor must decode to an object")
    return data


def default_order_columns(model: type[Model]) -> tuple[str, ...]:
    """Stable order: primary key columns (supports composite)."""
    return get_table_info(model).primary_key


def build_keyset_where(
    order: Sequence[OrderBy],
    cursor_values: dict[str, Any],
    *,
    dialect: Dialect | str = Dialect.SQLITE,
    after: bool = True,
) -> tuple[str, list[Any]]:
    """Build tuple comparison for keyset: (c1,c2,...) > (v1,v2,...) .

    Uses lexicographic expansion for broad SQL compatibility (SQLite + Postgres).
    """
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    ph = "?" if d is Dialect.SQLITE else "%s"
    cols = [o.column for o in order]
    for c in cols:
        if c not in cursor_values:
            raise ValueError(f"cursor missing order column {c!r}")

    # For mixed ASC/DESC, expand carefully; MVP assumes all ASC or all DESC same direction.
    descending = all(o.descending for o in order)
    if any(o.descending for o in order) and not descending:
        raise ValueError("mixed ASC/DESC keyset not supported in v1")

    parts: list[str] = []
    params: list[Any] = []
    # (a > va) OR (a = va AND b > vb) OR ...
    for i, col in enumerate(cols):
        and_parts: list[str] = []
        for j in range(i):
            and_parts.append(f"{quote_ident(cols[j], d)} = {ph}")
            params.append(cursor_values[cols[j]])
        op = "<" if descending else ">"
        if not after:
            op = ">" if descending else "<"
        and_parts.append(f"{quote_ident(col, d)} {op} {ph}")
        params.append(cursor_values[col])
        parts.append("(" + " AND ".join(and_parts) + ")")
    return "(" + " OR ".join(parts) + ")", params


def order_from_columns(columns: Sequence[str], *, descending: bool = False) -> list[OrderBy]:
    return [OrderBy(c, descending=descending) for c in columns]


def cursor_from_row(row: Any, columns: Sequence[str]) -> str:
    if hasattr(row, "model_dump"):
        data = row.model_dump()
    elif isinstance(row, dict):
        data = row
    else:
        raise TypeError("row must be model or dict")
    return encode_cursor({c: data[c] for c in columns})


def keyset_filters_note() -> str:
    return (
        "Prefer keyset cursors for deep pages. OFFSET scans grow with page depth "
        "and are discouraged for large admin tables."
    )
