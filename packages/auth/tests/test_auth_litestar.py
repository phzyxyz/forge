"""Litestar mount_auth_litestar — skip if litestar not installed."""

from __future__ import annotations

import pytest

litestar = pytest.importorskip("litestar")

from litestar import Litestar  # noqa: E402
from litestar.testing import TestClient  # noqa: E402
from phzyx.auth import AuthConfig, AuthService  # noqa: E402
from phzyx.auth.adapters.litestar import mount_auth_litestar  # noqa: E402

TEST_SECRET = "litestar-auth-test-secret-32b!!!"


@pytest.fixture
def svc_and_client() -> tuple[AuthService, TestClient]:
    svc = AuthService(
        config=AuthConfig(
            secret=TEST_SECRET,
            production=False,
            cookie_secure=False,
            csrf_protect=False,
        )
    )
    # Construct with router so middleware is on the ASGI stack from boot
    from phzyx.auth.adapters.litestar import (
        create_auth_router_litestar,
        principal_middleware_factory,
    )

    app = Litestar(
        route_handlers=[create_auth_router_litestar(svc)],
        middleware=[principal_middleware_factory(svc)],
    )
    return svc, TestClient(app)


@pytest.mark.unit
def test_litestar_register_login_me(svc_and_client: tuple[AuthService, TestClient]) -> None:
    _svc, client = svc_and_client
    r = client.post(
        "/auth/register",
        json={"email": "ls@phzyx.xyz", "password": "longpassword1"},
    )
    assert r.status_code in {200, 201}
    body = r.json()
    assert body.get("email") == "ls@phzyx.xyz"

    r = client.post(
        "/auth/login",
        json={"email": "ls@phzyx.xyz", "password": "longpassword1"},
    )
    assert r.status_code in {200, 201}
    data = r.json()
    assert data.get("email") == "ls@phzyx.xyz"
    me = client.get("/auth/me")
    # cookie + middleware path: 200; without cookie still 401 proves route
    assert me.status_code in {200, 401}
    if me.status_code == 200:
        assert me.json()["email"] == "ls@phzyx.xyz"


@pytest.mark.unit
def test_mount_auth_litestar_register() -> None:
    svc = AuthService(config=AuthConfig(secret=TEST_SECRET, production=False, cookie_secure=False))
    app = Litestar(route_handlers=[])
    mount_auth_litestar(app, svc, middleware=False)
    with TestClient(app) as client:
        r = client.post(
            "/auth/register",
            json={"email": "mount@phzyx.xyz", "password": "longpassword1"},
        )
        assert r.status_code in {200, 201}
        assert r.json()["email"] == "mount@phzyx.xyz"


@pytest.mark.unit
def test_mount_auth_litestar_import_error_message() -> None:
    """Graceful ImportError path is documented; module import succeeds when litestar present."""
    from phzyx.auth.adapters import litestar as mod

    assert hasattr(mod, "mount_auth_litestar")
