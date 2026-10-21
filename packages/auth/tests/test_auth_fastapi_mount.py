"""FastAPI mount_auth integration tests."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from phzyx.auth import AuthConfig, AuthService  # noqa: E402
from phzyx.auth.adapters.fastapi import (  # noqa: E402
    mount_auth,
    require_user,
    websocket_principal,
)
from phzyx.auth.principal import Principal  # noqa: E402

TEST_SECRET = "fastapi-test-secret-key-32bytes!!"  # 32+ bytes


@pytest.fixture
def client() -> TestClient:
    svc = AuthService(
        config=AuthConfig(
            secret=TEST_SECRET,
            production=False,
            cookie_secure=False,
            csrf_protect=False,  # dedicated CSRF test below
        )
    )
    app = FastAPI()
    mount_auth(app, svc)

    @app.get("/protected")
    async def protected(user: Principal = Depends(require_user)) -> dict:  # noqa: B008
        return {"id": user.id, "email": user.email}

    return TestClient(app)


@pytest.mark.unit
def test_register_login_me_protected(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        json={"email": "spa@phzyx.xyz", "password": "longpassword1"},
    )
    assert r.status_code == 200
    r = client.post(
        "/auth/login",
        json={"email": "spa@phzyx.xyz", "password": "longpassword1"},
    )
    assert r.status_code == 200
    assert "phzyx_session" in client.cookies
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "spa@phzyx.xyz"
    prot = client.get("/protected")
    assert prot.status_code == 200
    assert prot.json()["email"] == "spa@phzyx.xyz"
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


@pytest.mark.unit
def test_login_jwt_and_api_key(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "jwt@phzyx.xyz", "password": "longpassword1"},
    )
    r = client.post(
        "/auth/login",
        json={
            "email": "jwt@phzyx.xyz",
            "password": "longpassword1",
            "issue_jwt": True,
        },
    )
    data = r.json()
    assert "access_token" in data
    client.cookies.clear()
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    key = client.post(
        "/auth/api-keys",
        json={"name": "ci", "scopes": ["x:y"]},
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert key.status_code == 200
    raw = key.json()["raw_key"]
    client.cookies.clear()
    me2 = client.get("/auth/me", headers={"X-API-Key": raw})
    assert me2.status_code == 200
    listed = client.get(
        "/auth/api-keys",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["keys"]) == 1
    kid = key.json()["id"]
    deleted = client.delete(
        f"/auth/api-keys/{kid}",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert deleted.status_code == 200


@pytest.mark.unit
def test_refresh_request_id_replays_then_a_different_id_revokes(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "refresh@phzyx.xyz", "password": "longpassword1"},
    )
    login = client.post(
        "/auth/login",
        json={
            "email": "refresh@phzyx.xyz",
            "password": "longpassword1",
            "issue_jwt": True,
        },
    )
    refresh_token = login.json()["refresh_token"]
    first = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Refresh-Request-Id": "retry-1"},
    )
    assert first.status_code == 200
    again = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Refresh-Request-Id": "retry-1"},
    )
    assert again.status_code == 200
    assert again.json()["refresh_token"] == first.json()["refresh_token"]
    assert again.json()["access_token"] == first.json()["access_token"]

    other = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"Refresh-Request-Id": "retry-2"},
    )
    assert other.status_code == 401
    successor = client.post(
        "/auth/refresh",
        json={"refresh_token": first.json()["refresh_token"]},
        headers={"Refresh-Request-Id": "retry-1"},
    )
    assert successor.status_code == 401


@pytest.mark.unit
def test_password_forgot_dev_token(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "reset@phzyx.xyz", "password": "longpassword1"},
    )
    r = client.post("/auth/password/forgot", json={"email": "reset@phzyx.xyz"})
    assert r.status_code == 200
    assert r.json().get("dev_token")
    token = r.json()["dev_token"]
    r2 = client.post(
        "/auth/password/reset",
        json={"token": token, "new_password": "anotherlongpass2"},
    )
    assert r2.status_code == 200
    assert (
        client.post(
            "/auth/login",
            json={"email": "reset@phzyx.xyz", "password": "anotherlongpass2"},
        ).status_code
        == 200
    )


@pytest.mark.unit
def test_csrf_blocks_mutating_session_request() -> None:
    svc = AuthService(
        config=AuthConfig(
            secret=TEST_SECRET,
            production=False,
            cookie_secure=False,
            csrf_protect=True,
        )
    )
    app = FastAPI()
    mount_auth(app, svc)
    c = TestClient(app)
    c.post("/auth/register", json={"email": "csrf@x.co", "password": "longpassword1"})
    login = c.post(
        "/auth/login",
        json={"email": "csrf@x.co", "password": "longpassword1"},
    )
    assert login.status_code == 200
    csrf = login.json().get("csrf_token")
    assert csrf
    # missing header → 403
    bad = c.post("/auth/api-keys", json={"name": "x", "scopes": ["a:b"]})
    assert bad.status_code == 403
    good = c.post(
        "/auth/api-keys",
        json={"name": "x", "scopes": ["a:b"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert good.status_code == 200


@pytest.mark.unit
def test_websocket_principal_from_bearer() -> None:
    svc = AuthService(config=AuthConfig(secret=TEST_SECRET, production=False, cookie_secure=False))
    svc.register("ws@x.co", "longpassword1")
    res = svc.login("ws@x.co", "longpassword1", issue_jwt=True)
    assert res.tokens

    class FakeWS:
        cookies = {}
        headers = {"authorization": f"Bearer {res.tokens.access_token}"}
        closed: int | None = None

        async def close(self, code: int = 1000) -> None:
            self.closed = code

    import asyncio

    p = asyncio.run(websocket_principal(FakeWS(), service=svc))
    assert p.email == "ws@x.co"
