"""Security, themes ambient, layouts, audit (S6)."""

from __future__ import annotations

import pytest
from phzyx.admin import (
    AdminService,
    AuditLog,
    LayoutPrefs,
    LayoutStore,
    SettingsStore,
    assert_no_mass_assignment,
    csp_headers,
    infer_resource,
    resolve_theme,
    theme_tokens_css,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    secret: str = Field(admin_exclude=True, default="s")

    class Meta:
        table = "users"
        register = False


@pytest.mark.unit
def test_resolve_ambient_theme() -> None:
    assert resolve_theme("system-ambient", prefers_dark=True) == "stellar-dark"
    assert resolve_theme("system-ambient", prefers_dark=False) == "magical-white"
    assert resolve_theme("magical-white") == "magical-white"
    css = theme_tokens_css("stellar-dark", reduced_transparency=True)
    assert "phzyx-bg-app" in css


@pytest.mark.unit
def test_mass_assignment_denies_secrets() -> None:
    res = infer_resource(User)
    with pytest.raises(Exception, match="mass assignment|excluded"):
        assert_no_mass_assignment(res, {"id": 1, "email": "a", "secret": "x"})
    clean = assert_no_mass_assignment(res, {"id": 1, "email": "a@b.co"})
    assert "secret" not in clean


@pytest.mark.unit
def test_csp_headers() -> None:
    h = csp_headers()
    assert "Content-Security-Policy" in h
    assert "default-src" in h["Content-Security-Policy"]


@pytest.mark.unit
def test_layouts_and_settings_store() -> None:
    store = LayoutStore()
    prefs = LayoutPrefs(resource="users", principal_id="u1", columns=["email", "id"])
    store.put(prefs)
    assert store.get("users", "u1") is not None
    settings = SettingsStore()
    settings.patch({"default_theme": "system-ambient", "reduced_transparency": True})
    assert settings.get().default_theme == "system-ambient"


@pytest.mark.integration
@pytest.mark.sqlite
def test_audit_on_create(tmp_path) -> None:
    db = tmp_path / "a.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([User], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        audit = AuditLog()
        svc = AdminService(
            resources={"users": infer_resource(User)},
            session=session,
            audit=audit,
        )
        svc.create("users", {"id": 1, "email": "a@b.co"})
        events = audit.list()
        assert any(e.action == "create" for e in events)
        session.close()
    finally:
        conn.close()
