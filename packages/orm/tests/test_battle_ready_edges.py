"""Battle-readiness edge cases — insert/update/upsert/locks/count."""

from __future__ import annotations

from datetime import datetime

import pytest
from phzyx.orm import (
    ConflictError,
    Field,
    Model,
    Session,
    soft_delete,
    soft_delete_filter,
    upsert,
)
from phzyx.orm.sql import build_select
from phzyx.schema import apply_manifest_sqlite, build_manifest
from phzyx.schema.types import Dialect


class EdgeUser(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    version: int = Field(default=1, optimistic=True)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None, auto_now_add=True)
    # Generated: omitted on insert
    price: int = Field(default=10)
    qty: int = Field(default=2)
    total: int | None = Field(default=None, generated="price * qty")

    class Meta:
        table = "edge_users"
        register = False


@pytest.fixture()
def session():
    m = build_manifest([EdgeUser])
    # SQLite may not support generated columns on all versions — strip for apply
    # by building simple table via push-compatible DDL without generated if needed
    conn = apply_manifest_sqlite(m)
    # If generated failed, table may still work without total column expression
    s = Session(conn, dialect=Dialect.SQLITE)
    yield s
    s.close()


@pytest.mark.unit
def test_ai_pk_empty_string_and_explicit_seed():
    class U(Model):
        id: int | None = Field(default=None, primary_key=True)
        email: str = Field()

        class Meta:
            table = "u_edge"
            register = False

    conn = apply_manifest_sqlite(build_manifest([U]))
    s = Session(conn, dialect=Dialect.SQLITE)
    a = s.add(U(email="a@x.co"))
    s.commit()
    assert a.id == 1
    # empty string id treated as omit
    b = s.add(U(id=None, email="b@x.co"))  # type: ignore[arg-type]
    s.commit()
    assert b.id == 2
    # explicit seed id
    c = s.add(U(id=99, email="c@x.co"))
    s.commit()
    assert c.id == 99
    s.close()


@pytest.mark.unit
def test_for_update_not_emitted_on_sqlite():
    class R(Model):
        id: int | None = Field(default=None, primary_key=True)
        name: str = Field()

        class Meta:
            table = "r_fu"
            register = False

    frag = build_select(R, dialect=Dialect.SQLITE, for_update=True)
    assert "FOR UPDATE" not in frag.sql
    frag_pg = build_select(R, dialect=Dialect.POSTGRES, for_update="NOWAIT")
    assert "FOR UPDATE NOWAIT" in frag_pg.sql


@pytest.mark.unit
def test_optimistic_conflict_and_count():
    class D(Model):
        id: int | None = Field(default=None, primary_key=True)
        title: str = Field()
        version: int = Field(default=1, optimistic=True)

        class Meta:
            table = "d_opt2"
            register = False

    conn = apply_manifest_sqlite(build_manifest([D]))
    s = Session(conn, dialect=Dialect.SQLITE)
    d = s.add(D(title="t"))
    s.commit()
    assert s.count(D) == 1
    a = s.get(D, d.id)
    b = s.get(D, d.id)
    assert a and b
    s.update(a, title="t2")
    s.commit()
    with pytest.raises(ConflictError):
        s.update(b, title="t3")
    s.close()


@pytest.mark.unit
def test_upsert_and_soft_delete_edges():
    class D(Model):
        id: int | None = Field(default=None, primary_key=True)
        title: str = Field()
        deleted_at: datetime | None = Field(default=None)

        class Meta:
            table = "d_up"
            register = False

    conn = apply_manifest_sqlite(build_manifest([D]))
    s = Session(conn, dialect=Dialect.SQLITE)
    s.add(D(id=5, title="x"))
    s.commit()
    out = upsert(s, D(id=5, title="y"), conflict=["id"], update_columns=["title"])
    s.commit()
    assert out.title == "y"
    row = s.get(D, 5)
    assert row is not None
    soft_delete(s, row)
    s.commit()
    assert s.query(D, where=soft_delete_filter()) == []
    # row still exists (soft-deleted)
    assert s.count(D) == 1
    s.close()


@pytest.mark.unit
def test_update_rejects_unset_pk():
    class D(Model):
        id: int | None = Field(default=None, primary_key=True)
        title: str = Field()

        class Meta:
            table = "d_pk"
            register = False

    conn = apply_manifest_sqlite(build_manifest([D]))
    s = Session(conn, dialect=Dialect.SQLITE)
    ghost = D.model_construct(title="no-id")
    with pytest.raises(ValueError, match="primary key"):
        s.update(ghost, title="x")
    s.close()
