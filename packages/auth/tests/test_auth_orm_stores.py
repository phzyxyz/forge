"""ORM-backed auth stores (SQLite)."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.auth import (
    AUTH_MODELS,
    AuthConfig,
    AuthService,
    HybridUserMap,
    JwtService,
    OrmAPIKeyStore,
    OrmPasswordResetStore,
    OrmRateLimiter,
    OrmRefreshStore,
    OrmSessionStore,
    OrmUserRepository,
)
from phzyx.auth.password import PasswordHasher
from phzyx.engine import connect, push_schema
from phzyx.orm.session_sync import Session
from phzyx.schema.types import Dialect


@pytest.fixture
def orm_svc(tmp_path: Path) -> AuthService:
    db = tmp_path / "auth.db"
    url = f"sqlite:///{db}"
    conn, adapter = connect(url)
    try:
        push_schema(list(AUTH_MODELS), conn, adapter, yes=True)
    finally:
        conn.close()

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    repo = OrmUserRepository(session_factory=factory)
    return AuthService(
        config=AuthConfig(
            secret="orm-store-test-secret-key-32b!!!",
            production=False,
            password=PasswordHasher(min_length=5),
        ),
        sessions=OrmSessionStore(session_factory=factory),
        api_keys=OrmAPIKeyStore(session_factory=factory),
        password_reset_store=OrmPasswordResetStore(session_factory=factory),
        users=HybridUserMap(repo=repo),  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_orm_register_login_session_survives_reload(orm_svc: AuthService, tmp_path: Path) -> None:
    orm_svc.register("ops@phzyx.xyz", "longpassword1", is_staff=True)
    res = orm_svc.login("ops@phzyx.xyz", "longpassword1")
    assert res.session_token
    p = orm_svc.principal_from_session(res.session_token)
    assert p is not None and p.email == "ops@phzyx.xyz"

    # new AuthService on same DB sees user + session
    db = tmp_path / "auth.db"
    url = f"sqlite:///{db}"

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    repo = OrmUserRepository(session_factory=factory)
    svc2 = AuthService(
        config=AuthConfig(
            secret="orm-store-test-secret-key-32b!!!",
            production=False,
            password=PasswordHasher(min_length=5),
        ),
        sessions=OrmSessionStore(session_factory=factory),
        api_keys=OrmAPIKeyStore(session_factory=factory),
        password_reset_store=OrmPasswordResetStore(session_factory=factory),
        users=HybridUserMap(repo=repo),  # type: ignore[arg-type]
    )
    p2 = svc2.principal_from_session(res.session_token)
    assert p2 is not None and p2.email == "ops@phzyx.xyz"
    # login with persisted password
    res2 = svc2.login("ops@phzyx.xyz", "longpassword1")
    assert res2.session_token


@pytest.mark.unit
def test_two_services_register_without_sharing_an_id_counter(tmp_path: Path) -> None:
    """A new AuthService must not insert id=1 again just because its counter restarted."""
    db = tmp_path / "ids.db"
    url = f"sqlite:///{db}"
    conn, adapter = connect(url)
    try:
        push_schema(list(AUTH_MODELS), conn, adapter, yes=True)
    finally:
        conn.close()

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    def make() -> AuthService:
        repo = OrmUserRepository(session_factory=factory)
        return AuthService(
            config=AuthConfig(
                secret="orm-store-test-secret-key-32b!!!",
                production=False,
                password=PasswordHasher(min_length=5),
            ),
            users=HybridUserMap(repo=repo),  # type: ignore[arg-type]
        )

    first = make()
    second = make()
    a = first.register("one@phzyx.xyz", "longpassword1")
    b = second.register("two@phzyx.xyz", "longpassword1")
    assert int(a.id) > 0
    assert int(b.id) > 0
    assert a.id != b.id


@pytest.mark.unit
def test_orm_refresh_rate_limit_and_session_revoke(orm_svc: AuthService, tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'auth.db'}"

    def factory() -> Session:
        c, _ = connect(url)
        return Session(c, dialect=Dialect.SQLITE)

    principal = orm_svc.register("refresh@phzyx.xyz", "longpassword1")
    jwt = JwtService(
        secret="orm-store-test-secret-key-32b!!!",
        refresh_store=OrmRefreshStore(session_factory=factory),
    )
    first = jwt.issue_pair(principal)
    rotated = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: principal)
    assert rotated.refresh_token != first.refresh_token
    replayed = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: principal)
    assert replayed.refresh_token == rotated.refresh_token

    limiter = OrmRateLimiter(session_factory=factory)
    assert limiter.hit("login:test", limit=2, window_seconds=60)
    assert limiter.hit("login:test", limit=2, window_seconds=60)
    assert limiter.hit("login:test", limit=2, window_seconds=60) is False

    logged = orm_svc.login("refresh@phzyx.xyz", "longpassword1")
    assert logged.session_token
    assert orm_svc.sessions.revoke_user(principal.id) >= 1
    assert orm_svc.principal_from_session(logged.session_token) is None


@pytest.mark.unit
def test_orm_api_key_and_reset(orm_svc: AuthService) -> None:
    orm_svc.register("k@phzyx.xyz", "longpassword1")
    u = list(orm_svc.users.values())[0]
    issued = orm_svc.create_api_key(name="ci", user_id=str(u.id), scopes=["x:y"])
    p = orm_svc.principal_from_api_key(issued.raw_key)
    assert p is not None and p.has_scope("x:y")
    tok = orm_svc.request_password_reset("k@phzyx.xyz")
    assert tok
    orm_svc.reset_password(tok, "newlongpassword2")
    orm_svc.login("k@phzyx.xyz", "newlongpassword2")
