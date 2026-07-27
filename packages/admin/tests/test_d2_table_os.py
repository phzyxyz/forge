"""Diamond D2 — filters, bulk actions, keyset pagination mode."""

from __future__ import annotations

import pytest
from phzyx.admin import AdminService, BulkAction, infer_resource, list_bulk_actions
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Person(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    name: str = Field()
    active: bool = Field(default=True)
    score: int = Field(default=0)

    class Meta:
        table = "d2_people"
        register = False


@pytest.mark.unit
def test_infer_filterable_and_bulk_action_export() -> None:
    res = infer_resource(Person)
    assert "email" in res.filterable
    assert "active" in res.filterable
    assert "score" in res.filterable
    col = res.column("active")
    assert col is not None and col.filterable and col.filter_type == "bool"
    schema = res.public_schema()
    assert "filterable" in schema
    assert any(c["name"] == "active" and c["filter_type"] == "bool" for c in schema["columns"])
    actions = list_bulk_actions("people", has_active=True)
    assert any(a["name"] == "deactivate" for a in actions)
    assert isinstance(BulkAction(name="x", label="X"), BulkAction)


@pytest.mark.integration
@pytest.mark.sqlite
def test_list_filters_and_bulk_deactivate(tmp_path) -> None:
    db = tmp_path / "d2.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Person], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        session.add(Person(id=1, email="a@x.co", name="A", active=True, score=10))
        session.add(Person(id=2, email="b@x.co", name="B", active=True, score=20))
        session.add(Person(id=3, email="c@x.co", name="C", active=False, score=10))
        session.commit()
        svc = AdminService(resources={"people": infer_resource(Person)}, session=session)

        by_active = svc.list("people", filters={"active": "true"})
        assert by_active.total == 2
        assert all(r["active"] is True for r in by_active.items)

        by_score = svc.list("people", filters={"score": "10"})
        assert by_score.total == 2
        assert {r["id"] for r in by_score.items} == {1, 3}

        by_email = svc.list("people", filters={"email": "b@x.co"})
        assert by_email.total == 1 and by_email.items[0]["name"] == "B"

        # ignored unknown filter
        ignore = svc.list("people", filters={"not_a_col": "x"})
        assert ignore.total == 3

        acts = svc.list_bulk_actions("people")
        assert any(a["name"] == "deactivate" for a in acts)

        idents = [r["_identity"] for r in by_active.items]
        out = svc.bulk_action("people", "deactivate", idents)
        assert out["updated"] == 2
        after = svc.list("people", filters={"active": "true"})
        assert after.total == 0
        session.close()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_default_list_is_keyset_with_offset_compat(tmp_path) -> None:
    """Default list mode is keyset; page>1 without cursor falls back to offset."""
    from phzyx.admin.service import _resolve_list_pagination

    assert _resolve_list_pagination("keyset", page=1, cursor=None) == "keyset"
    assert _resolve_list_pagination("keyset", page=2, cursor=None) == "offset"
    assert _resolve_list_pagination("offset", page=1, cursor=None) == "offset"
    assert _resolve_list_pagination("keyset", page=2, cursor="abc") == "keyset"


def test_keyset_pagination_mode(tmp_path) -> None:

    db = tmp_path / "d2k.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Person], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        for i in range(1, 6):
            session.add(Person(id=i, email=f"u{i}@x.co", name=f"U{i}", active=True, score=i))
        session.commit()
        svc = AdminService(resources={"people": infer_resource(Person)}, session=session)

        off = svc.list("people", page_size=2, pagination="offset")
        assert off.pagination == "offset"
        assert off.next_cursor is None
        assert len(off.items) == 2

        k1 = svc.list("people", page_size=2, pagination="keyset")
        assert k1.pagination == "keyset"
        assert k1.has_more and k1.next_cursor
        k2 = svc.list(
            "people",
            page_size=2,
            pagination="keyset",
            cursor=k1.next_cursor,
            filters={"active": "true"},
        )
        assert k2.items[0]["id"] > k1.items[-1]["id"]
        session.close()
    finally:
        conn.close()
