"""Async engine / connection factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from phzyx.schema.types import Dialect


@dataclass
class AsyncEngine:
    dialect: Dialect
    url: str
    _factory: Any
    _pool: Any = None

    async def connect(self) -> Any:
        """Open one connection.

        PostgreSQL engines borrow from a pool. The object returned here
        carries ``_phzyx_release``; the asyncpg proxy itself rejects extra
        attributes. :meth:`dispose` closes that pool. SQLite still opens a
        single driver connection.
        """
        if self._pool is not None:
            return await self._pool.checkout()
        return await self._factory()

    async def dispose(self) -> None:
        """Close the PostgreSQL pool. No-op for SQLite and an unopened pool."""
        if self._pool is not None:
            await self._pool.close()


def create_async_engine(url: str) -> AsyncEngine:
    """Create an async engine for ``sqlite+aiosqlite://`` or ``postgresql+asyncpg://``."""
    raw = url.strip()
    if raw.startswith("sqlite+aiosqlite:"):
        path = _sqlite_path(raw.replace("sqlite+aiosqlite:", "sqlite:", 1))
        return AsyncEngine(dialect=Dialect.SQLITE, url=raw, _factory=_aiosqlite_factory(path))
    if raw.startswith("sqlite:"):
        # allow sqlite:// for async via aiosqlite
        path = _sqlite_path(raw)
        return AsyncEngine(
            dialect=Dialect.SQLITE,
            url=raw,
            _factory=_aiosqlite_factory(path),
        )
    if raw.startswith(("postgresql+asyncpg://", "postgres+asyncpg://")):
        dsn = "postgresql://" + raw.split("://", 1)[1]
        return _postgres_engine(raw, dsn)
    if raw.startswith(("postgresql://", "postgres://")):
        # prefer asyncpg when create_async_engine is used
        dsn = raw.replace("postgres://", "postgresql://", 1)
        return _postgres_engine(raw, dsn)
    raise ValueError("unsupported async URL; use sqlite+aiosqlite:///… or postgresql+asyncpg://…")


def _sqlite_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    if parsed.netloc == ":memory:" or path in {":memory:", "/:memory:"}:
        return ":memory:"
    if url.startswith("sqlite:////"):
        return path
    return path[1:] if path.startswith("/") else path or ":memory:"


def _aiosqlite_factory(path: str):
    async def _connect():
        try:
            import aiosqlite
        except ImportError as exc:  # pragma: no cover
            raise ImportError("install aiosqlite: uv add 'phzyx-orm[sqlite]'") from exc
        db = await aiosqlite.connect(path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        return db

    return _connect


def _postgres_engine(url: str, dsn: str) -> AsyncEngine:
    from phzyx.orm.pool_async import AsyncPostgresPool

    return AsyncEngine(
        dialect=Dialect.POSTGRES,
        url=url,
        _factory=None,
        _pool=AsyncPostgresPool(dsn),
    )
