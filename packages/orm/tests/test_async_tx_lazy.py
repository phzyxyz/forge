"""PostgreSQL sessions begin a transaction even without ``async with``."""

from __future__ import annotations

import pytest
from phzyx.orm import AsyncSession, create_async_engine
from phzyx.schema.types import Dialect


class _Tx:
    def __init__(self) -> None:
        self.started = False
        self.done: str | None = None

    async def start(self) -> None:
        self.started = True

    async def commit(self) -> None:
        self.done = "commit"

    async def rollback(self) -> None:
        self.done = "rollback"


class _Conn:
    def __init__(self) -> None:
        self.tx: _Tx | None = None
        self.statements: list[str] = []

    def transaction(self, readonly: bool = False) -> _Tx:
        self.tx = _Tx()
        return self.tx

    async def execute(self, sql: str, *params: object) -> str:
        self.statements.append(sql)
        return "SELECT 1"


@pytest.mark.unit
async def test_commit_without_context_manager_reaches_postgres() -> None:
    conn = _Conn()
    session = AsyncSession(conn, dialect=Dialect.POSTGRES, manage_transaction=True)
    await session.execute_native("INSERT INTO t VALUES (1)")
    assert conn.tx is not None and conn.tx.started
    await session.commit()
    assert conn.tx.done == "commit"


@pytest.mark.unit
async def test_rollback_without_context_manager_reaches_postgres() -> None:
    conn = _Conn()
    session = AsyncSession(conn, dialect=Dialect.POSTGRES)
    await session.execute_native("INSERT INTO t VALUES (1)")
    await session.rollback()
    assert conn.tx is not None
    assert conn.tx.done == "rollback"


@pytest.mark.unit
async def test_postgres_engine_owns_a_pool_and_dispose_is_safe_before_open() -> None:
    engine = create_async_engine("postgresql+asyncpg://phzyx:phzyx@127.0.0.1/none")
    assert engine._pool is not None
    await engine.dispose()
    await engine.dispose()
