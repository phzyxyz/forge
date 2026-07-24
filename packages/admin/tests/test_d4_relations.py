"""Diamond D4 — FK metadata, autocomplete, has-many relations."""

from __future__ import annotations

import pytest
from phzyx.admin import AdminService, infer_resource, wire_relations
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Author(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    email: str = Field()

    class Meta:
        table = "authors"
        register = False


class Article(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    author_id: int = Field(foreign_key="authors.id")

    class Meta:
        table = "articles"
        register = False


class Comment(Model):
    id: int = Field(primary_key=True)
    author_id: int = Field(foreign_key="authors.id")
    body: str = Field()

    class Meta:
        table = "comments"
        register = False


@pytest.mark.unit
def test_infer_fk_and_wire_relations() -> None:
    authors = infer_resource(Author)
    articles = infer_resource(Article)
    comments = infer_resource(Comment)
    assert articles.column("author_id")
    assert articles.column("author_id").widget == "fk"
    assert articles.column("author_id").fk_resource == "authors"

    wired = wire_relations({"authors": authors, "articles": articles, "comments": comments})
    auth = wired["authors"]
    rel_names = {r.name for r in auth.relations}
    assert "articles" in rel_names
    assert "comments" in rel_names
    art = wired["articles"]
    col = art.column("author_id")
    assert col and col.fk_label_fields
    schema = auth.public_schema()
    assert schema["relations"]


@pytest.mark.integration
@pytest.mark.sqlite
def test_autocomplete_and_list_relation(tmp_path) -> None:
    db = tmp_path / "d4.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Author, Article, Comment], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        session.add(Author(id=1, name="Ada", email="ada@x.co"))
        session.add(Author(id=2, name="Bob", email="bob@x.co"))
        session.add(Article(id=1, title="A1", author_id=1))
        session.add(Article(id=2, title="A2", author_id=1))
        session.add(Article(id=3, title="B1", author_id=2))
        session.add(Comment(id=1, author_id=1, body="hi"))
        session.commit()
        resources = wire_relations(
            {
                "authors": infer_resource(Author),
                "articles": infer_resource(Article),
                "comments": infer_resource(Comment),
            }
        )
        svc = AdminService(resources=resources, session=session)

        opts = svc.autocomplete("authors", q="Ada")
        assert len(opts) >= 1
        assert any(o["label"].startswith("Ada") or "ada" in o["label"].lower() for o in opts)
        assert opts[0]["value"] in {1, "1"} or any(o["value"] == 1 for o in opts)

        related = svc.list_relation("authors", "1", "articles")
        assert related.total == 2
        assert all(r["author_id"] == 1 for r in related.items)

        session.close()
    finally:
        conn.close()
