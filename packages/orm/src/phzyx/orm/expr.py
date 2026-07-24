"""Query filter expressions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from phzyx.schema.ddl import quote_ident
from phzyx.schema.types import Dialect


@dataclass(frozen=True, slots=True)
class Filter:
    column: str
    op: str
    value: Any = None


@dataclass(frozen=True, slots=True)
class OrderBy:
    column: str
    descending: bool = False


def eq(column: str, value: Any) -> Filter:
    return Filter(column, "eq", value)


def ne(column: str, value: Any) -> Filter:
    return Filter(column, "ne", value)


def lt(column: str, value: Any) -> Filter:
    return Filter(column, "lt", value)


def lte(column: str, value: Any) -> Filter:
    return Filter(column, "lte", value)


def gt(column: str, value: Any) -> Filter:
    return Filter(column, "gt", value)


def gte(column: str, value: Any) -> Filter:
    return Filter(column, "gte", value)


def in_(column: str, values: Sequence[Any]) -> Filter:
    return Filter(column, "in", list(values))


def is_null(column: str) -> Filter:
    return Filter(column, "is_null", None)


def is_not_null(column: str) -> Filter:
    return Filter(column, "is_not_null", None)


def like(column: str, pattern: str) -> Filter:
    return Filter(column, "like", pattern)


def ilike(column: str, pattern: str) -> Filter:
    return Filter(column, "ilike", pattern)


def or_(*filters: Filter) -> Filter:
    """OR-group of filters (nested compile)."""
    return Filter(column="", op="or", value=list(filters))


def asc(column: str) -> OrderBy:
    return OrderBy(column, descending=False)


def desc(column: str) -> OrderBy:
    return OrderBy(column, descending=True)


def compile_filters(
    filters: Sequence[Filter],
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> tuple[str, list[Any]]:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    ph = "?" if d is Dialect.SQLITE else "%s"
    parts: list[str] = []
    params: list[Any] = []
    for f in filters:
        if f.op == "or":
            sub = list(f.value or [])
            if not sub:
                parts.append("1 = 0")
                continue
            sub_sql, sub_params = compile_filters(sub, dialect=d)
            # compile_filters joins with AND; re-compile each child alone
            child_parts: list[str] = []
            child_params: list[Any] = []
            for child in sub:
                cs, cp = compile_filters([child], dialect=d)
                if cs:
                    child_parts.append(f"({cs})" if " AND " in cs else cs)
                    child_params.extend(cp)
            if child_parts:
                parts.append("(" + " OR ".join(child_parts) + ")")
                params.extend(child_params)
            continue
        col = quote_ident(f.column, d)
        if f.op == "eq":
            parts.append(f"{col} = {ph}")
            params.append(f.value)
        elif f.op == "ne":
            parts.append(f"{col} <> {ph}")
            params.append(f.value)
        elif f.op == "lt":
            parts.append(f"{col} < {ph}")
            params.append(f.value)
        elif f.op == "lte":
            parts.append(f"{col} <= {ph}")
            params.append(f.value)
        elif f.op == "gt":
            parts.append(f"{col} > {ph}")
            params.append(f.value)
        elif f.op == "gte":
            parts.append(f"{col} >= {ph}")
            params.append(f.value)
        elif f.op == "in":
            values = list(f.value or [])
            if not values:
                parts.append("1 = 0")
            else:
                placeholders = ", ".join(ph for _ in values)
                parts.append(f"{col} IN ({placeholders})")
                params.extend(values)
        elif f.op == "is_null":
            parts.append(f"{col} IS NULL")
        elif f.op == "is_not_null":
            parts.append(f"{col} IS NOT NULL")
        elif f.op == "like":
            parts.append(f"{col} LIKE {ph}")
            params.append(f.value)
        elif f.op == "ilike":
            if d is Dialect.SQLITE:
                parts.append(f"LOWER({col}) LIKE LOWER({ph})")
            else:
                parts.append(f"{col} ILIKE {ph}")
            params.append(f.value)
        else:
            raise ValueError(f"unknown filter op: {f.op}")
    return " AND ".join(parts), params
