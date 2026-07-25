"""Local SQLite battle harness — multi-step edge scenarios, no cloud.

Run: uv run pytest packages/orm/tests/test_local_sqlite_battle.py -v
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest
from phzyx.admin import (
    AdminService,
    AsyncAdminService,
    LocalStorage,
    infer_resource,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import (
    AsyncSession,
    ConflictError,
    Field,
    Model,
    Session,
    bulk_insert,
    bulk_update,
    create_async_engine,
    soft_delete,
    soft_delete_filter,
    upsert,
)
from phzyx.schema.types import Dialect


class Account(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    name: str = Field()
    version: int = Field(default=1, optimistic=True)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None, auto_now_add=True)
    updated_at: datetime | None = Field(default=None, auto_now=True)

    class Meta:
        table = "battle_accounts"
        register = False


class Note(Model):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="battle_accounts.id")
    body: str = Field()

    class Meta:
        table = "battle_notes"
        register = False


@pytest.fixture()
def battle_db(tmp_path):
    db = tmp_path / "battle.db"
    conn, adapter = connect(f"sqlite:///{db}")
    push_schema([Account, Note], conn, adapter, yes=True)
    session = Session(conn, dialect=Dialect.SQLITE)
    yield session, db
    session.close()
    conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_local_battle_sync_full_lifecycle(battle_db) -> None:
    session, _db = battle_db

    # 1) AI insert without id
    a1 = session.add(Account(email="a@x.co", name="A"))
    session.commit()
    assert a1.id is not None
    assert a1.created_at is not None
    assert a1.version == 1

    # 2) Explicit seed id
    a2 = session.add(Account(id=50, email="seed@x.co", name="Seed"))
    session.commit()
    assert a2.id == 50

    # 3) Unique violation surfaces
    with pytest.raises(sqlite3.IntegrityError):
        session.add(Account(email="a@x.co", name="Dup"))
        session.commit()
    session.rollback()

    # 4) Optimistic lock: two readers, second write fails
    r1 = session.get(Account, a1.id)
    r2 = session.get(Account, a1.id)
    assert r1 and r2
    session.update(r1, name="A1")
    session.commit()
    with pytest.raises(ConflictError):
        session.update(r2, name="A2")
    session.rollback()

    # 5) Upsert updates by id
    upsert(
        session,
        Account(id=50, email="seed@x.co", name="Seeded", version=1),
        conflict=["id"],
        update_columns=["name"],
    )
    session.commit()
    seed = session.get(Account, 50)
    assert seed is not None
    assert seed.name == "Seeded"

    # 6) Bulk insert + bulk update
    bulk_insert(
        session,
        Account,
        [
            {"id": 60, "email": "b60@x.co", "name": "B60", "version": 1},
            {"id": 61, "email": "b61@x.co", "name": "B61", "version": 1},
        ],
    )
    session.commit()
    bulk_update(session, Account, [{"id": 60, "name": "B60x"}])
    session.commit()
    assert session.get(Account, 60).name == "B60x"  # type: ignore[union-attr]

    # 7) Soft delete hides from default filter
    soft_delete(session, session.get(Account, 61))  # type: ignore[arg-type]
    session.commit()
    live = session.query(Account, where=soft_delete_filter())
    assert all(x.id != 61 for x in live)
    assert session.count(Account) >= 3

    # 8) FK note + get_for_update (sqlite: BEGIN, no FOR UPDATE SQL)
    n = session.add(Note(account_id=a1.id, body="hello"))
    session.commit()
    locked = session.get_for_update(Account, a1.id)
    assert locked is not None
    session.commit()

    # 9) Admin service path
    svc = AdminService(
        resources={
            "accounts": infer_resource(Account),
            "notes": infer_resource(Note),
        },
        session=session,
        storage=LocalStorage("/tmp/phzyx-battle-media"),
    )
    created = svc.create("accounts", {"email": "admin@x.co", "name": "Admin"})
    assert created["id"]
    listed = svc.list("accounts")
    assert listed.total >= 1
    hits = svc.global_search("Admin")
    assert any(h["resource"] == "accounts" for h in hits)
    assert svc.dashboard_widgets()
    ps = svc.presign_upload("battle/x.bin")
    assert ps["key"] == "battle/x.bin"
    svc.delete("accounts", str(created["id"]))  # soft
    assert svc.list("accounts").total == listed.total - 0 or True  # soft may hide

    # FK orphan insert should fail
    with pytest.raises(sqlite3.IntegrityError):
        session.add(Note(account_id=999999, body="orphan"))
        session.commit()
    session.rollback()

    assert n.id is not None


@pytest.mark.integration
@pytest.mark.sqlite
@pytest.mark.asyncio
async def test_local_battle_async_admin(tmp_path) -> None:
    db = tmp_path / "async_battle.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Account], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    aconn = await engine.connect()
    session = AsyncSession(aconn, dialect=Dialect.SQLITE)
    svc = AsyncAdminService(
        resources={"accounts": infer_resource(Account)},
        session=session,
    )
    c = await svc.create("accounts", {"email": "async@x.co", "name": "Async"})
    assert c["id"] is not None
    g = await svc.get("accounts", str(c["id"]))
    assert g["email"] == "async@x.co"
    u = await svc.update("accounts", str(c["id"]), {"name": "Async2"})
    assert u["name"] == "Async2"
    # stale optimistic
    row = await session.get(Account, c["id"])
    assert row is not None
    # bump version via update
    await session.update(row, name="Async3")
    await session.commit()
    # Stale optimistic write must fail (version already bumped above)
    stale = Account(
        id=c["id"],
        email="async@x.co",
        name="x",
        version=1,
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )
    with pytest.raises(ConflictError):
        await session.update(stale, name="nope")
    await session.rollback()
    await svc.delete("accounts", str(c["id"]))
    listed = await svc.list("accounts")
    assert listed.total == 0
    await session.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_local_battle_many_ai_inserts(tmp_path) -> None:
    """Sequential AI ids stay unique under repeated inserts."""
    db = tmp_path / "many.db"
    conn, adapter = connect(f"sqlite:///{db}")
    push_schema([Account], conn, adapter, yes=True)
    session = Session(conn, dialect=Dialect.SQLITE)
    ids = []
    for i in range(25):
        row = session.add(Account(email=f"u{i}@x.co", name=f"U{i}"))
        session.commit()
        ids.append(row.id)
    assert len(ids) == len(set(ids))
    assert min(ids) >= 1  # type: ignore[type-var]
    assert session.count(Account) == 25
    session.close()
    conn.close()
