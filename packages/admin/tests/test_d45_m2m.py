"""Diamond D4.5 — many-to-many multi-select save round-trip."""

from __future__ import annotations

import pytest
from phzyx.admin import AdminService, infer_resource, m2m_relation, wire_relations
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Post(Model):
    id: int = Field(primary_key=True)
    title: str = Field()

    class Meta:
        table = "posts_m2m"
        register = False


class Tag(Model):
    id: int = Field(primary_key=True)
    name: str = Field()

    class Meta:
        table = "tags_m2m"
        register = False


class PostTag(Model):
    """Through table: composite PK of two FKs → auto M2M."""

    post_id: int = Field(primary_key=True, foreign_key="posts_m2m.id")
    tag_id: int = Field(primary_key=True, foreign_key="tags_m2m.id")

    class Meta:
        table = "post_tags_m2m"
        register = False


@pytest.mark.unit
def test_wire_detects_m2m() -> None:
    wired = wire_relations(
        {
            "posts_m2m": infer_resource(Post),
            "tags_m2m": infer_resource(Tag),
            "post_tags_m2m": infer_resource(PostTag),
        }
    )
    posts = wired["posts_m2m"]
    m2m = [r for r in posts.relations if r.kind == "m2m"]
    assert m2m, posts.relations
    rel = m2m[0]
    assert rel.resource == "tags_m2m"
    assert rel.through == "post_tags_m2m"
    assert rel.through_local == "post_id"
    assert rel.through_remote == "tag_id"
    schema = posts.public_schema()
    assert any(r.get("kind") == "m2m" for r in schema["relations"])
    # reverse auto-wire
    tags = wired["tags_m2m"]
    rev = [r for r in tags.relations if r.kind == "m2m"]
    assert rev and rev[0].resource == "posts_m2m"
    assert rev[0].through_local == "tag_id"


@pytest.mark.unit
def test_m2m_relation_helper() -> None:
    rel = m2m_relation(
        name="tags",
        resource="tags",
        through="post_tags",
        through_local="post_id",
        through_remote="tag_id",
        label="Tags",
    )
    assert rel.kind == "m2m"
    assert rel.through == "post_tags"
    assert rel.foreign_key == ""


@pytest.mark.integration
@pytest.mark.sqlite
def test_m2m_list_and_set_roundtrip(tmp_path) -> None:
    db = tmp_path / "m2m.db"
    url = f"sqlite:///{db}"
    conn, ad = connect(url)
    try:
        push_schema([Post, Tag, PostTag], conn, ad, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        session.add(Post(id=1, title="Hello"))
        session.add(Post(id=2, title="World"))
        session.add(Tag(id=10, name="python"))
        session.add(Tag(id=11, name="admin"))
        session.add(Tag(id=12, name="orm"))
        session.add(PostTag(post_id=1, tag_id=10))
        session.commit()

        resources = wire_relations(
            {
                "posts_m2m": infer_resource(Post),
                "tags_m2m": infer_resource(Tag),
                "post_tags_m2m": infer_resource(PostTag),
            }
        )
        svc = AdminService(resources=resources, session=session)

        listed = svc.list_relation("posts_m2m", "1", "tags_m2m")
        assert listed.total == 1
        assert listed.items[0]["name"] == "python"

        ids = svc.get_m2m_ids("posts_m2m", "1", "tags_m2m")
        assert ids == ["10"]

        out = svc.set_m2m("posts_m2m", "1", "tags_m2m", [10, 11, 12, 11])
        assert out["count"] == 3  # deduped
        assert out["ids"] == ["10", "11", "12"]
        ids2 = svc.get_m2m_ids("posts_m2m", "1", "tags_m2m")
        assert set(ids2) == {"10", "11", "12"}

        listed2 = svc.list_relation("posts_m2m", "1", "tags_m2m")
        assert listed2.total == 3

        # clear all memberships
        cleared = svc.set_m2m("posts_m2m", "1", "tags_m2m", [])
        assert cleared["count"] == 0
        assert svc.get_m2m_ids("posts_m2m", "1", "tags_m2m") == []
        assert svc.list_relation("posts_m2m", "1", "tags_m2m").total == 0

        # re-link reverse side
        svc.set_m2m("tags_m2m", "11", "posts_m2m", [1, 2])
        rev = svc.list_relation("tags_m2m", "11", "posts_m2m")
        assert rev.total == 2
        assert {str(r["id"]) for r in rev.items} == {"1", "2"}

        session.close()
    finally:
        conn.close()
