"""durable_auth_service is the production wiring, and it is not memory."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.auth import (
    AUTH_MODELS,
    AuthConfig,
    AuthService,
    HybridUserMap,
    MemorySessionStore,
    OrmAPIKeyStore,
    OrmPasswordResetStore,
    OrmRateLimiter,
    OrmRefreshStore,
    OrmSessionStore,
    durable_auth_service,
)
from phzyx.engine import connect, push_schema
from phzyx.orm.session_sync import Session
from phzyx.schema.types import Dialect

_SECRET = "production-guard-secret-key-32b!!"


@pytest.mark.unit
def test_config_only_auth_service_is_still_in_memory() -> None:
    service = AuthService(config=AuthConfig(secret=_SECRET, production=False))
    assert isinstance(service.sessions, MemorySessionStore)
    assert isinstance(service.users, dict)


@pytest.mark.unit
def test_durable_auth_service_uses_the_database_in_production(tmp_path: Path) -> None:
    db = tmp_path / "auth.db"
    url = f"sqlite:///{db}"
    conn, adapter = connect(url)
    try:
        push_schema(list(AUTH_MODELS), conn, adapter, yes=True)
    finally:
        conn.close()

    def factory() -> Session:
        opened, _adapter = connect(url)
        return Session(opened, dialect=Dialect.SQLITE)

    service = durable_auth_service(factory, secret=_SECRET, production=True)
    assert isinstance(service.sessions, OrmSessionStore)
    assert isinstance(service.users, HybridUserMap)
    assert isinstance(service.api_keys, OrmAPIKeyStore)
    assert isinstance(service.password_reset_store, OrmPasswordResetStore)
    assert isinstance(service.rate_limiter, OrmRateLimiter)
    assert service.jwt is not None
    assert isinstance(service.jwt.refresh_store, OrmRefreshStore)

    registered = service.register("ada@phzyx.xyz", "longpassword1")
    assert int(registered.id) > 0

    # A second process-shaped service reads the same rows. Nothing stayed
    # in the first service's memory.
    again = durable_auth_service(factory, secret=_SECRET, production=True)
    logged_in = again.login("ada@phzyx.xyz", "longpassword1")
    assert logged_in.session_token
    seen = again.principal_from_session(logged_in.session_token)
    assert seen is not None and seen.email == "ada@phzyx.xyz"
