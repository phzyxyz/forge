"""Prepare insert/update values: AI PK, generated omit, timestamps."""

from __future__ import annotations

import warnings
from datetime import UTC, date, datetime, time
from typing import Any

from phzyx.schema.model import Model, get_table_info


def utcnow() -> datetime:
    """Naive UTC wall clock — portable across SQLite / Postgres / MySQL.

    MySQL ``DATETIME`` rejects timezone-aware values and ISO strings with
    ``+00:00``. Postgres and SQLite accept naive UTC fine.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def autoincrement_pk_name(model: type[Model]) -> str | None:
    """Return single autoincrement PK column name, if any."""
    info = get_table_info(model)
    if len(info.primary_key) != 1:
        return None
    name = info.primary_key[0]
    meta = info.columns.get(name)
    if meta is None:
        return None
    if meta.autoincrement is False:
        return None
    if meta.foreign_key:
        return None
    return name


def _is_empty_pk(val: Any) -> bool:
    return val is None or val == "" or val == b""


def _sql_friendly(value: Any) -> Any:
    """Normalize values so every dialect's DB-API can bind them.

    - timezone-aware datetimes → naive UTC
    - leave date/time/datetime objects as objects (drivers adapt them)
    - leave other JSON-ish scalars as-is
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    if isinstance(value, (date, time, datetime)):
        return value
    return value


def prepare_insert_values(instance: Model) -> tuple[dict[str, Any], str | None]:
    """Return (values for INSERT, omitted_autoincrement_pk_or_None).

    Edge rules:
    - Omit autoincrement PK when None/"" so DB generates it.
    - Never insert generated columns (DB computes them).
    - Fill auto_now_add / auto_now when unset (naive UTC).
    - Explicit non-empty AI PK is kept (seeds / imports).
    """
    model = type(instance)
    info = get_table_info(model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        # mode="python" keeps datetime objects; mode="json" emits ISO with tz
        # that MySQL DATETIME rejects.
        data = instance.model_dump(mode="python")

    data = {k: _sql_friendly(v) for k, v in data.items()}

    # Drop generated columns always on insert
    for name, meta in info.columns.items():
        if meta.generated:
            data.pop(name, None)

    ai_pk = autoincrement_pk_name(model)
    omitted: str | None = None
    if ai_pk is not None and _is_empty_pk(data.get(ai_pk)):
        data.pop(ai_pk, None)
        omitted = ai_pk

    now: datetime | None = None
    for name, meta in info.columns.items():
        if meta.generated:
            continue
        needs_ts = (meta.auto_now_add or meta.auto_now) and _is_empty_pk(data.get(name))
        if needs_ts:
            if now is None:
                now = utcnow()
            data[name] = now

    if not data:
        raise ValueError(
            "insert requires at least one column after omitting autoincrement/generated defaults"
        )
    return data, omitted


def prepare_update_values(
    instance: Model,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Merge update values with auto_now; strip unsafe / non-mutable columns.

    Always drops:
    - **primary key** columns (identity is only in WHERE, never SET — prevents
      accidental or malicious PK rewrites via ``update`` / ``update_by_pk``)
    - **generated** columns (DB-owned)

    Fills ``auto_now`` timestamps. Raises if nothing remains to SET.
    """
    info = get_table_info(type(instance))
    pk = set(info.primary_key)
    out = {k: _sql_friendly(v) for k, v in values.items() if k not in pk}
    for name, meta in info.columns.items():
        if meta.generated:
            out.pop(name, None)
    now: datetime | None = None
    for name, meta in info.columns.items():
        if meta.auto_now:
            if now is None:
                now = utcnow()
            out[name] = now
    if not out:
        raise ValueError(
            "update requires at least one column after stripping primary key / generated"
        )
    return out
