"""Diamond D7 — audit trail + forbidden authz."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phzyx.admin.auth import AllowAll, DenyWrites
from phzyx.admin.fastapi import AdminBoard
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Item(Model):
    id: int = Field(primary_key=True)
    title: str = Field()

    class Meta:
        table = "t_d7_items"
        register = False


@pytest.fixture
def app_client(tmp_path):
    db = tmp_path / "d7.db"
    url = f"sqlite:///{db}"
    conn, ad = connect(url)
    push_schema([Item], conn, ad, yes=True)
    s = Session(conn, dialect=Dialect.SQLITE)
    s.add(Item(id=1, title="one"))
    s.commit()

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    application = FastAPI()
    AdminBoard(
        application,
        models=[Item],
        session_factory=factory,
        authz=AllowAll(),
        database_url=url,
    )
    return TestClient(application), application


@pytest.mark.unit
def test_audit_records_and_lists(app_client) -> None:
    client, app = app_client
    # create triggers audit
    r = client.post(
        "/admin/api/v1/resources/t_d7_items/records",
        json={"id": 2, "title": "two"},
    )
    assert r.status_code == 200
    audit = client.get("/admin/api/v1/audit")
    assert audit.status_code == 200
    body = audit.json()
    assert body["total"] >= 1
    actions = [e["action"] for e in body["items"]]
    assert "create" in actions


@pytest.mark.unit
def test_forbidden_returns_clear_403(tmp_path) -> None:
    db = tmp_path / "d7b.db"
    url = f"sqlite:///{db}"
    conn, ad = connect(url)
    push_schema([Item], conn, ad, yes=True)
    conn.close()

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    application = FastAPI()
    AdminBoard(
        application,
        models=[Item],
        session_factory=factory,
        authz=DenyWrites(),
        database_url=url,
    )
    client = TestClient(application)
    r = client.post(
        "/admin/api/v1/resources/t_d7_items/records",
        json={"id": 9, "title": "nope"},
    )
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "forbidden"
    assert "message" in err
    assert err.get("details", {}).get("action") == "create" or "create" in err["message"]
