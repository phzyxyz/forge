"""Explicit asyncpg pool lifecycle for long-lived applications such as FastAPI."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from phzyx.orm.session_async import AsyncSession
from phzyx.schema.types import Dialect


class AsyncPostgresPool:
    """Own a bounded pool; borrowed sessions never close a physical connection.

    Open during application startup and close during shutdown. Native asyncpg
    codecs are retained except optional JSON/JSONB decoding to Python values.
    ``init`` can install additional codecs on each physical connection.
    """

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        acquire_timeout: float = 5,
        close_timeout: float = 10,
        json_codecs: bool = True,
        init: Callable[[Any], Awaitable[None]] | None = None,
        **connect_options: Any,
    ) -> None:
        if not 0 <= min_size <= max_size or max_size < 1:
            raise ValueError("pool sizes must satisfy 0 <= min_size <= max_size and max_size >= 1")
        if acquire_timeout <= 0 or close_timeout <= 0:
            raise ValueError("pool timeouts must be positive")
        self.dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        self.min_size = min_size
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self.close_timeout = close_timeout
        self.json_codecs = json_codecs
        self.init = init
        self.connect_options = {"timeout": 10, "command_timeout": 30, **connect_options}
        self._pool: Any = None
        self._lifecycle_lock = asyncio.Lock()

    async def _initialize(self, conn: Any) -> None:
        if self.json_codecs:
            for name in ("json", "jsonb"):
                await conn.set_type_codec(
                    name,
                    schema="pg_catalog",
                    encoder=json.dumps,
                    decoder=json.loads,
                    format="text",
                )
        if self.init is not None:
            await self.init(conn)

    async def open(self) -> None:
        """Initialize once; callers may retry after a failed startup."""
        async with self._lifecycle_lock:
            if self._pool is not None:
                return
            try:
                import asyncpg
            except ImportError as exc:
                raise ImportError("install asyncpg: uv add 'phzyx-forge[postgres]'") from exc

            pool = asyncpg.create_pool(
                self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
                init=self._initialize,
                **self.connect_options,
            )
            try:
                await pool
            except BaseException:
                pool.terminate()
                raise
            self._pool = pool

    async def close(self) -> None:
        """Drain borrowed connections, then terminate if the shutdown deadline expires."""
        async with self._lifecycle_lock:
            pool = self._pool
            if pool is None:
                return
            self._pool = None
            try:
                await asyncio.wait_for(pool.close(), timeout=self.close_timeout)
            except BaseException:
                pool.terminate()
                raise

    async def checkout(self) -> Any:
        """Borrow one connection. The connection's ``_phzyx_release`` returns it.

        Opens the pool on first use. Callers that use :meth:`session` or
        :meth:`connection` should keep using those context managers.
        """
        await self.open()
        pool = self._pool
        if pool is None:
            raise RuntimeError("open the PostgreSQL pool before acquiring a connection")
        conn = await pool.acquire(timeout=self.acquire_timeout)

        async def _release() -> None:
            try:
                await pool.release(conn)
            except Exception:
                terminate = getattr(conn, "terminate", None)
                if terminate is not None:
                    terminate()

        conn._phzyx_release = _release
        return conn

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Any, None]:
        """Borrow a raw asyncpg connection; release resets state even on cancellation."""
        await self.open()
        pool = self._pool
        if pool is None:
            raise RuntimeError("open the PostgreSQL pool before acquiring a connection")
        async with pool.acquire(timeout=self.acquire_timeout) as conn:
            yield conn

    @asynccontextmanager
    async def session(self, *, read_only: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """Borrow one connection for an automatically committed/rolled-back transaction."""
        async with (
            self.connection() as conn,
            AsyncSession(
                conn,
                dialect=Dialect.POSTGRES,
                read_only=read_only,
                owns_connection=False,
                manage_transaction=True,
            ) as session,
        ):
            yield session

    async def __aenter__(self) -> AsyncPostgresPool:
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
