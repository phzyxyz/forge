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

    async def connect(self) -> Any:
        return await self._factory()

    async def dispose(self) -> None:
        return None


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
        dsn = raw.split("://", 1)[1]
        dsn = "postgresql://" + dsn
        return AsyncEngine(dialect=Dialect.POSTGRES, url=raw, _factory=_asyncpg_factory(dsn))
    if raw.startswith(("postgresql://", "postgres://")):
        # prefer asyncpg when create_async_engine is used
        dsn = raw.replace("postgres://", "postgresql://", 1)
        return AsyncEngine(dialect=Dialect.POSTGRES, url=raw, _factory=_asyncpg_factory(dsn))
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


def _asyncpg_factory(dsn: str):
    async def _connect():
        try:
            import asyncpg  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("install asyncpg: uv add 'phzyx-orm[postgres]'") from exc
        return await asyncpg.connect(dsn)

    return _connect
