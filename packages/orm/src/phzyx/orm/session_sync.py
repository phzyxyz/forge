"""Session — sync CRUD (API mirror of AsyncSession for dual tests / CLI)."""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any, TypeVar

from phzyx.orm.engine_sync import Engine
from phzyx.orm.expr import Filter, OrderBy, eq
from phzyx.orm.hydrate import model_to_row, row_to_model
from phzyx.orm.sql import (
    build_delete,
    build_insert,
    build_select,
    build_select_by_pk,
    build_update,
)
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import Dialect

M = TypeVar("M", bound=Model)


class Session:
    """Sync unit-of-work for CRUD + queries (mirrors AsyncSession)."""

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
        data = model_to_row(instance)
        frag = build_insert(type(instance), data, dialect=self.dialect)
        self._execute(frag.sql, frag.params)
        return instance

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
        where = [eq(col, data[col]) for col in info.primary_key]
        frag = build_update(type(instance), values, where, dialect=self.dialect)
        self._execute(frag.sql, frag.params)
        return type(instance).model_validate({**data, **values})

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
        )
        return self._fetch_all(model, frag.sql, frag.params)

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
        from phzyx.orm.keyset import (
            KeysetPage,
            cursor_from_row,
            default_order_columns,
            order_from_columns,
        )

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
        from phzyx.orm.keyset import default_order_columns, order_from_columns

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

    def _execute(self, sql: str, params: list[Any]) -> None:
        if self.dialect is Dialect.SQLITE:
            self._conn.execute(sql, params)
        else:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)

    def _fetch_one(self, model: type[M], sql: str, params: list[Any]) -> M | None:
        if self.dialect is Dialect.SQLITE:
            cur = self._conn.execute(sql, params)
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
            cur = self._conn.execute(sql, params)
            return [row_to_model(model, r) for r in cur.fetchall()]
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            cols = list(model.model_fields.keys())
            return [row_to_model(model, dict(zip(cols, r, strict=False))) for r in cur.fetchall()]


def create_session(engine: Engine) -> Session:
    return Session(engine.connect(), dialect=engine.dialect)
