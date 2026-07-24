"""Sync + async session CRUD on SQLite (M3 gate)."""

from __future__ import annotations

import pytest
from phzyx.engine import connect, push_schema
from phzyx.orm import (
    AsyncSession,
    Field,
    Model,
    Session,
    create_async_engine,
    create_engine,
    desc,
    eq,
    gte,
)
from phzyx.schema.types import Dialect


class Item(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    score: int = Field(default=0)

    class Meta:
        table = "items"
        register = False


class Membership(Model):
    org_id: int = Field(primary_key=True)
    user_id: int = Field(primary_key=True)
    role: str = Field(default="member")

    class Meta:
        table = "memberships"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_sync_crud_filter_order_limit(tmp_path) -> None:
    db = tmp_path / "orm.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_engine(f"sqlite:///{db}")
    with Session(engine.connect(), dialect=Dialect.SQLITE) as session:
        session.add(Item(id=1, name="a", score=10))
        session.add(Item(id=2, name="b", score=20))
        session.add(Item(id=3, name="c", score=30))
        session.commit()

        got = session.get(Item, 2)
        assert got is not None and got.name == "b"

        rows = session.query(
            Item,
            where=[gte("score", 20)],
            order_by=[desc("score")],
            limit=2,
        )
        assert [r.id for r in rows] == [3, 2]

        session.update(got, name="bb")
        session.commit()
        assert session.get(Item, 2).name == "bb"  # type: ignore[union-attr]

        session.delete(session.get(Item, 1))  # type: ignore[arg-type]
        session.commit()
        assert session.get(Item, 1) is None


@pytest.mark.integration
@pytest.mark.sqlite
def test_sync_transaction_rollback(tmp_path) -> None:
    db = tmp_path / "tx.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_engine(f"sqlite:///{db}")
    session = Session(engine.connect(), dialect=Dialect.SQLITE)
    try:
        session.begin()
        session.add(Item(id=1, name="x", score=1))
        session.rollback()
        assert session.get(Item, 1) is None
    finally:
        session.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_composite_key_get(tmp_path) -> None:
    db = tmp_path / "ck.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Membership], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_engine(f"sqlite:///{db}")
    with Session(engine.connect(), dialect=Dialect.SQLITE) as session:
        session.add(Membership(org_id=1, user_id=2, role="admin"))
        session.commit()
        row = session.get(Membership, {"org_id": 1, "user_id": 2})
        assert row is not None and row.role == "admin"
        row2 = session.get(Membership, (1, 2))
        assert row2 is not None


@pytest.mark.integration
@pytest.mark.sqlite
@pytest.mark.asyncio
async def test_async_session_crud(tmp_path) -> None:
    db = tmp_path / "async.db"
    # create schema with sync push first
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    conn = await engine.connect()
    session = AsyncSession(conn, dialect=Dialect.SQLITE)
    try:
        await session.add(Item(id=1, name="async", score=5))
        await session.commit()
        got = await session.get(Item, 1)
        assert got is not None and got.name == "async"
        rows = await session.query(Item, where=[eq("name", "async")])
        assert len(rows) == 1
    finally:
        await session.close()
