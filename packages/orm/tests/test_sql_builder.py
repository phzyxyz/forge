"""SQL builder unit tests (S3.1)."""

from __future__ import annotations

import pytest
from phzyx.orm import (
    Field,
    Model,
    build_delete,
    build_insert,
    build_select,
    build_select_by_pk,
    build_update,
    desc,
    eq,
    in_,
    is_null,
    like,
)
from phzyx.schema.types import Dialect


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    age: int | None = Field(default=None)

    class Meta:
        table = "users"
        register = False


@pytest.mark.unit
def test_insert_select_update_delete_parameterized() -> None:
    ins = build_insert(User, {"id": 1, "email": "a@b.co"}, dialect=Dialect.SQLITE)
    assert "INSERT INTO" in ins.sql
    assert ins.params == [1, "a@b.co"]
    assert "?" in ins.sql

    sel = build_select(User, where=[eq("email", "a@b.co")], order_by=[desc("id")], limit=10)
    assert "WHERE" in sel.sql and "ORDER BY" in sel.sql and "LIMIT 10" in sel.sql

    upd = build_update(User, {"email": "x@y.z"}, [eq("id", 1)])
    assert "UPDATE" in upd.sql and upd.params[-1] == 1

    delete = build_delete(User, [eq("id", 1)])
    assert "DELETE FROM" in delete.sql


@pytest.mark.unit
def test_filters_in_null_like() -> None:
    sel = build_select(User, where=[in_("id", [1, 2]), is_null("age"), like("email", "%@%")])
    assert "IN" in sel.sql
    assert "IS NULL" in sel.sql
    assert "LIKE" in sel.sql


@pytest.mark.unit
def test_composite_pk_select() -> None:
    class Membership(Model):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True)

        class Meta:
            table = "memberships"
            register = False

    frag = build_select_by_pk(Membership, {"org_id": 1, "user_id": 2})
    assert frag.params == [1, 2]
    assert frag.sql.count("=") >= 2


@pytest.mark.unit
def test_update_requires_where() -> None:
    with pytest.raises(ValueError, match="WHERE"):
        build_update(User, {"email": "x"}, [])


@pytest.mark.unit
def test_postgres_placeholders_and_returning() -> None:
    ins = build_insert(User, {"id": 1, "email": "a@b.co"}, dialect=Dialect.POSTGRES, returning=True)
    assert "%s" in ins.sql
    assert "RETURNING" in ins.sql


@pytest.mark.unit
def test_mysql_placeholders_and_backticks() -> None:
    ins = build_insert(User, {"id": 1, "email": "a@b.co"}, dialect=Dialect.MYSQL)
    assert "%s" in ins.sql
    assert "`users`" in ins.sql or "`id`" in ins.sql
    assert "RETURNING" not in ins.sql
    sel = build_select(User, where=[eq("email", "a@b.co")], dialect=Dialect.MYSQL)
    assert "%s" in sel.sql
    assert "`email`" in sel.sql


@pytest.mark.unit
def test_create_engine_accepts_mysql_url() -> None:
    from phzyx.orm.engine_sync import create_engine

    eng = create_engine("mysql+pymysql://root@localhost/app")
    assert eng.dialect is Dialect.MYSQL
    eng2 = create_engine("mariadb://root@localhost/app")
    assert eng2.dialect is Dialect.MYSQL
