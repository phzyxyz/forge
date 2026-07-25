"""Dialect-aware upsert helpers (SQLite / Postgres / MySQL)."""

from __future__ import annotations

from typing import Any

from phzyx.orm.hydrate import row_to_model
from phzyx.orm.insert_prep import prepare_insert_values
from phzyx.orm.session_sync import Session
from phzyx.schema.ddl import quote_ident as qident
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect


def upsert(
    session: Session,
    instance: Model,
    *,
    conflict: list[str] | None = None,
    update_columns: list[str] | None = None,
) -> Model:
    """Insert or update on conflict.

    * SQLite / Postgres: ``ON CONFLICT (cols) DO UPDATE`` / ``DO NOTHING``
    * MySQL: ``ON DUPLICATE KEY UPDATE`` (classic ``VALUES(col)`` form)

    ``conflict`` defaults to primary key columns. Returns a re-fetched or
    RETURNING-hydrated model when possible.
    """
    model = type(instance)
    info = get_table_info(model)
    conf = list(conflict) if conflict else list(info.primary_key)
    if not conf:
        raise ValueError("upsert requires conflict target columns")

    data, omitted = prepare_insert_values(instance)
    # Conflict targets must be present for ON CONFLICT / lookup after insert
    for c in conf:
        if c not in data and c != omitted:
            val = getattr(instance, c, None)
            if val is not None:
                data[c] = val
        if c not in data and c == omitted:
            raise ValueError(
                f"upsert cannot omit autoincrement conflict column {c!r}; "
                f"pass an explicit value or use a natural unique key"
            )

    cols = list(data.keys())
    if not cols:
        raise ValueError("upsert requires columns")
    d = session.dialect
    table = qident(info.name, d)
    col_sql = ", ".join(qident(c, d) for c in cols)
    ph = "?" if d is Dialect.SQLITE else "%s"
    placeholders = ", ".join(ph for _ in cols)
    params: list[Any] = [data[c] for c in cols]

    updates = (
        list(update_columns) if update_columns is not None else [c for c in cols if c not in conf]
    )
    # Never try to "update" generated columns
    for name, meta in info.columns.items():
        if meta.generated and name in updates:
            updates = [u for u in updates if u != name]

    if d is Dialect.MYSQL:
        if not updates:
            # No-op update keeps row (MySQL requires SET clause)
            first = cols[0]
            set_sql = f"{qident(first, d)} = VALUES({qident(first, d)})"
        else:
            set_sql = ", ".join(f"{qident(c, d)} = VALUES({qident(c, d)})" for c in updates)
        sql = (
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {set_sql}"
        )
    elif d is Dialect.MSSQL:
        # MERGE … WHEN MATCHED / NOT MATCHED (SQL Server 2008+).
        conf_on = " AND ".join(f"target.{qident(c, d)} = source.{qident(c, d)}" for c in conf)
        source_cols = ", ".join(f"{ph} AS {qident(c, d)}" for c in cols)
        if updates:
            set_sql = ", ".join(f"target.{qident(c, d)} = source.{qident(c, d)}" for c in updates)
            matched = f"WHEN MATCHED THEN UPDATE SET {set_sql}"
        else:
            matched = "WHEN MATCHED THEN UPDATE SET target.{0} = target.{0}".format(
                qident(conf[0], d)
            )
        insert_cols = ", ".join(qident(c, d) for c in cols)
        insert_vals = ", ".join(f"source.{qident(c, d)}" for c in cols)
        sql = (
            f"MERGE {table} AS target "
            f"USING (SELECT {source_cols}) AS source "
            f"ON ({conf_on}) "
            f"{matched} "
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
        )
    else:
        conf_sql = ", ".join(qident(c, d) for c in conf)
        if not updates:
            sql = (
                f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conf_sql}) DO NOTHING"
            )
        else:
            set_sql = ", ".join(f"{qident(c, d)} = excluded.{qident(c, d)}" for c in updates)
            sql = (
                f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conf_sql}) DO UPDATE SET {set_sql}"
            )
        if d is Dialect.POSTGRES:
            all_cols = ", ".join(qident(c, d) for c in model.model_fields)
            sql += f" RETURNING {all_cols}"

    if d is Dialect.POSTGRES and " RETURNING " in sql:
        row = session.execute_returning(sql, params)
        if row is not None:
            return row_to_model(model, row)
        # DO NOTHING with no row — fetch existing
        return _fetch_by_conflict(session, model, conf, data) or instance

    identity_on = False
    table_plain = info.name
    if d is Dialect.MSSQL:
        from phzyx.orm.insert_prep import autoincrement_pk_name

        ai = autoincrement_pk_name(model)
        if ai is not None and data.get(ai) is not None:
            cur = session._conn.cursor()
            try:
                cur.execute(f"SET IDENTITY_INSERT [{table_plain}] ON")
            finally:
                cur.close()
            identity_on = True
    try:
        session.execute(sql, params)
    finally:
        if identity_on:
            cur = session._conn.cursor()
            try:
                cur.execute(f"SET IDENTITY_INSERT [{table_plain}] OFF")
            finally:
                cur.close()
    found = _fetch_by_conflict(session, model, conf, data)
    return found if found is not None else instance


def _fetch_by_conflict(
    session: Session,
    model: type[Model],
    conf: list[str],
    data: dict[str, Any],
) -> Model | None:
    if len(conf) == 1:
        key = data.get(conf[0])
        if key is None:
            return None
        return session.get(model, key)
    key = {c: data[c] for c in conf if c in data}
    if len(key) != len(conf):
        return None
    return session.get(model, key)
