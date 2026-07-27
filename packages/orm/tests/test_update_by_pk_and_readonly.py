"""update_by_pk + read_only session guards (must not break optimistic update)."""

from __future__ import annotations

import pytest
from phzyx.engine import connect, push_schema
from phzyx.orm import (
    AsyncSession,
    Field,
    Model,
    OrmError,
    Session,
    create_async_engine,
    create_engine,
)
from phzyx.schema.types import Dialect


class Item(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    score: int = Field(default=0)

    class Meta:
        table = "items_ubpk"
        register = False


class Versioned(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    version: int = Field(default=0, optimistic=True)

    class Meta:
        table = "ver_ubpk"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_sync_update_by_pk_and_readonly(tmp_path) -> None:
    db = tmp_path / "ubpk.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item, Versioned], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_engine(f"sqlite:///{db}")
    with Session(engine.connect(), dialect=Dialect.SQLITE) as session:
        session.add(Item(id=1, name="a", score=1))
        session.commit()

        updated = session.update_by_pk(Item, 1, name="b", score=9)
        assert updated is not None
        assert updated.name == "b" and updated.score == 9
        session.commit()

        assert session.update_by_pk(Item, 999, name="nope") is None

        session.add(Versioned(id=1, title="t", version=0))
        session.commit()
        row = session.get(Versioned, 1)
        assert row is not None
        session.update(row, title="t2")
        session.commit()
        assert session.get(Versioned, 1).version == 1  # type: ignore[union-attr]

        with pytest.raises(ValueError, match="optimistic"):
            session.update_by_pk(Versioned, 1, title="x")

        # PK must never appear in SET — ignored even if caller passes id=
        session.update_by_pk(Item, 1, id=999, name="safe")
        session.commit()
        assert session.get(Item, 1) is not None
        assert session.get(Item, 999) is None
        assert session.get(Item, 1).name == "safe"  # type: ignore[union-attr]

    with Session(engine.connect(), dialect=Dialect.SQLITE, read_only=True) as ro:
        assert ro.get(Item, 1) is not None
        with pytest.raises(OrmError, match="read_only"):
            ro.add(Item(id=2, name="x", score=0))
        with pytest.raises(OrmError, match="read_only"):
            ro.update_by_pk(Item, 1, name="z")


@pytest.mark.integration
@pytest.mark.sqlite
@pytest.mark.asyncio
async def test_async_update_by_pk_keyset_count(tmp_path) -> None:
    db = tmp_path / "ubpk_async.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    conn_a = await engine.connect()
    try:
        session = AsyncSession(conn_a, dialect=Dialect.SQLITE)
        await session.add(Item(id=1, name="a", score=1))
        await session.add(Item(id=2, name="b", score=2))
        await session.add(Item(id=3, name="c", score=3))
        await session.commit()

        u = await session.update_by_pk(Item, 2, name="bb")
        assert u is not None and u.name == "bb"
        await session.commit()

        assert await session.count(Item) == 3
        page = await session.query_keyset(Item, limit=2)
        assert len(page.items) == 2
        assert page.has_more and page.next_cursor
        page2 = await session.query_keyset(Item, limit=2, cursor=page.next_cursor)
        assert len(page2.items) == 1

        ro = AsyncSession(conn_a, dialect=Dialect.SQLITE, read_only=True)
        with pytest.raises(OrmError, match="read_only"):
            await ro.delete(u)
    finally:
        await conn_a.close()
        await engine.dispose()
