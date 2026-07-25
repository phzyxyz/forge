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


class Person(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    name: str = Field()

    class Meta:
        table = "people_api"
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


@pytest.mark.integration
@pytest.mark.sqlite
def test_search_widgets_i18n_and_unique(tmp_path) -> None:
    db = tmp_path / "swapi.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Person], conn, adapter, yes=True)
    finally:
        conn.close()

    def session_factory() -> Session:
        c, _ = connect(f"sqlite:///{db}")
        return Session(c, dialect=Dialect.SQLITE)

    app = FastAPI()
    AdminBoard(app, models=[Person], session_factory=session_factory)
    client = TestClient(app)

    meta = client.get("/admin/api/v1/meta")
    assert meta.json()["features"]["global_search"] is True

    res_name = "people_api"  # table Meta.name used by infer_resource
    created = client.post(
        f"/admin/api/v1/resources/{res_name}/records",
        json={"email": "ada@x.co", "name": "Ada"},
    )
    assert created.status_code == 200

    # unique email
    dup = client.post(
        f"/admin/api/v1/resources/{res_name}/records",
        json={"email": "ada@x.co", "name": "Other"},
    )
    assert dup.status_code == 422
    body = dup.json()
    assert body["error"]["code"] == "validation_error"
    assert "email" in (body["error"]["details"].get("fields") or {})

    search = client.get("/admin/api/v1/search", params={"q": "Ada"})
    assert search.status_code == 200
    items = search.json()["items"]
    assert any(h["resource"] == res_name for h in items)

    widgets = client.get("/admin/api/v1/widgets")
    assert widgets.status_code == 200
    assert any(w["resource"] == res_name for w in widgets.json()["items"])

    i18n = client.get("/admin/api/v1/i18n")
    assert i18n.status_code == 200
    assert i18n.json()["catalog"]["action.save"] == "Save"
