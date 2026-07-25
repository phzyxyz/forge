"""Pre-insert / pre-update uniqueness checks for AdminService.

Catches duplicate unique fields before the driver IntegrityError so operators
get a clean 422 with field-level messages (e.g. email already exists).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from phzyx.orm.expr import Filter, eq
from phzyx.schema.model import Model, get_table_info


def _row_key(model: type[Model], row: Any) -> Any:
    pk = get_table_info(model).primary_key
    if len(pk) == 1:
        return getattr(row, pk[0])
    return {c: getattr(row, c) for c in pk}


def _is_same_row(model: type[Model], row: Any, exclude_key: Any | None) -> bool:
    if exclude_key is None:
        return False
    rk = _row_key(model, row)
    if rk == exclude_key:
        return True
    # Tolerate str/int identity drift (e.g. "1" vs 1).
    try:
        if str(rk) == str(exclude_key):
            return True
    except Exception:
        pass
    return False


def unique_field_errors(
    model: type[Model],
    data: dict[str, Any],
    *,
    query: Callable[[Sequence[Filter]], Sequence[Any]],
    exclude_key: Any | None = None,
) -> dict[str, str]:
    """Return ``{field: message}`` for unique violations in ``data``.

    ``query(where)`` must return model instances matching the filters (limit
    small — callers typically use ``limit=5``).
    """
    info = get_table_info(model)
    errors: dict[str, str] = {}

    for col_name, meta in info.columns.items():
        if not meta.unique or col_name not in data:
            continue
        val = data[col_name]
        if val is None or val == "":
            continue
        try:
            rows = query([eq(col_name, val)])
        except Exception:
            continue
        for row in rows:
            if _is_same_row(model, row, exclude_key):
                continue
            errors[col_name] = "already exists"
            break

    # Meta.unique_together = (("a", "b"), ...)
    meta_cls = getattr(model, "Meta", None)
    for cols in getattr(meta_cls, "unique_together", ()) or ():
        if not cols:
            continue
        names = tuple(cols)
        if any(n not in data for n in names):
            continue
        if any(data.get(n) is None or data.get(n) == "" for n in names):
            continue
        where = [eq(n, data[n]) for n in names]
        try:
            rows = query(where)
        except Exception:
            continue
        for row in rows:
            if _is_same_row(model, row, exclude_key):
                continue
            # Attribute the message to the first column for form highlighting.
            errors[names[0]] = f"already exists for ({', '.join(names)})"
            break

    return errors


def raise_if_unique_violations(
    model: type[Model],
    data: dict[str, Any],
    *,
    query: Callable[[Sequence[Filter]], Sequence[Any]],
    exclude_key: Any | None = None,
) -> None:
    """Raise :class:`ValidationAdminError` when unique constraints would fail."""
    from phzyx.admin.errors import ValidationAdminError

    errs = unique_field_errors(model, data, query=query, exclude_key=exclude_key)
    if errs:
        raise ValidationAdminError("Validation failed", fields=errs)


async def raise_if_unique_violations_async(
    model: type[Model],
    data: dict[str, Any],
    *,
    query,  # async (where) -> rows
    exclude_key: Any | None = None,
) -> None:
    """Async variant of :func:`raise_if_unique_violations`."""
    from phzyx.admin.errors import ValidationAdminError

    info = get_table_info(model)
    errors: dict[str, str] = {}

    for col_name, meta in info.columns.items():
        if not meta.unique or col_name not in data:
            continue
        val = data[col_name]
        if val is None or val == "":
            continue
        try:
            rows = await query([eq(col_name, val)])
        except Exception:
            continue
        for row in rows:
            if _is_same_row(model, row, exclude_key):
                continue
            errors[col_name] = "already exists"
            break

    meta_cls = getattr(model, "Meta", None)
    for cols in getattr(meta_cls, "unique_together", ()) or ():
        if not cols:
            continue
        names = tuple(cols)
        if any(n not in data for n in names):
            continue
        if any(data.get(n) is None or data.get(n) == "" for n in names):
            continue
        where = [eq(n, data[n]) for n in names]
        try:
            rows = await query(where)
        except Exception:
            continue
        for row in rows:
            if _is_same_row(model, row, exclude_key):
                continue
            errors[names[0]] = f"already exists for ({', '.join(names)})"
            break

    if errors:
        raise ValidationAdminError("Validation failed", fields=errors)
