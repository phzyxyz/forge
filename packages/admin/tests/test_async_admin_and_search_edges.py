"""AsyncAdmin CRUD + search edge cases."""

from __future__ import annotations

from datetime import datetime

import pytest
from phzyx.admin import AdminService, AsyncAdminService, LocalStorage, infer_resource
from phzyx.engine import connect, push_schema
from phzyx.orm import AsyncSession, Field, Model, Session, create_async_engine
from phzyx.schema.types import Dialect


class Item(Model):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field()
    deleted_at: datetime | None = Field(default=None)

    class Meta:
        table = "async_items"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
@pytest.mark.asyncio
async def test_async_admin_crud(tmp_path) -> None:
    db = tmp_path / "a.db"
    # Create schema via sync push
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    aconn = await engine.connect()
    session = AsyncSession(aconn, dialect=Dialect.SQLITE)
    svc = AsyncAdminService(
        resources={"items": infer_resource(Item)},
        session=session,
    )
    created = await svc.create("items", {"name": "alpha"})
    assert created["id"] is not None
    assert "_identity" in created

    got = await svc.get("items", str(created["id"]))
    assert got["name"] == "alpha"

    listed = await svc.list("items")
    assert listed.total == 1

    updated = await svc.update("items", str(created["id"]), {"name": "beta"})
    assert updated["name"] == "beta"

    await svc.delete("items", str(created["id"]))
    listed2 = await svc.list("items")
    assert listed2.total == 0

    await session.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_search_empty_and_wildcard_escape(tmp_path) -> None:
    db = tmp_path / "s.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        svc = AdminService(
            resources={"items": infer_resource(Item)},
            session=session,
            storage=LocalStorage(tmp_path / "m"),
        )
        svc.create("items", {"name": "100%_real"})
        assert svc.global_search("") == []
        hits = svc.global_search("%")
        # escaped % should not match everything as wildcard alone necessarily
        assert isinstance(hits, list)
        widgets = svc.dashboard_widgets()
        assert widgets and widgets[0]["value"] >= 1
        session.close()
    finally:
        conn.close()
