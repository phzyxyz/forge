"""D2.5 operators + PK-auto + export include + field RBAC."""

from __future__ import annotations

import pytest
from phzyx.admin.auth import AllowAll
from phzyx.admin.resource import infer_resource
from phzyx.admin.service import AdminService
from phzyx.auth.admin_bridge import PhzyxFieldAuthz
from phzyx.auth.principal import Principal
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    name: str = Field()
    active: bool = Field(default=True)
    age: int = Field(default=0)

    class Meta:
        table = "t_users_d25"
        register = False


class Post(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    author_id: int = Field(foreign_key="t_users_d25.id")

    class Meta:
        table = "t_posts_d25"
        register = False


@pytest.fixture
def svc(tmp_path):
    db = tmp_path / "d25.db"
    url = f"sqlite:///{db}"
    conn, ad = connect(url)
    push_schema([User, Post], conn, ad, yes=True)
    session = Session(conn, dialect=Dialect.SQLITE)
    session.add(User(id=1, email="a@x.co", name="Alice", active=True, age=30))
    session.add(User(id=2, email="b@x.co", name="Bob", active=False, age=22))
    session.add(User(id=3, email="c@x.co", name="Cara", active=True, age=45))
    session.add(Post(id=1, title="Hello", author_id=1))
    session.add(Post(id=2, title="World", author_id=1))
    session.commit()
    resources = {
        "users": infer_resource(User, name="users"),
        "posts": infer_resource(Post, name="posts"),
    }
    # wire relations manually for export include
    from phzyx.admin.resource import wire_relations

    resources = wire_relations(resources)
    # ensure users has posts relation if wire_relations adds it
    return AdminService(resources=resources, session=session, authz=AllowAll())


@pytest.mark.unit
def test_filter_ops_contains_and_gt(svc: AdminService) -> None:
    r = svc.list("users", filters={"email__contains": "a@"}, principal=None)
    assert r.total >= 1
    r2 = svc.list("users", filters={"age__gt": "25"}, principal=None)
    assert all(int(i["age"]) > 25 for i in r2.items)


@pytest.mark.unit
def test_live_search_or_across_fields(svc: AdminService) -> None:
    r = svc.list("users", search="Bob", principal=None)
    assert r.total == 1
    assert r.items[0]["name"] == "Bob"


@pytest.mark.unit
def test_pk_auto_create(svc: AdminService) -> None:
    schema = svc.public_schema("users")
    id_col = next(c for c in schema["columns"] if c["name"] == "id")
    assert id_col.get("autoincrement") is True
    created = svc.create(
        "users",
        {"email": "d@x.co", "name": "Dan", "active": True, "age": 19},
        principal=None,
    )
    assert created["id"]
    assert created["email"] == "d@x.co"


@pytest.mark.unit
def test_export_include_relations(svc: AdminService) -> None:
    # if wire_relations didn't attach, attach manually
    users = svc.get_resource("users")
    if not users.relations:
        from dataclasses import replace

        from phzyx.admin.resource import RelationConfig

        svc.resources["users"] = replace(
            users,
            relations=(
                RelationConfig(
                    name="posts",
                    label="Posts",
                    resource="posts",
                    foreign_key="author_id",
                ),
            ),
        )
    media, body = svc.export(
        "users",
        fmt="json",
        include=["posts"],
        filters={"email__eq": "a@x.co"},
        principal=None,
    )
    assert "application/json" in media
    assert "_relations" in body or "Hello" in body


@pytest.mark.unit
def test_field_rbac_hides_field() -> None:
    class DenyEmail(PhzyxFieldAuthz):
        def __init__(self) -> None:
            super().__init__(default_allow=True)

        def allow_read(self, principal, resource, field):  # type: ignore[no-untyped-def]
            if field == "email":
                return False
            return super().allow_read(principal, resource, field)

    # rebuild minimal
    from phzyx.engine import connect, push_schema

    conn, ad = connect("sqlite:///:memory:")
    push_schema([User], conn, ad, yes=True)
    session = Session(conn, dialect=Dialect.SQLITE)
    session.add(User(id=1, email="secret@x.co", name="X", active=True, age=1))
    session.commit()
    resources = {"users": infer_resource(User, name="users")}
    svc = AdminService(
        resources=resources,
        session=session,
        authz=AllowAll(),
        field_authz=DenyEmail(),
    )
    p = Principal(id="1", is_staff=True, permissions=frozenset())
    row = svc.get("users", "1", principal=p)
    assert "email" not in row
    assert row["name"] == "X"
