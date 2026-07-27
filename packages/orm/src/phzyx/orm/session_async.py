"""AsyncSession — async CRUD over Phzyx models."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from types import TracebackType
from typing import Any, TypeVar

from phzyx.orm.engine_async import AsyncEngine
from phzyx.orm.errors import ConflictError, OrmError
from phzyx.orm.expr import Filter, OrderBy, eq
from phzyx.orm.hydrate import model_to_row, row_to_model
from phzyx.orm.insert_prep import prepare_insert_values, prepare_update_values
from phzyx.orm.keyset import (
    KeysetPage,
    cursor_from_row,
    default_order_columns,
    order_from_columns,
)
from phzyx.orm.pk_util import primary_key_map, reject_optimistic_for_by_pk
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


@lru_cache(maxsize=2048)
def _asyncpg_sql(sql: str) -> str:
    """Convert ``%s`` placeholders (psycopg style) to asyncpg ``$1, $2, …``.

    Cached: SQL builders emit stable statement strings for common shapes.
    """
    if "%s" not in sql:
        return sql
    parts = sql.split("%s")
    out: list[str] = []
    for i, part in enumerate(parts[:-1]):
        out.append(part)
        out.append(f"${i + 1}")
    out.append(parts[-1])
    return "".join(out)


class AsyncSession:
    """Async unit-of-work for CRUD + queries.

    Pass ``read_only=True`` to reject writes (get/query/count still work).
    """

    def __init__(self, conn: Any, *, dialect: Dialect, read_only: bool = False) -> None:
        self._conn = conn
        self.dialect = dialect
        self.read_only = read_only
        self._in_tx = False

    def _ensure_writable(self) -> None:
        if self.read_only:
            raise OrmError("AsyncSession is read_only; writes are disabled")

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
        if self.read_only:
            self._in_tx = False
            return
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
        self._ensure_writable()
        data, omitted_pk = prepare_insert_values(instance)
        use_returning = self.dialect is Dialect.POSTGRES
        frag = build_insert(
            type(instance),
            data,
            dialect=self.dialect,
            returning=use_returning,
        )
        if self.dialect is Dialect.SQLITE:
            await self._conn.execute(frag.sql, adapt_sqlite_params(frag.params))
            base = {**data}
            if omitted_pk is not None:
                cur = await self._conn.execute("SELECT last_insert_rowid()")
                row = await cur.fetchone()
                new_id = row[0] if row else None
                if new_id is None:
                    raise RuntimeError(
                        f"INSERT succeeded but lastrowid missing for {type(instance).__name__}"
                    )
                base[omitted_pk] = new_id
            return type(instance).model_validate(base)

        if use_returning:
            row = await self._conn.fetchrow(_asyncpg_sql(frag.sql), *frag.params)
            if row is not None:
                return row_to_model(type(instance), dict(row))
            if omitted_pk is not None:
                raise RuntimeError(
                    f"INSERT RETURNING produced no row for {type(instance).__name__}"
                )
            return type(instance).model_validate(data)

        await self._conn.execute(_asyncpg_sql(frag.sql), *frag.params)
        base = {**data}
        if omitted_pk is not None:
            new_id = getattr(self._conn, "lastrowid", None)
            if not new_id:
                raise RuntimeError(
                    f"INSERT succeeded but lastrowid missing for {type(instance).__name__}"
                )
            base[omitted_pk] = new_id
        return type(instance).model_validate(base)

    async def get(self, model: type[M], key: Any) -> M | None:
        frag = build_select_by_pk(model, key, dialect=self.dialect)
        return await self._fetch_one(model, frag.sql, frag.params)

    async def delete(self, instance: Model) -> None:
        self._ensure_writable()
        info = get_table_info(type(instance))
        data = model_to_row(instance)
        where = [eq(col, data[col]) for col in info.primary_key]
        frag = build_delete(type(instance), where, dialect=self.dialect)
        await self.execute(frag.sql, frag.params)

    async def update(self, instance: Model, **values: Any) -> Model:
        self._ensure_writable()
        info = get_table_info(type(instance))
        data = model_to_row(instance)
        for col in info.primary_key:
            if data.get(col) is None:
                raise ValueError(
                    f"cannot update {type(instance).__name__}: primary key {col!r} is unset"
                )
        try:
            values = prepare_update_values(instance, values)
        except ValueError:
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
        use_returning = self.dialect is Dialect.POSTGRES
        frag = build_update(
            type(instance),
            values,
            where,
            dialect=self.dialect,
            returning=use_returning,
        )
        if use_returning:
            row = await self._conn.fetchrow(_asyncpg_sql(frag.sql), *frag.params)
            if row is None:
                if has_opt:
                    raise ConflictError("optimistic lock failed: row was updated elsewhere")
                # Non-optimistic miss (deleted concurrent) — keep merge fallback shape.
                return type(instance).model_validate({**data, **values})
            return row_to_model(type(instance), dict(row))
        n = await self.execute(frag.sql, frag.params)
        if has_opt and n == 0:
            raise ConflictError("optimistic lock failed: row was updated elsewhere")
        if has_opt and n < 0:
            # Driver reported unknown rowcount — re-read and compare versions.
            await self._verify_optimistic(type(instance), data, info)
        return type(instance).model_validate({**data, **values})

    async def update_by_pk(self, model: type[M], key: Any, **values: Any) -> M | None:
        """UPDATE by primary key without a prior SELECT.

        Returns the updated row, or ``None`` if no row matched.
        Models with optimistic columns must use :meth:`update` instead.
        """
        self._ensure_writable()
        reject_optimistic_for_by_pk(model)
        pk_map = primary_key_map(model, key)
        if not values:
            return await self.get(model, key)
        shell = model.model_construct(**pk_map)
        try:
            prepared = prepare_update_values(shell, values)
        except ValueError:
            if not values:
                return await self.get(model, key)
            raise
        where = [eq(col, pk_map[col]) for col in pk_map]
        use_returning = self.dialect is Dialect.POSTGRES
        frag = build_update(
            model,
            prepared,
            where,
            dialect=self.dialect,
            returning=use_returning,
        )
        if use_returning:
            row = await self._conn.fetchrow(_asyncpg_sql(frag.sql), *frag.params)
            if row is None:
                return None
            return row_to_model(model, dict(row))
        n = await self.execute(frag.sql, frag.params)
        if n == 0:
            return None
        return await self.get(model, key)

    async def count(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
    ) -> int:
        """Efficient COUNT(*) — does not load rows."""
        frag = build_count(model, where=where, dialect=self.dialect)
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(frag.sql, adapt_sqlite_params(frag.params))
            row = await cur.fetchone()
            return int(row[0]) if row else 0
        val = await self._conn.fetchval(_asyncpg_sql(frag.sql), *frag.params)
        return int(val or 0)

    async def query(
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
        return await self._fetch_all(model, frag.sql, frag.params)

    async def query_keyset(
        self,
        model: type[M],
        *,
        where: Sequence[Filter] = (),
        order_by: Sequence[OrderBy] | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> KeysetPage:
        """Fetch a keyset page with next_cursor (limit+1 probe)."""
        order = list(order_by) if order_by else order_from_columns(default_order_columns(model))
        cols = [o.column for o in order]
        rows = await self.query(
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
        return KeysetPage(
            items=page_rows,
            next_cursor=next_c,
            prev_cursor=cursor,
            has_more=has_more,
        )

    async def get_for_update(
        self,
        model: type[M],
        key: Any,
        *,
        nowait: bool = False,
        skip_locked: bool = False,
    ) -> M | None:
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
        rows = await self.query(model, where=where, limit=1, for_update=mode)
        return rows[0] if rows else None

    async def execute(self, sql: str, params: list[Any] | None = None) -> int:
        """Execute a parameterized statement; return rowcount or ``-1`` if unknown."""
        # Allow SELECT via execute on read-only; block obvious writes.
        if self.read_only:
            head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
            if head not in {"SELECT", "WITH", "EXPLAIN", "SHOW", "PRAGMA"}:
                self._ensure_writable()
        bind = list(params or [])
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(sql, adapt_sqlite_params(bind))
            rc = getattr(cur, "rowcount", None)
            return -1 if rc is None else int(rc)
        result = await self._conn.execute(_asyncpg_sql(sql), *bind)
        # asyncpg StatusMessage has .get_raw_status or we re-check; often no rowcount.
        rc = getattr(result, "rowcount", None)
        if rc is None and hasattr(result, "split"):
            # e.g. "UPDATE 1"
            try:
                parts = str(result).split()
                rc = int(parts[-1]) if parts[-1].isdigit() else -1
            except Exception:
                rc = -1
        return -1 if rc is None else int(rc)

    async def _verify_optimistic(self, model: type[Model], data: dict[str, Any], info: Any) -> None:
        """When rowcount is unreliable, re-read and compare optimistic columns."""
        key = (
            data[info.primary_key[0]]
            if len(info.primary_key) == 1
            else {c: data[c] for c in info.primary_key}
        )
        current = await self.get(model, key)
        if current is None:
            raise ConflictError("optimistic lock failed: row missing")
        for col_name, meta in info.columns.items():
            if meta.optimistic and getattr(current, col_name, None) != data.get(col_name):
                raise ConflictError("optimistic lock failed: row was updated elsewhere")

    async def _fetch_one(self, model: type[M], sql: str, params: list[Any]) -> M | None:
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(sql, adapt_sqlite_params(params))
            row = await cur.fetchone()
            if row is None:
                return None
            return row_to_model(model, row)
        row = await self._conn.fetchrow(_asyncpg_sql(sql), *params)
        if row is None:
            return None
        return row_to_model(model, dict(row))

    async def _fetch_all(self, model: type[M], sql: str, params: list[Any]) -> list[M]:
        if self.dialect is Dialect.SQLITE:
            cur = await self._conn.execute(sql, adapt_sqlite_params(params))
            rows = await cur.fetchall()
            return [row_to_model(model, r) for r in rows]
        rows = await self._conn.fetch(_asyncpg_sql(sql), *params)
        return [row_to_model(model, dict(r)) for r in rows]


async def create_async_session(engine: AsyncEngine) -> AsyncSession:
    conn = await engine.connect()
    return AsyncSession(conn, dialect=engine.dialect)
