"""Opt-in PostgreSQL tests; PHZYX_TEST_DATABASE_URL must target a disposable DB."""

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from phzyx.orm import AsyncPostgresPool, AsyncSession
from phzyx.schema.types import Dialect

DSN = os.environ.get("PHZYX_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not DSN, reason="explicit test DSN required"),
]


@pytest_asyncio.fixture
async def pool():
    async with AsyncPostgresPool(DSN, max_size=1, statement_cache_size=0) as pool:
        async with pool.session() as session:
            await session.execute_native("CREATE TABLE phzyx_tx_probe (id int PRIMARY KEY)")
        try:
            yield pool
        finally:
            async with pool.session() as session:
                await session.execute_native("DROP TABLE phzyx_tx_probe")


async def test_session_commits_and_rolls_back(pool):
    async with pool.session() as session:
        await session.execute_native("INSERT INTO phzyx_tx_probe VALUES ($1)", 1)
    with pytest.raises(RuntimeError):
        async with pool.session() as session:
            await session.execute_native("INSERT INTO phzyx_tx_probe VALUES ($1)", 2)
            raise RuntimeError("abort")
    async with pool.session() as session:
        assert await session.fetch_native("SELECT * FROM phzyx_tx_probe") == [{"id": 1}]


async def test_nested_savepoint_rollback_keeps_outer_work(pool):
    async with pool.session() as session:
        await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (1)")
        with pytest.raises(RuntimeError):
            async with session.savepoint():
                await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (2)")
                async with session.savepoint():
                    await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (3)")
                raise RuntimeError("undo inner")
        await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (4)")
    async with pool.session() as session:
        assert await session.fetch_native("SELECT * FROM phzyx_tx_probe ORDER BY id") == [
            {"id": 1},
            {"id": 4},
        ]


async def test_borrowed_session_cannot_commit_or_close_callers_transaction(pool):
    async with pool.connection() as conn:
        outer = conn.transaction()
        await outer.start()
        async with AsyncSession(conn, dialect=Dialect.POSTGRES, owns_connection=False) as session:
            await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (1)")
            await session.commit()
            await session.rollback()
        assert conn.is_in_transaction()
        assert not conn.is_closed()
        await outer.rollback()
        assert await conn.fetchval("SELECT count(*) FROM phzyx_tx_probe") == 0


async def test_managed_session_inside_external_transaction_owns_only_savepoint(pool):
    async with pool.connection() as conn:
        outer = conn.transaction()
        await outer.start()
        async with AsyncSession(
            conn,
            dialect=Dialect.POSTGRES,
            owns_connection=False,
            manage_transaction=True,
        ) as session:
            await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (1)")
        assert conn.is_in_transaction()
        await outer.rollback()
        assert await conn.fetchval("SELECT count(*) FROM phzyx_tx_probe") == 0


async def test_cancelled_request_rolls_back_and_releases_pool_slot(pool):
    ready = asyncio.Event()

    async def request():
        async with pool.session() as session:
            await session.execute_native("INSERT INTO phzyx_tx_probe VALUES (1)")
            ready.set()
            await session.execute_native("SELECT pg_sleep(30)")

    task = asyncio.create_task(request())
    await asyncio.wait_for(ready.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with pool.session() as session:
        assert await session.fetch_native("SELECT * FROM phzyx_tx_probe") == []


async def test_pool_reuses_connection_and_resets_local_context(pool):
    async with pool.session() as session:
        first = await session.fetch_native("SELECT pg_backend_pid() AS pid")
        await session.execute_native("SELECT set_config('app.tenant_id', $1, true)", "42")
    async with pool.session() as session:
        assert await session.fetch_native("SELECT pg_backend_pid() AS pid") == first
        rows = await session.fetch_native("SELECT current_setting('app.tenant_id', true) AS tenant")
        assert rows[0]["tenant"] in (None, "")


async def test_native_sql_preserves_literals_and_postgres_types(pool):
    identity = uuid4()
    now = datetime.now(UTC)
    async with pool.session() as session:
        rows = await session.fetch_native(
            "SELECT $1::uuid AS id, $2::jsonb AS payload, $3::int[] AS items, "
            "$4::numeric AS amount, $5::timestamptz AS at, '%s'::text AS literal",
            identity,
            {"text": "%s and $1", "ok": True},
            [1, 2],
            Decimal("1.20"),
            now,
        )
        assert rows == [
            {
                "id": identity,
                "payload": {"text": "%s and $1", "ok": True},
                "items": [1, 2],
                "amount": Decimal("1.20"),
                "at": now,
                "literal": "%s",
            }
        ]


async def test_read_only_transaction_rejects_cte_write(pool):
    import asyncpg

    with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
        async with pool.session(read_only=True) as session:
            await session.fetch_native(
                "WITH written AS (INSERT INTO phzyx_tx_probe VALUES (1) RETURNING id) "
                "SELECT * FROM written"
            )


async def test_pool_requires_open_and_reopens_after_close():
    pool = AsyncPostgresPool(DSN, max_size=1)
    with pytest.raises(RuntimeError, match="open"):
        async with pool.connection():
            pass
    for _ in range(2):
        await pool.open()
        await pool.open()
        async with pool.session() as session:
            assert await session.fetch_native("SELECT 1 AS value") == [{"value": 1}]
        await pool.close()
        await pool.close()


async def test_failed_commit_preserves_error_and_releases_pool(pool):
    import asyncpg

    with pytest.raises(asyncpg.UniqueViolationError):
        async with pool.session() as session:
            await session.execute_native(
                "CREATE TEMP TABLE deferred_probe (id int UNIQUE DEFERRABLE INITIALLY DEFERRED)"
            )
            await session.execute_native("INSERT INTO deferred_probe VALUES (1), (1)")
    async with pool.session() as session:
        assert await session.fetch_native("SELECT 1 AS ok") == [{"ok": 1}]


async def test_closing_unfinished_owned_session_rolls_back():
    import asyncpg

    conn = await asyncpg.connect(DSN)
    session = AsyncSession(conn, dialect=Dialect.POSTGRES)
    await session.begin()
    await session.execute_native("CREATE TABLE unfinished_probe (id int)")
    await session.close()
    assert conn.is_closed()
    observer = await asyncpg.connect(DSN)
    try:
        assert await observer.fetchval("SELECT to_regclass('unfinished_probe')") is None
    finally:
        await observer.close()
