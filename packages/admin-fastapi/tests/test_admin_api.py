"""FastAPI AdminBoard API tests (S4.3)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phzyx.admin.fastapi import AdminBoard  # type: ignore[import-not-found]
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Item(Model):
    id: int = Field(primary_key=True)
    name: str = Field()

    class Meta:
        table = "items"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_adminboard_mount_and_resources(tmp_path) -> None:
    db = tmp_path / "api.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
    finally:
        conn.close()

    def session_factory() -> Session:
        c, _ = connect(f"sqlite:///{db}")
        return Session(c, dialect=Dialect.SQLITE)

    app = FastAPI()
    AdminBoard(app, models=[Item], session_factory=session_factory, theme="magical-white")
    client = TestClient(app)

    r = client.get("/admin/api/v1/resources")
    assert r.status_code == 200
    assert any(x["name"] == "items" for x in r.json())

    meta = client.get("/admin/api/v1/meta")
    assert meta.json()["theme"] == "magical-white"
    assert "stellar-dark" in meta.json()["themes"]

    created = client.post("/admin/api/v1/resources/items/records", json={"id": 1, "name": "widget"})
    assert created.status_code == 200
    assert created.json()["name"] == "widget"

    listed = client.get("/admin/api/v1/resources/items/records")
    assert listed.json()["total"] == 1

    exp = client.get("/admin/api/v1/resources/items/export?fmt=csv")
    assert exp.status_code == 200
    assert "widget" in exp.text

    open_meta = client.get("/admin/api/v1/files/open-meta", params={"key": "docs/a.pdf"})
    assert open_meta.json()["mode"] == "pdf"
