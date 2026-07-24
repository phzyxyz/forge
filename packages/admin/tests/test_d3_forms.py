"""Diamond D3 — form widgets, fieldsets, field-level validation."""

from __future__ import annotations

from datetime import date

import pytest
from phzyx.admin import AdminService, FieldsetConfig, ValidationAdminError, infer_resource
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class FormUser(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    name: str = Field()
    active: bool = Field(default=True)
    joined: date | None = Field(default=None)
    notes: str = Field(default="")

    class Meta:
        table = "d3_form_users"
        register = False


@pytest.mark.unit
def test_infer_widgets_fieldsets_required() -> None:
    res = infer_resource(FormUser)
    assert res.column("active") and res.column("active").widget == "bool"
    assert res.column("joined") and res.column("joined").widget == "date"
    assert res.column("notes") and res.column("notes").widget == "textarea"
    assert res.column("email") and res.column("email").required is True
    assert res.column("active") and res.column("active").required is False
    assert len(res.fieldsets) >= 2
    names = {fs.name for fs in res.fieldsets}
    assert "identity" in names and "details" in names
    schema = res.public_schema()
    assert any(c["widget"] == "bool" for c in schema["columns"])
    assert schema["fieldsets"]
    assert isinstance(FieldsetConfig(name="x", label="X", fields=("a",)), FieldsetConfig)


@pytest.mark.integration
@pytest.mark.sqlite
def test_create_validation_fields(tmp_path) -> None:
    db = tmp_path / "d3.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([FormUser], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        svc = AdminService(resources={"users": infer_resource(FormUser)}, session=session)
        with pytest.raises(ValidationAdminError) as ei:
            svc.create("users", {"id": 1})  # missing email/name
        err = ei.value
        assert err.status == 422
        fields = err.details.get("fields") or {}
        assert "email" in fields or "name" in fields or fields
        # happy path with date
        created = svc.create(
            "users",
            {
                "id": 1,
                "email": "a@b.co",
                "name": "A",
                "active": True,
                "joined": "2024-01-02",
                "notes": "hi",
            },
        )
        assert created["email"] == "a@b.co"
        assert created.get("joined") in {"2024-01-02", date(2024, 1, 2)} or str(
            created.get("joined")
        ).startswith("2024")
        session.close()
    finally:
        conn.close()
