"""phzyx-auth foundation tests (Phase A core)."""

from __future__ import annotations

import asyncio

import pytest
from phzyx.auth import (
    AbstractUser,
    AuthConfig,
    ForbiddenError,
    PasswordHasher,
    Principal,
    UnauthorizedError,
    User,
    hash_password,
    principal_from_user,
    require_auth,
    require_permissions,
    require_scopes,
    require_staff,
    resolve_permissions,
    seed_resource_permissions,
    verify_password,
)
from phzyx.auth.guards import ensure_authenticated, ensure_permissions, ensure_scopes, ensure_staff
from phzyx.auth.rbac import permission_code


@pytest.mark.unit
def test_argon2_hash_roundtrip() -> None:
    h = hash_password("correct horse battery")
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse battery")
    assert not verify_password(h, "wrong")


@pytest.mark.unit
def test_password_policy_min_length() -> None:
    from phzyx.auth.errors import ValidationAuthError

    ph = PasswordHasher(min_length=10)
    with pytest.raises(ValidationAuthError, match="at least"):
        ph.hash("short")


@pytest.mark.unit
def test_password_policy_rejects_placeholders() -> None:
    from phzyx.auth.errors import ValidationAuthError
    from phzyx.auth.policy import validate_email, validate_username

    ph = PasswordHasher(min_length=10)
    with pytest.raises(ValidationAuthError, match="common|placeholder"):
        ph.hash("password123")
    with pytest.raises(ValidationAuthError, match="email"):
        ph.hash("ops@phzyx.xyz", email="ops@phzyx.xyz")
    with pytest.raises(ValidationAuthError, match="email"):
        ph.hash("opsopsopsop", email="opsopsopsop@phzyx.xyz")  # password == local
    with pytest.raises(ValidationAuthError):
        validate_email("admin@example.com")
    with pytest.raises(ValidationAuthError):
        validate_username("admin")
    assert validate_email("ops@phzyx.xyz") == "ops@phzyx.xyz"
    assert validate_username("athul.dev") == "athul.dev"
    assert ph.hash("a-real-long-password-99").startswith("$argon2")


@pytest.mark.unit
def test_principal_permissions_and_scopes() -> None:
    p = Principal(
        id="1",
        email="a@b.co",
        permissions=frozenset({"posts:create", "posts:list"}),
        scopes=frozenset({"posts:read"}),
    )
    assert p.has_perm("posts:create")
    assert not p.has_perm("posts:delete")
    assert p.has_scope("posts:read")
    assert not p.has_scope("posts:write")
    su = Principal(id="2", is_superuser=True)
    assert su.has_perm("anything:here")
    assert su.has_scope("anything")


@pytest.mark.unit
def test_resolve_permissions_superuser() -> None:
    assert resolve_permissions(is_superuser=True) == frozenset({"*:*"})
    assert resolve_permissions(
        is_superuser=False,
        group_permission_codes=["a:b"],
        direct_permission_codes=["c:d"],
    ) == frozenset({"a:b", "c:d"})


@pytest.mark.unit
def test_seed_resource_permissions() -> None:
    codes = seed_resource_permissions("users")
    assert ("users:list", "users list") in codes
    assert permission_code("users", "delete") == "users:delete"


@pytest.mark.unit
def test_guards() -> None:
    with pytest.raises(UnauthorizedError):
        ensure_authenticated(None)
    with pytest.raises(ForbiddenError):
        ensure_authenticated(Principal(id="1", is_active=False))
    ensure_staff(Principal(id="1", is_staff=True))
    with pytest.raises(ForbiddenError):
        ensure_staff(Principal(id="2"))
    ok = Principal(id="1", permissions=frozenset({"posts:create"}))
    ensure_permissions(ok, ["posts:create"])
    with pytest.raises(ForbiddenError):
        ensure_permissions(ok, ["posts:delete"])
    scoped = Principal(id="1", scopes=frozenset({"api:read"}))
    ensure_scopes(scoped, ["api:read"])
    with pytest.raises(ForbiddenError):
        ensure_scopes(scoped, ["api:write"])


@pytest.mark.unit
def test_decorators_sync_and_async() -> None:
    principal = Principal(
        id="9",
        is_staff=True,
        permissions=frozenset({"x:y"}),
        scopes=frozenset({"s:1"}),
    )

    class Req:
        def __init__(self) -> None:
            self.state = type("S", (), {"principal": principal})()

    @require_auth
    def sync_view(request: Req) -> str:
        return "ok"

    assert sync_view(Req()) == "ok"

    @require_staff
    @require_permissions("x:y")
    @require_scopes("s:1")
    def sync_staff(request: Req) -> str:
        return "staff"

    assert sync_staff(Req()) == "staff"

    @require_auth
    async def async_view(request: Req) -> str:
        return "async-ok"

    assert asyncio.run(async_view(Req())) == "async-ok"


@pytest.mark.unit
def test_models_abstract_and_concrete() -> None:
    assert AbstractUser.__phzyx_table__ is None
    assert User.__phzyx_table__ is not None
    assert User.__phzyx_table__.name == "phzyx_auth_users"


@pytest.mark.unit
def test_principal_from_user() -> None:
    u = User(id=1, email="ops@phzyx.xyz", is_staff=True, is_superuser=False)
    p = principal_from_user(u, permissions={"users:list"}, auth_method="session")
    assert p.id == "1"
    assert p.email == "ops@phzyx.xyz"
    assert p.is_staff
    assert p.has_perm("users:list")


@pytest.mark.unit
def test_auth_config_from_env_dev() -> None:
    cfg = AuthConfig.from_env(production=False)
    assert cfg.secret
    assert cfg.user_model is User


@pytest.mark.unit
def test_auth_config_prod_rejects_weak_secret() -> None:
    with pytest.raises(ValueError, match="production"):
        AuthConfig(secret="change-me", production=True)


@pytest.mark.unit
def test_auth_config_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        AuthConfig(secret="short-dev-secret", production=False)
