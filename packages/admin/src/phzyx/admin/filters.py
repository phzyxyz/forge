"""Admin list/search filter expression builders.

Shared by :class:`~phzyx.admin.service.AdminService` and
:class:`~phzyx.admin.async_service.AsyncAdminService` so both paths use the
same rules without mocks or circular imports.
"""

from __future__ import annotations

from typing import Any

from phzyx.admin.resource import ResourceConfig
from phzyx.orm.expr import (
    eq,
    gt,
    gte,
    ilike,
    in_,
    is_not_null,
    is_null,
    like,
    lt,
    lte,
    ne,
    or_,
)

# Supported ``field__op`` suffixes and ``op:value`` shorthands.
FILTER_OPS = frozenset(
    {
        "eq",
        "ne",
        "lt",
        "lte",
        "gt",
        "gte",
        "like",
        "ilike",
        "contains",
        "startswith",
        "endswith",
        "in",
        "is_null",
        "is_not_null",
    }
)


def parse_filter_key(key: str) -> tuple[str, str]:
    """Split ``field`` or ``field__op`` into ``(field, op)``. Default op is ``eq``."""
    if "__" in key:
        col, op = key.rsplit("__", 1)
        op = op.lower()
        if op in FILTER_OPS:
            return col, op
    return key, "eq"


def coerce_filter_val(raw: str, filter_type: str) -> Any:
    """Coerce a query-string filter value for the column's filter type."""
    if filter_type == "bool":
        return raw.lower() in {"1", "true", "yes", "on"}
    if filter_type == "number":
        try:
            return int(raw) if "." not in raw else float(raw)
        except ValueError:
            return raw
    return raw


def filter_expr(col: str, op: str, raw: str, filter_type: str) -> Any | None:
    """Build one ORM filter expression for a column.

    Supports ``op:value`` shorthand when ``op`` is ``eq``
    (e.g. ``contains:foo``).
    """
    if op == "eq" and ":" in raw:
        maybe_op, rest = raw.split(":", 1)
        if maybe_op.lower() in FILTER_OPS:
            op, raw = maybe_op.lower(), rest
    if op in {"is_null", "isnull"}:
        return is_null(col)
    if op in {"is_not_null", "isnotnull"}:
        return is_not_null(col)
    if op == "in":
        parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
        vals = [coerce_filter_val(p, filter_type) for p in parts]
        return in_(col, vals)
    val = coerce_filter_val(raw, filter_type)
    if op == "eq":
        return eq(col, val)
    if op == "ne":
        return ne(col, val)
    if op == "lt":
        return lt(col, val)
    if op == "lte":
        return lte(col, val)
    if op == "gt":
        return gt(col, val)
    if op == "gte":
        return gte(col, val)
    if op == "like":
        return like(col, str(val))
    if op == "ilike":
        return ilike(col, str(val))
    if op == "contains":
        return ilike(col, f"%{val}%")
    if op == "startswith":
        return ilike(col, f"{val}%")
    if op == "endswith":
        return ilike(col, f"%{val}")
    return eq(col, val)


def build_where(
    res: ResourceConfig,
    *,
    search: str | None = None,
    filters: dict[str, str] | None = None,
    hide_soft_deleted: bool = True,
) -> list[Any]:
    """Build WHERE filters for list/search on a resource.

    Args:
        res: Resource being listed.
        search: Free-text search over ``res.searchable`` columns.
        filters: Query filters (``field`` or ``field__op`` keys).
        hide_soft_deleted: When True and the model has ``deleted_at``,
            exclude soft-deleted rows unless ``include_deleted`` is truthy
            in ``filters``.
    """
    where: list[Any] = []
    if search and res.searchable:
        q = f"%{search}%"
        parts = [ilike(col, q) for col in res.searchable]
        where.append(parts[0] if len(parts) == 1 else or_(*parts))
    if filters:
        allowed = set(res.filterable) | {c.name for c in res.columns if c.filterable}
        for key, raw in filters.items():
            col, op = parse_filter_key(key)
            if col not in allowed:
                continue
            cfg = res.column(col)
            if cfg is None:
                continue
            filt = filter_expr(col, op, raw, cfg.filter_type)
            if filt is not None:
                where.append(filt)
    if hide_soft_deleted and "deleted_at" in res.model.model_fields:
        inc = (filters or {}).get("include_deleted", "")
        if str(inc).lower() not in {"1", "true", "yes"}:
            where.append(is_null("deleted_at"))
    return where
