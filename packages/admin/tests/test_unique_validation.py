"""Admin create/update unique field validation (422, not silent IntegrityError)."""

from __future__ import annotations

import pytest
from phzyx.admin import AdminService, ValidationAdminError, infer_resource
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Account(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    name: str = Field()

    class Meta:
        table = "uniq_accounts"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_create_rejects_duplicate_unique_email(tmp_path) -> None:
    db = tmp_path / "uniq.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Account], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        svc = AdminService(
            resources={"accounts": infer_resource(Account)},
            session=session,
        )
        a = svc.create("accounts", {"email": "a@x.co", "name": "A"})
        assert a["email"] == "a@x.co"
        with pytest.raises(ValidationAdminError) as ei:
            svc.create("accounts", {"email": "a@x.co", "name": "Dup"})
        err = ei.value
        assert err.status == 422
        assert "email" in (err.details.get("fields") or {})
        session.close()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_update_allows_same_row_unique(tmp_path) -> None:
    db = tmp_path / "uniq2.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Account], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        svc = AdminService(
            resources={"accounts": infer_resource(Account)},
            session=session,
        )
        a = svc.create("accounts", {"email": "b@x.co", "name": "B"})
        # same email on same row is fine
        u = svc.update("accounts", str(a["id"]), {"name": "B2", "email": "b@x.co"})
        assert u["name"] == "B2"
        # another row claiming the email fails
        b = svc.create("accounts", {"email": "c@x.co", "name": "C"})
        with pytest.raises(ValidationAdminError):
            svc.update("accounts", str(b["id"]), {"email": "b@x.co"})
        session.close()
    finally:
        conn.close()
