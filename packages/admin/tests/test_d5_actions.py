"""Diamond D5 — AdminAction SPI + runner."""

from __future__ import annotations

import pytest
from phzyx.admin import (
    AdminAction,
    AdminService,
    infer_resource,
    list_admin_actions,
    run_admin_action,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Flag(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    active: bool = Field(default=True)

    class Meta:
        table = "d5_flags"
        register = False


@pytest.mark.unit
def test_admin_action_catalog_scopes() -> None:
    all_a = list_admin_actions("flags", has_active=True)
    scopes = {a["scope"] for a in all_a}
    assert "global" in scopes and "bulk" in scopes and "row" in scopes
    assert any(a["client"] == "export:csv" for a in all_a)
    bulk = list_admin_actions("flags", has_active=True, scope="bulk")
    assert all(a["scope"] == "bulk" for a in bulk)
    assert isinstance(AdminAction(name="x", label="X"), AdminAction)
    no_active = list_admin_actions("x", has_active=False)
    assert not any(a["name"] == "deactivate" for a in no_active)


@pytest.mark.integration
@pytest.mark.sqlite
def test_run_activate_deactivate(tmp_path) -> None:
    db = tmp_path / "d5.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Flag], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        session.add(Flag(id=1, name="a", active=True))
        session.add(Flag(id=2, name="b", active=True))
        session.commit()
        svc = AdminService(resources={"flags": infer_resource(Flag)}, session=session)
        listed = svc.list("flags")
        idents = [r["_identity"] for r in listed.items]
        out = run_admin_action(svc, "flags", "deactivate", idents)
        assert out["updated"] == 2
        assert svc.list("flags", filters={"active": "true"}).total == 0
        out2 = svc.run_action("flags", "activate", idents[:1])
        assert out2["updated"] == 1
        assert svc.list("flags", filters={"active": "true"}).total == 1
        catalog = svc.list_actions("flags")
        assert any(a["name"] == "export_csv" for a in catalog)
        session.close()
    finally:
        conn.close()
