"""Parameterized SQL builder (Sans-I/O)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from phzyx.orm.expr import Filter, OrderBy, compile_filters
from phzyx.orm.keyset import build_keyset_where, decode_cursor
from phzyx.schema.ddl import quote_ident
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect


@dataclass
class SqlFragment:
    sql: str
    params: list[Any] = field(default_factory=list)


def _table_name(model: type[Model], dialect: Dialect) -> str:
    info = get_table_info(model)
    if info.schema_name and dialect is Dialect.POSTGRES:
        return f"{quote_ident(info.schema_name, dialect)}.{quote_ident(info.name, dialect)}"
    return quote_ident(info.name, dialect)


def _columns(model: type[Model]) -> tuple[str, ...]:
    return tuple(model.model_fields.keys())


def build_insert(
    model: type[Model],
    values: dict[str, Any],
    *,
    dialect: Dialect | str = Dialect.SQLITE,
    returning: bool = False,
) -> SqlFragment:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    cols = list(values.keys())
    if not cols:
        raise ValueError("insert requires at least one column")
    table = _table_name(model, d)
    col_sql = ", ".join(quote_ident(c, d) for c in cols)
    placeholders = ", ".join("?" if d is Dialect.SQLITE else "%s" for _ in cols)
    sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
    if returning and d is Dialect.POSTGRES:
        all_cols = ", ".join(quote_ident(c, d) for c in _columns(model))
        sql += f" RETURNING {all_cols}"
    return SqlFragment(sql=sql, params=[values[c] for c in cols])


def build_update(
    model: type[Model],
    values: dict[str, Any],
    where: Sequence[Filter],
    *,
    dialect: Dialect | str = Dialect.SQLITE,
    returning: bool = False,
) -> SqlFragment:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if not values:
        raise ValueError("update requires at least one column")
    if not where:
        raise ValueError("update requires a WHERE clause (safety)")
    table = _table_name(model, d)
    ph = "?" if d is Dialect.SQLITE else "%s"
    set_parts = [f"{quote_ident(c, d)} = {ph}" for c in values]
    params: list[Any] = list(values.values())
    where_sql, where_params = compile_filters(where, dialect=d)
    params.extend(where_params)
    sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where_sql}"
    if returning and d is Dialect.POSTGRES:
        all_cols = ", ".join(quote_ident(c, d) for c in _columns(model))
        sql += f" RETURNING {all_cols}"
    return SqlFragment(sql=sql, params=params)


def build_delete(
    model: type[Model],
    where: Sequence[Filter],
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> SqlFragment:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if not where:
        raise ValueError("delete requires a WHERE clause (safety)")
    table = _table_name(model, d)
    where_sql, where_params = compile_filters(where, dialect=d)
    sql = f"DELETE FROM {table} WHERE {where_sql}"
    return SqlFragment(sql=sql, params=where_params)


def build_select(
    model: type[Model],
    *,
    where: Sequence[Filter] = (),
    order_by: Sequence[OrderBy] = (),
    limit: int | None = None,
    offset: int | None = None,
    cursor: str | None = None,
    cursor_after: bool = True,
    dialect: Dialect | str = Dialect.SQLITE,
) -> SqlFragment:
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    table = _table_name(model, d)
    cols = ", ".join(quote_ident(c, d) for c in _columns(model))
    sql = f"SELECT {cols} FROM {table}"
    params: list[Any] = []
    clauses: list[str] = []
    if where:
        where_sql, where_params = compile_filters(where, dialect=d)
        clauses.append(where_sql)
        params.extend(where_params)
    if cursor:
        if not order_by:
            raise ValueError("keyset cursor requires order_by")
        values = decode_cursor(cursor)
        ks_sql, ks_params = build_keyset_where(order_by, values, dialect=d, after=cursor_after)
        clauses.append(ks_sql)
        params.extend(ks_params)
    if clauses:
        sql += " WHERE " + " AND ".join(f"({c})" for c in clauses)
    if order_by:
        parts = []
        for o in order_by:
            direction = "DESC" if o.descending else "ASC"
            parts.append(f"{quote_ident(o.column, d)} {direction}")
        sql += " ORDER BY " + ", ".join(parts)
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    if offset is not None:
        # Discouraged for deep pages — prefer cursor=
        sql += f" OFFSET {int(offset)}"
    return SqlFragment(sql=sql, params=params)


def build_select_by_pk(
    model: type[Model],
    key: Any,
    *,
    dialect: Dialect | str = Dialect.SQLITE,
) -> SqlFragment:
    """Build SELECT for single or composite primary key.

    ``key`` is a scalar for single PK, or a dict/tuple for composite.
    """
    from phzyx.orm.expr import eq

    info = get_table_info(model)
    pk = info.primary_key
    if not pk:
        raise ValueError(f"{model.__name__} has no primary key")
    filters: list[Filter] = []
    if len(pk) == 1:
        val = key[pk[0]] if isinstance(key, dict) else key
        filters.append(eq(pk[0], val))
    else:
        if isinstance(key, dict):
            for col in pk:
                if col not in key:
                    raise ValueError(f"composite key missing {col!r}")
                filters.append(eq(col, key[col]))
        elif isinstance(key, (tuple, list)):
            if len(key) != len(pk):
                raise ValueError(f"composite key expects {len(pk)} values")
            for col, val in zip(pk, key, strict=True):
                filters.append(eq(col, val))
        else:
            raise ValueError("composite primary key requires dict or tuple")
    return build_select(model, where=filters, limit=1, dialect=dialect)
