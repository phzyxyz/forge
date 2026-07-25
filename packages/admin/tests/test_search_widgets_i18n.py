"""Global search, widgets, i18n, relation managers."""

from __future__ import annotations

import pytest
from phzyx.admin import (
    AdminService,
    I18n,
    all_relation_managers,
    infer_resource,
    wire_relations,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Author(Model):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field()

    class Meta:
        table = "authors_sw"
        register = False


class Book(Model):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field()
    author_id: int = Field(foreign_key="authors_sw.id")

    class Meta:
        table = "books_sw"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_search_widgets_i18n(tmp_path) -> None:
    db = tmp_path / "sw.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Author, Book], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        resources = wire_relations(
            {
                "authors": infer_resource(Author),
                "books": infer_resource(Book),
            }
        )
        svc = AdminService(resources=resources, session=session)
        a = svc.create("authors", {"name": "Ada"})
        svc.create("books", {"title": "Notes", "author_id": a["id"]})

        hits = svc.global_search("Ada")
        assert any(h["resource"] == "authors" for h in hits)

        widgets = svc.dashboard_widgets()
        assert any(w["resource"] == "books" and w["value"] >= 1 for w in widgets)

        cat = svc.i18n_catalog()
        assert cat["action.save"] == "Save"
        assert I18n("en").t("error.conflict")

        rms = svc.relation_managers("authors")
        assert isinstance(rms, list)
        assert all_relation_managers(resources)
        session.close()
    finally:
        conn.close()
