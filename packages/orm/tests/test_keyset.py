"""Keyset pagination tests (S5.1)."""

from __future__ import annotations

import pytest
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session, bulk_insert, encode_cursor
from phzyx.schema.types import Dialect


class Row(Model):
    id: int = Field(primary_key=True)
    name: str = Field()

    class Meta:
        table = "rows"
        register = False


class Comp(Model):
    a: int = Field(primary_key=True)
    b: int = Field(primary_key=True)
    label: str = Field(default="x")

    class Meta:
        table = "comp"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_keyset_pages_and_composite(tmp_path) -> None:
    db = tmp_path / "ks.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Row, Comp], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        bulk_insert(session, Row, [{"id": i, "name": f"n{i}"} for i in range(1, 11)])
        session.commit()

        p1 = session.query_keyset(Row, limit=3)
        assert len(p1.items) == 3
        assert p1.has_more and p1.next_cursor
        p2 = session.query_keyset(Row, limit=3, cursor=p1.next_cursor)
        assert p2.items[0].id > p1.items[-1].id
        # no overlap
        assert {r.id for r in p1.items}.isdisjoint({r.id for r in p2.items})

        bulk_insert(
            session,
            Comp,
            [{"a": 1, "b": i, "label": f"c{i}"} for i in range(1, 6)],
        )
        session.commit()
        c1 = session.query_keyset(Comp, limit=2)
        assert len(c1.items) == 2
        c2 = session.query_keyset(Comp, limit=2, cursor=c1.next_cursor)
        assert (c2.items[0].a, c2.items[0].b) > (c1.items[-1].a, c1.items[-1].b)

        # stream all
        all_ids = [r.id for r in session.iter_query(Row, chunk_size=4)]
        assert all_ids == list(range(1, 11))
        session.close()
    finally:
        conn.close()


@pytest.mark.unit
def test_cursor_roundtrip() -> None:
    c = encode_cursor({"id": 5, "name": "x"})
    from phzyx.orm import decode_cursor

    assert decode_cursor(c)["id"] == 5
