"""Production boot refuses memory auth stores, HMAC passkeys, and AllowAll."""

from __future__ import annotations

import pytest
from phzyx.admin.auth import AllowAll, refuse_allow_all
from phzyx.admin.service import AdminService
from phzyx.auth import AuthConfig, AuthService, HmacPasskeyBackend
from phzyx.auth.passkeys import default_passkey_backend

SECRET = "production-guard-secret-key-32b!!"


@pytest.mark.unit
def test_production_auth_refuses_memory_defaults() -> None:
    with pytest.raises(RuntimeError, match="in-memory"):
        AuthService(config=AuthConfig(secret=SECRET, production=True))


@pytest.mark.unit
def test_default_passkey_backend_is_not_hmac() -> None:
    backend = default_passkey_backend()
    assert not isinstance(backend, HmacPasskeyBackend)


@pytest.mark.unit
def test_allow_all_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_ENV", "production")
    with pytest.raises(RuntimeError, match="AllowAll"):
        refuse_allow_all(AllowAll())
    with pytest.raises(RuntimeError, match="AllowAll"):
        AdminService(resources={}, session=object(), authz=AllowAll())  # type: ignore[arg-type]
    try:
        from phzyx.admin.litestar import AdminBoardConfig
    except ImportError:
        AdminBoardConfig = None
    if AdminBoardConfig is not None:
        with pytest.raises(RuntimeError, match="AllowAll"):
            AdminBoardConfig(
                models=[],
                session_factory=lambda: object(),  # type: ignore[arg-type,return-value]
                authz=AllowAll(),
            )
