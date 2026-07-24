"""AsyncSession — async CRUD over Phzyx models."""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any, TypeVar

from phzyx.orm.engine_async import AsyncEngine
from phzyx.orm.expr import Filter, OrderBy
from phzyx.orm.hydrate import model_to_row, row_to_model
from phzyx.orm.sql import (
    build_delete,
    build_insert,
    build_select,
    build_select_by_pk,
    build_update,
)
from phzyx.schema.model import Model
from phzyx.schema.types import Dialect

M = TypeVar("M", bound=Model)


class AsyncSession:
    """Async unit-of-work for CRUD + queries."""

    def __init__(self, conn: Any, *, dialect: Dialect) -> None:
        self._conn = conn
        self.dialect = dialect
        self._in_tx = False

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self.close()

    async def close(self) -> None:
        if hasattr(self._conn, "close"):
            result = self._conn.close()
            if hasattr(result, "__await__"):
                await result

    async def commit(self) -> None:
        if self.dialect is Dialect.SQLITE:
            await self._conn.commit()
        elif hasattr(self._conn, "transaction") and self._in_tx:
            # asyncpg uses transaction context; plain connection auto-commits statements
            pass
        self._in_tx = False

    async def rollback(self) -> None:
        if self.dialect is Dialect.SQLITE:
            await self._conn.rollback()
        self._in_tx = False

    async def begin(self) -> AsyncSession:
        if self.dialect is Dialect.SQLITE:
            await self._conn.execute("BEGIN")
        self._in_tx = True
        return self

    async def add(self, instance: Model) -> Model:
        data = model_to_row(instance)
        frag = build_insert(
            type(instance),
            data,
            dialect=self.dialect,
            returning=self.dialect is Dialect.POSTGRES,
        )
        if self.dialect is Dialect.SQLITE:
            await self._conn.execute(frag.sql, frag.params)
            # re-read if single pk autoincrement not used; values already known
            return instance
        # asyncpg
        if frag.sql.upper().endswith("RETURNING") or " RETURNING " in frag.sql.upper():
            row = await self._conn.fetchrow(frag.sql, *frag.params)
            if row is not None:
                return row_to_model(type(instance), dict(row))
        else:
            await self._conn.execute(frag.sql, *frag.params)
        return instance

    async def get(self, model: type[M], key: Any) -> M | None:
        frag = build_select_by_pk(model, key, dialect=self.dialect)
        return await self._fetch_one(model, frag.sql, frag.params)

    async def delete(self, instance: Model) -> None:
        from phzyx.orm.expr import eq
        from phzyx.schema.model import get_table_info

        info = get_table_info(type(instance))
        data = model_to_row(instance)
        where = [eq(col, data[col]) for col in info.primary_key]
        frag = build_delete(type(instance), where, dialect=self.dialect)
        await self._execute(frag.sql, frag.params)

    async def update(self, instance: Model, **values: Any) -> Model:
        from phzyx.orm.expr import eq
        from phzyx.schema.model import get_table_info

        info = get_table_info(type(instance))
        data = model_to_row(instance)
        where = [eq(col, data[col]) for col in info.primary_key]
        frag = build_update(type(instance), values, where, dialect=self.dialect)
        await self._execute(frag.sql, frag.params)
        merged = {**data, **values}
        return type(instance).model_validate(merged)

    async def query(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
        order_by: Sequence[OrderBy] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[M]:
        frag = build_select(
            model,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
            dialect=self.dialect,
        )
        return await self._fetch_all(model, frag.sql, frag.params)

    async def _execute(self, sql: str, params: list[Any]) -> None:
        if self.dialect is Dialect.SQLITE:
            await self._conn.execute(sql, params)
        else:
            await self._conn.execute(sql, *params)

    async def _fetch_one(self, model: type[M], sql: str, params: list[Any]) -> M | None:
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(sql, params)
            row = await cur.fetchone()
            if row is None:
                return None
            return row_to_model(model, row)
        row = await self._conn.fetchrow(sql, *params)
        if row is None:
            return None
        return row_to_model(model, dict(row))

    async def _fetch_all(self, model: type[M], sql: str, params: list[Any]) -> list[M]:
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(sql, params)
            rows = await cur.fetchall()
            return [row_to_model(model, r) for r in rows]
        rows = await self._conn.fetch(sql, *params)
        return [row_to_model(model, dict(r)) for r in rows]


async def create_async_session(engine: AsyncEngine) -> AsyncSession:
    conn = await engine.connect()
    return AsyncSession(conn, dialect=engine.dialect)
