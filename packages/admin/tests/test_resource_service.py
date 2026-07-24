"""Admin resource + service tests (S4.1–S4.2)."""

from __future__ import annotations

import pytest
from phzyx.admin import (
    AdminService,
    DenyWrites,
    ForbiddenError,
    encode_identity,
    export_csv,
    export_json,
    infer_resource,
    open_meta_for_key,
    override_resource,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, FileField, Model, Session
from phzyx.schema.types import Dialect


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    secret: str = Field(admin_exclude=True, default="s3cr3t")

    class Meta:
        table = "users"
        register = False


class Membership(Model):
    org_id: int = Field(primary_key=True)
    user_id: int = Field(primary_key=True)
    role: str = Field(default="member")

    class Meta:
        table = "memberships"
        register = False


class Asset(Model):
    id: int = Field(primary_key=True)
    path: str = FileField()

    class Meta:
        table = "assets"
        register = False


@pytest.mark.unit
def test_infer_resource_and_identity() -> None:
    res = infer_resource(User)
    assert res.name == "users"
    assert res.primary_key == ("id",)
    secret = res.column("secret")
    assert secret is not None and secret.secret is True
    assert "secret" not in res.exportable_columns()

    ident = encode_identity(Membership, {"org_id": 1, "user_id": 2})
    assert "org_id" in ident or "%22" in ident


@pytest.mark.integration
@pytest.mark.sqlite
def test_service_crud_export_copy_authz(tmp_path) -> None:
    db = tmp_path / "admin.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([User, Membership], conn, adapter, yes=True)
    finally:
        conn.close()

    def factory() -> Session:
        c, _ = connect(f"sqlite:///{db}")
        return Session(c, dialect=Dialect.SQLITE)

    resources = {
        "users": override_resource(infer_resource(User), secrets=("secret",)),
        "memberships": infer_resource(Membership),
    }
    # keep session open for service
    session = factory()
    try:
        svc = AdminService(resources=resources, session=session)
        created = svc.create("users", {"id": 1, "email": "a@b.co"})
        assert created["email"] == "a@b.co"
        assert "secret" not in created
        listed = svc.list("users")
        assert listed.total == 1
        ident = created["_identity"]
        got = svc.get("users", ident)
        assert got["email"] == "a@b.co"

        body_json = export_json(resources["users"], listed.items)
        assert "a@b.co" in body_json
        assert "s3cr3t" not in body_json and "nope" not in body_json
        body_csv = export_csv(resources["users"], listed.items)
        assert "email" in body_csv

        copy = svc.copy("users", fmt="json")
        assert "a@b.co" in copy

        # composite
        m = svc.create("memberships", {"org_id": 9, "user_id": 8, "role": "admin"})
        mid = m["_identity"]
        assert svc.get("memberships", mid)["role"] == "admin"

        denied = AdminService(resources=resources, session=session, authz=DenyWrites())
        with pytest.raises(ForbiddenError):
            denied.create("users", {"id": 2, "email": "x@y.z"})
    finally:
        session.close()


@pytest.mark.unit
def test_file_opener_modes() -> None:
    assert open_meta_for_key("a.png").mode == "image"
    assert open_meta_for_key("a.pdf").mode == "pdf"
    assert open_meta_for_key("a.txt").mode == "text"
    assert open_meta_for_key("a.bin").mode == "download"
