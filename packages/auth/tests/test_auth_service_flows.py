"""AuthService flows — login, sessions, JWT, API keys, reset, lockout, email."""

from __future__ import annotations

import asyncio

import pytest
from phzyx.auth import (
    AsyncAuthService,
    AuthConfig,
    AuthService,
    InvalidCredentialsError,
    LockedError,
    Principal,
)
from phzyx.auth.admin_bridge import PhzyxAuthz as Bridge
from phzyx.auth.cli import create_superuser
from phzyx.auth.csrf import csrf_valid, issue_csrf_token
from phzyx.auth.guards import ensure_authenticated

TEST_SECRET = "test-secret-key-not-for-prod-32b!"  # 32+ bytes


@pytest.fixture
def svc() -> AuthService:
    return AuthService(config=AuthConfig(secret=TEST_SECRET, production=False))


@pytest.mark.unit
def test_register_login_session_logout(svc: AuthService) -> None:
    p = svc.register("ops@phzyx.xyz", "longpassword1", is_staff=True)
    assert p.email == "ops@phzyx.xyz"
    res = svc.login("ops@phzyx.xyz", "longpassword1")
    assert res.session_token
    assert res.principal.is_staff
    me = svc.principal_from_session(res.session_token)
    assert me is not None and me.id == p.id
    svc.logout(res.session_token)
    assert svc.principal_from_session(res.session_token) is None


@pytest.mark.unit
def test_login_bad_password(svc: AuthService) -> None:
    svc.register("a@b.co", "longpassword1")
    with pytest.raises(InvalidCredentialsError):
        svc.login("a@b.co", "wrongpassword")


@pytest.mark.unit
def test_lockout_after_failures(svc: AuthService) -> None:
    svc.config.max_failed_logins = 3
    svc.register("lock@b.co", "longpassword1")
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            svc.login("lock@b.co", "wrongpasswordxx")
    with pytest.raises(LockedError):
        svc.login("lock@b.co", "longpassword1")


@pytest.mark.unit
def test_jwt_and_refresh(svc: AuthService) -> None:
    svc.register("jwt@b.co", "longpassword1")
    res = svc.login("jwt@b.co", "longpassword1", issue_jwt=True)
    assert res.tokens and res.tokens.access_token
    p = svc.principal_from_bearer(f"Bearer {res.tokens.access_token}")
    assert p is not None and p.email == "jwt@b.co"
    pair = svc.refresh_jwt(res.tokens.refresh_token)
    assert pair.access_token


@pytest.mark.unit
def test_api_key_auth(svc: AuthService) -> None:
    svc.register("key@b.co", "longpassword1")
    u = list(svc.users.values())[0]
    issued = svc.create_api_key(name="ci", user_id=str(u.id), scopes=["posts:read"])
    assert issued.raw_key.startswith("phx_")
    p = svc.principal_from_api_key(issued.raw_key)
    assert p is not None
    assert p.has_scope("posts:read")
    assert p.auth_method == "api_key"
    keys = svc.list_api_keys(str(u.id))
    assert len(keys) == 1
    assert svc.revoke_api_key(issued.id, user_id=str(u.id))
    assert svc.principal_from_api_key(issued.raw_key) is None


@pytest.mark.unit
def test_password_reset(svc: AuthService) -> None:
    svc.register("reset@b.co", "longpassword1")
    token = svc.request_password_reset("reset@b.co")
    assert token
    svc.reset_password(token, "newlongpassword2")
    with pytest.raises(InvalidCredentialsError):
        svc.login("reset@b.co", "longpassword1")
    res = svc.login("reset@b.co", "newlongpassword2")
    assert res.session_token


@pytest.mark.unit
def test_password_reset_unknown_email_no_token(svc: AuthService) -> None:
    assert svc.request_password_reset("nobody@x.co") is None


@pytest.mark.unit
def test_change_password_revokes_sessions(svc: AuthService) -> None:
    svc.register("chg@b.co", "longpassword1")
    res = svc.login("chg@b.co", "longpassword1")
    assert res.session_token
    uid = res.principal.id
    svc.change_password(uid, "longpassword1", "brandnewpass99")
    assert svc.principal_from_session(res.session_token) is None
    ok = svc.login("chg@b.co", "brandnewpass99")
    assert ok.session_token


@pytest.mark.unit
def test_email_verify(svc: AuthService) -> None:
    p = svc.register("v@b.co", "longpassword1")
    user = svc.users["v@b.co"]
    assert not user.email_verified
    tok = svc.request_email_verification(p.id)
    svc.verify_email(tok)
    assert user.email_verified


@pytest.mark.unit
def test_resolve_composite(svc: AuthService) -> None:
    svc.register("c@b.co", "longpassword1")
    res = svc.login("c@b.co", "longpassword1", issue_jwt=True)
    assert res.tokens
    p1 = svc.resolve_principal(authorization=f"Bearer {res.tokens.access_token}")
    p2 = svc.resolve_principal(session_token=res.session_token)
    assert p1 and p2 and p1.id == p2.id


@pytest.mark.unit
def test_async_service_login() -> None:
    svc = AuthService(
        config=AuthConfig(secret="async-secret-key-xx-min-32bytes!", production=False)
    )
    async_svc = AsyncAuthService(inner=svc)

    async def run() -> None:
        await async_svc.register("async@b.co", "longpassword1")
        result = await async_svc.login("async@b.co", "longpassword1")
        assert result.session_token
        p = await async_svc.resolve_principal(session_token=result.session_token)
        assert p is not None

    asyncio.run(run())


@pytest.mark.unit
def test_phzyx_authz_bridge() -> None:
    z = Bridge(require_staff=True)
    assert not z.authorize(None, "list", "users")
    staff = Principal(id="1", is_staff=True, permissions=frozenset({"users:list"}))
    assert z.authorize(staff, "list", "users")
    assert not z.authorize(staff, "delete", "users")
    su = Principal(id="2", is_superuser=True, is_staff=True)
    assert z.authorize(su, "delete", "users")
    non_staff = Principal(id="3", permissions=frozenset({"users:list"}))
    assert not z.authorize(non_staff, "list", "users")


@pytest.mark.unit
def test_body_ensure_authenticated_pattern(svc: AuthService) -> None:
    """In-endpoint check: optional principal then ensure_*."""
    svc.register("body@b.co", "longpassword1")
    res = svc.login("body@b.co", "longpassword1")
    p = svc.principal_from_session(res.session_token)
    assert ensure_authenticated(p).id == res.principal.id


@pytest.mark.unit
def test_csrf_helpers() -> None:
    t = issue_csrf_token()
    assert csrf_valid(t, t)
    assert not csrf_valid(t, "other")


@pytest.mark.unit
def test_create_superuser_cli(svc: AuthService) -> None:
    uid = create_superuser("su@phzyx.xyz", "superlongpass1", service=svc)
    user = svc.users["su@phzyx.xyz"]
    assert str(user.id) == uid
    assert user.is_staff and user.is_superuser


@pytest.mark.unit
def test_secret_too_short_rejected() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        AuthConfig(secret="too-short", production=False)
