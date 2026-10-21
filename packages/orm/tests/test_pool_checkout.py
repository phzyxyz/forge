"""checkout must not write attributes onto asyncpg's pool proxy."""

from __future__ import annotations

import pytest
from phzyx.orm.pool_async import AsyncPostgresPool


class _Proxy:
    """Same constraint as asyncpg's PoolConnectionProxy: no instance dict."""

    __slots__ = ()

    async def execute(self, sql: str) -> str:
        return sql


class _OneSlotPool:
    def __init__(self) -> None:
        self.proxy = _Proxy()
        self.checked_out = False

    async def acquire(self, timeout: float | None = None) -> _Proxy:
        if self.checked_out:
            raise TimeoutError("pool exhausted")
        self.checked_out = True
        return self.proxy

    async def release(self, conn: _Proxy) -> None:
        if conn is not self.proxy:
            raise RuntimeError("released a connection this pool did not lend")
        self.checked_out = False


@pytest.mark.unit
async def test_checkout_release_lets_a_one_slot_pool_be_borrowed_again() -> None:
    holder = AsyncPostgresPool(
        "postgresql://phzyx:phzyx@127.0.0.1/none",
        min_size=1,
        max_size=1,
    )
    holder._pool = _OneSlotPool()

    borrowed = await holder.checkout()
    assert callable(borrowed._phzyx_release)
    assert await borrowed.execute("select 1") == "select 1"
    await borrowed._phzyx_release()

    again = await holder.checkout()
    assert callable(again._phzyx_release)
