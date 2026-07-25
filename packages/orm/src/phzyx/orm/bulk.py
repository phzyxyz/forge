"""Bulk insert / update helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from phzyx.orm.expr import eq
from phzyx.orm.insert_prep import autoincrement_pk_name, utcnow
from phzyx.orm.session_sync import Session
from phzyx.orm.sql import build_insert, build_update
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect
from pydantic_core import PydanticUndefined


def bulk_insert(
    session: Session,
    model: type[Model],
    rows: Sequence[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> int:
    """Insert many row dicts. Omits null autoincrement PKs per row.

    Fills model field defaults and auto_now(_add) timestamps when keys are
    missing so partial dicts do not insert NULL into NOT NULL columns.

    Returns number of rows submitted (not DB rowcount on all drivers).
    """
    if not rows:
        return 0
    info = get_table_info(model)
    ai = autoincrement_pk_name(model)
    n = 0
    batch: list[dict[str, Any]] = []
    for raw in rows:
        data = dict(raw)
        if ai is not None and data.get(ai) is None:
            data.pop(ai, None)
        # Apply pydantic field defaults for omitted keys (e.g. balance=0).
        for field_name, field_info in model.model_fields.items():
            if field_name in data:
                continue
            default = field_info.default
            if default is not PydanticUndefined and default is not None:
                data[field_name] = default
            elif field_info.default_factory is not None:
                data[field_name] = field_info.default_factory()
        for name, meta in info.columns.items():
            if meta.generated:
                data.pop(name, None)
                continue
            if meta.auto_now_add and data.get(name) is None:
                data[name] = utcnow()
            if meta.auto_now and data.get(name) is None:
                data[name] = utcnow()
        batch.append(data)
        if len(batch) >= chunk_size:
            n += _flush_inserts(session, model, batch)
            batch.clear()
    if batch:
        n += _flush_inserts(session, model, batch)
    return n


def _flush_inserts(session: Session, model: type[Model], batch: list[dict[str, Any]]) -> int:
    ai = autoincrement_pk_name(model)
    identity_on = False
    table = get_table_info(model).name
    conn = session._conn  # same live connection as Session.execute
    if (
        session.dialect is Dialect.MSSQL
        and ai is not None
        and any(row.get(ai) is not None for row in batch)
    ):
        cur = conn.cursor()
        try:
            cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
        finally:
            cur.close()
        identity_on = True
    try:
        for data in batch:
            frag = build_insert(model, data, dialect=session.dialect)
            session.execute(frag.sql, frag.params)
    finally:
        if identity_on:
            cur = conn.cursor()
            try:
                cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            finally:
                cur.close()
    return len(batch)


def bulk_update(
    session: Session,
    model: type[Model],
    rows: Sequence[dict[str, Any]],
    *,
    key: str | Sequence[str] | None = None,
) -> int:
    """Update rows by primary key (or explicit key columns).

    Each dict must include key columns plus fields to set.
    """
    info = get_table_info(model)
    key_cols = list(key) if key is not None else list(info.primary_key)
    if isinstance(key, str):
        key_cols = [key]
    n = 0
    for raw in rows:
        data = dict(raw)
        where = []
        for col in key_cols:
            if col not in data:
                raise ValueError(f"bulk_update row missing key {col!r}")
            where.append(eq(col, data[col]))
        values = {k: v for k, v in data.items() if k not in key_cols}
        for name, meta in info.columns.items():
            if meta.auto_now:
                values[name] = utcnow()
        if not values:
            continue
        frag = build_update(model, values, where, dialect=session.dialect)
        session.execute(frag.sql, frag.params)
        n += 1
    return n
