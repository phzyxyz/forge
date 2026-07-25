"""Optimistic lock, soft delete, upsert, bulk_update."""

from __future__ import annotations

from datetime import datetime

import pytest
from phzyx.orm import (
    ConflictError,
    Field,
    Model,
    Session,
    bulk_update,
    soft_delete,
    soft_delete_filter,
    upsert,
)
from phzyx.schema import apply_manifest_sqlite, build_manifest
from phzyx.schema.types import Dialect


class Doc(Model):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field()
    version: int = Field(default=1, optimistic=True)
    deleted_at: datetime | None = Field(default=None)

    class Meta:
        table = "docs_opt"
        register = False


@pytest.mark.unit
def test_optimistic_conflict_and_soft_delete() -> None:
    m = build_manifest([Doc])
    conn = apply_manifest_sqlite(m)
    s = Session(conn, dialect=Dialect.SQLITE)
    d = s.add(Doc(title="a"))
    s.commit()
    assert d.id == 1
    assert d.version == 1

    d2 = s.get(Doc, 1)
    assert d2 is not None
    d2b = s.get(Doc, 1)
    assert d2b is not None
    s.update(d2, title="b")
    s.commit()
    with pytest.raises(ConflictError):
        s.update(d2b, title="c")  # stale version

    soft_delete(s, s.get(Doc, 1))  # type: ignore[arg-type]
    s.commit()
    live = s.query(Doc, where=soft_delete_filter())
    assert live == []


@pytest.mark.unit
def test_upsert_and_bulk_update() -> None:
    m = build_manifest([Doc])
    conn = apply_manifest_sqlite(m)
    s = Session(conn, dialect=Dialect.SQLITE)
    s.add(Doc(id=10, title="x", version=1))
    s.commit()
    upsert(s, Doc(id=10, title="y", version=1), conflict=["id"], update_columns=["title"])
    s.commit()
    row = s.get(Doc, 10)
    assert row is not None
    assert row.title == "y"
    bulk_update(s, Doc, [{"id": 10, "title": "z"}])
    s.commit()
    row2 = s.get(Doc, 10)
    assert row2 is not None
    assert row2.title == "z"
