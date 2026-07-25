"""Session — sync CRUD (API mirror of AsyncSession).

Prefer AsyncSession for app routes. Sync Session is for scripts/CLI and for
AdminBoard's session_factory today (same models, dual production path).
"""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any, TypeVar

from phzyx.orm.engine_sync import Engine
from phzyx.orm.errors import ConflictError
from phzyx.orm.expr import Filter, OrderBy, eq
from phzyx.orm.hydrate import model_to_row, row_to_model
from phzyx.orm.insert_prep import prepare_insert_values, prepare_update_values
from phzyx.orm.keyset import (
    KeysetPage,
    cursor_from_row,
    default_order_columns,
    order_from_columns,
)
from phzyx.orm.sql import (
    build_count,
    build_delete,
    build_insert,
    build_select,
    build_select_by_pk,
    build_update,
)
from phzyx.orm.sqlite_params import adapt_sqlite_params
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect

M = TypeVar("M", bound=Model)


class Session:
    """Sync unit-of-work for CRUD + queries (mirrors AsyncSession).

    Use for scripts/CLI and AdminBoard session_factory; prefer AsyncSession
    for app request handlers.
    """

    def __init__(self, conn: Any, *, dialect: Dialect) -> None:
        self._conn = conn
        self.dialect = dialect

    def __enter__(self) -> Session:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()

    def close(self) -> None:
        self._conn.close()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def begin(self) -> Session:
        if self.dialect is Dialect.SQLITE:
            self._conn.execute("BEGIN")
        return self

    def add(self, instance: Model) -> Model:
        data, omitted_pk = prepare_insert_values(instance)
        use_returning = self.dialect is Dialect.POSTGRES
        frag = build_insert(
            type(instance),
            data,
            dialect=self.dialect,
            returning=use_returning,
        )
        if use_returning:
            row = self.execute_returning(frag.sql, frag.params)
            if row is not None:
                return row_to_model(type(instance), row)
            # RETURNING empty is a hard failure when we omitted AI PK
            if omitted_pk is not None:
                raise RuntimeError(
                    f"INSERT RETURNING produced no row for {type(instance).__name__}"
                )
            return type(instance).model_validate(data)

        # SQL Server: explicit values into IDENTITY columns need IDENTITY_INSERT.
        identity_on = False
        table_name = ""
        if self.dialect is Dialect.MSSQL and omitted_pk is None:
            from phzyx.orm.insert_prep import autoincrement_pk_name

            ai = autoincrement_pk_name(type(instance))
            if ai is not None and data.get(ai) is not None:
                table_name = get_table_info(type(instance)).name
                self._execute(f"SET IDENTITY_INSERT [{table_name}] ON", [])
                identity_on = True
        try:
            self._execute(frag.sql, frag.params)
            base = {**data}
            if omitted_pk is not None:
                new_id = self._lastrowid()
                if new_id is None:
                    raise RuntimeError(
                        f"INSERT succeeded but lastrowid missing for {type(instance).__name__}"
                    )
                base[omitted_pk] = new_id
            return type(instance).model_validate(base)
        finally:
            if identity_on:
                self._execute(f"SET IDENTITY_INSERT [{table_name}] OFF", [])

    def get(self, model: type[M], key: Any) -> M | None:
        frag = build_select_by_pk(model, key, dialect=self.dialect)
        return self._fetch_one(model, frag.sql, frag.params)

    def delete(self, instance: Model) -> None:
        info = get_table_info(type(instance))
        data = model_to_row(instance)
        where = [eq(col, data[col]) for col in info.primary_key]
        frag = build_delete(type(instance), where, dialect=self.dialect)
        self._execute(frag.sql, frag.params)

    def update(self, instance: Model, **values: Any) -> Model:
        info = get_table_info(type(instance))
        data = model_to_row(instance)
        # Reject updates that don't touch PK identity (missing PK on instance)
        for col in info.primary_key:
            if data.get(col) is None:
                raise ValueError(
                    f"cannot update {type(instance).__name__}: primary key {col!r} is unset"
                )
        try:
            values = prepare_update_values(instance, values)
        except ValueError:
            # No mutable columns (e.g. only generated) — no-op return current
            if not values:
                return instance
            raise
        where = [eq(col, data[col]) for col in info.primary_key]
        has_opt = False
        for col_name, meta in info.columns.items():
            if not meta.optimistic:
                continue
            has_opt = True
            old_v = data.get(col_name)
            if old_v is None:
                old_v = 0
            where.append(eq(col_name, old_v))
            values[col_name] = int(old_v) + 1
        frag = build_update(type(instance), values, where, dialect=self.dialect)
        n = self._execute_rowcount(frag.sql, frag.params)
        if has_opt and n == 0:
            raise ConflictError("optimistic lock failed: row was updated elsewhere")
        if has_opt and n < 0:
            self._verify_optimistic(type(instance), data, info)
        return type(instance).model_validate({**data, **values})

    def count(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
    ) -> int:
        """Efficient COUNT(*) — does not load rows."""
        frag = build_count(model, where=where, dialect=self.dialect)
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute(frag.sql, adapt_sqlite_params(frag.params))
            row = cur.fetchone()
            return int(row[0]) if row else 0
        with self._conn.cursor() as cur:
            cur.execute(frag.sql, frag.params)
            row = cur.fetchone()
            if row is None:
                return 0
            return int(row[0] if not isinstance(row, dict) else next(iter(row.values())))

    def query(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
        order_by: Sequence[OrderBy] = (),
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
        cursor_after: bool = True,
        for_update: bool | str = False,
    ) -> list[M]:
        frag = build_select(
            model,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
            cursor=cursor,
            cursor_after=cursor_after,
            dialect=self.dialect,
            for_update=for_update,
        )
        return self._fetch_all(model, frag.sql, frag.params)

    def get_for_update(
        self,
        model: type[M],
        key: Any,
        *,
        nowait: bool = False,
        skip_locked: bool = False,
    ) -> M | None:
        """Fetch by PK with row lock (FOR UPDATE on PG/MySQL; BEGIN on SQLite)."""
        if self.dialect is Dialect.SQLITE:
            # Serialize writers in this connection.
            self.begin()
        mode: bool | str = True
        if nowait:
            mode = "NOWAIT"
        elif skip_locked:
            mode = "SKIP LOCKED"
        info = get_table_info(model)
        pk = info.primary_key
        if len(pk) == 1:
            val = key[pk[0]] if isinstance(key, dict) else key
            where = [eq(pk[0], val)]
        else:
            if not isinstance(key, dict):
                raise ValueError("composite key requires dict")
            where = [eq(c, key[c]) for c in pk]
        # SQLite: for_update flag is a no-op in SQL builder
        fu: bool | str = False if self.dialect is Dialect.SQLITE else mode
        rows = self.query(model, where=where, limit=1, for_update=fu)
        return rows[0] if rows else None

    def query_keyset(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
        order_by: Sequence[OrderBy] | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> Any:
        """Fetch a keyset page with next_cursor (limit+1 probe)."""
        order = list(order_by) if order_by else order_from_columns(default_order_columns(model))
        cols = [o.column for o in order]
        rows = self.query(
            model,
            where=where,
            order_by=order,
            limit=limit + 1,
            cursor=cursor,
            cursor_after=True,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_c = cursor_from_row(page_rows[-1], cols) if has_more and page_rows else None
        prev_c = cursor  # client can walk back with reverse order later
        return KeysetPage(
            items=page_rows,
            next_cursor=next_c,
            prev_cursor=prev_c,
            has_more=has_more,
        )

    def iter_query(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
        order_by: Sequence[OrderBy] | None = None,
        chunk_size: int = 500,
    ):
        """Stream rows via keyset chunks (bounded memory)."""
        order = list(order_by) if order_by else order_from_columns(default_order_columns(model))
        cursor = None
        while True:
            page = self.query_keyset(
                model, where=where, order_by=order, limit=chunk_size, cursor=cursor
            )
            yield from page.items
            if not page.has_more or not page.next_cursor:
                break
            cursor = page.next_cursor

    def execute(self, sql: str, params: list[Any] | None = None) -> int:
        """Execute a parameterized statement.

        Returns:
            Driver rowcount when available, otherwise ``-1``.
            Optimistic-lock code treats ``0`` as a miss and ``-1`` as
            “unknown — re-verify”.
        """
        return self._execute_rowcount(sql, list(params or []))

    def execute_returning(self, sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
        """Run INSERT/UPDATE…RETURNING (Postgres) and return a column mapping."""
        with self._conn.cursor() as cur:
            cur.execute(sql, list(params or []))
            row = cur.fetchone()
            if row is None:
                return None
            if isinstance(row, dict):
                return row
            if cur.description:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row, strict=False))
            return None

    def _execute(self, sql: str, params: list[Any]) -> None:
        """Internal alias used by session CRUD paths."""
        self.execute(sql, params)

    def _execute_rowcount(self, sql: str, params: list[Any]) -> int:
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute(sql, adapt_sqlite_params(params))
            rc = getattr(cur, "rowcount", None)
            return -1 if rc is None else int(rc)
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            # Capture insert id before the cursor context exits (PyMySQL).
            lid = getattr(cur, "lastrowid", None)
            if lid:
                self._last_insert_id = lid
            elif hasattr(self._conn, "insert_id"):
                try:
                    conn_lid = self._conn.insert_id()
                    if conn_lid:
                        self._last_insert_id = conn_lid
                except Exception:
                    pass
            rc = getattr(cur, "rowcount", None)
            return -1 if rc is None else int(rc)

    def _verify_optimistic(self, model: type[Model], data: dict[str, Any], info: Any) -> None:
        """When rowcount is unreliable, re-read and compare optimistic columns."""
        key = (
            data[info.primary_key[0]]
            if len(info.primary_key) == 1
            else {c: data[c] for c in info.primary_key}
        )
        current = self.get(model, key)
        if current is None:
            raise ConflictError("optimistic lock failed: row missing")
        for col_name, meta in info.columns.items():
            if meta.optimistic and getattr(current, col_name, None) != data.get(col_name):
                raise ConflictError("optimistic lock failed: row was updated elsewhere")

    def _lastrowid(self) -> Any:
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute("SELECT last_insert_rowid()")
            row = cur.fetchone()
            return row[0] if row else None
        if self.dialect is Dialect.MSSQL:
            cur = self._conn.cursor()
            try:
                cur.execute("SELECT CAST(SCOPE_IDENTITY() AS BIGINT)")
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else None
            finally:
                cur.close()
        # Prefer id captured on the last execute (MySQL/PyMySQL closes cursors).
        cached = getattr(self, "_last_insert_id", None)
        if cached is not None:
            return cached
        # PyMySQL: connection.insert_id()
        if hasattr(self._conn, "insert_id"):
            try:
                lid = self._conn.insert_id()
                if lid:
                    return lid
            except Exception:
                pass
        if hasattr(self._conn, "lastrowid") and self._conn.lastrowid:
            return self._conn.lastrowid
        try:
            with self._conn.cursor() as cur:
                if hasattr(cur, "lastrowid") and cur.lastrowid:
                    return cur.lastrowid
        except Exception:
            return None
        return None

    def _fetch_one(self, model: type[M], sql: str, params: list[Any]) -> M | None:
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute(sql, adapt_sqlite_params(params))
            row = cur.fetchone()
            return None if row is None else row_to_model(model, row)
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                return None
            cols = list(model.model_fields.keys())
            return row_to_model(model, dict(zip(cols, row, strict=False)))

    def _fetch_all(self, model: type[M], sql: str, params: list[Any]) -> list[M]:
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute(sql, adapt_sqlite_params(params))
            return [row_to_model(model, r) for r in cur.fetchall()]
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            cols = list(model.model_fields.keys())
            return [row_to_model(model, dict(zip(cols, r, strict=False))) for r in cur.fetchall()]


def create_session(engine: Engine) -> Session:
    return Session(engine.connect(), dialect=engine.dialect)
