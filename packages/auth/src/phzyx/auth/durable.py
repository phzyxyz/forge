"""The auth service an application should construct.

``AuthService(config)`` with no stores is the in-memory stand-in used by
unit tests. It forgets every login when the process exits. Production
refuses that stand-in. It does not, by itself, open a database.

:func:`durable_auth_service` is the wiring. Sessions, users, refresh
tokens, API keys, password-reset tokens, and rate limits are rows in
the caller's database.
"""

from __future__ import annotations

from collections.abc import Callable

from phzyx.auth.config import AuthConfig
from phzyx.auth.orm_stores import (
    HybridUserMap,
    OrmAPIKeyStore,
    OrmPasswordResetStore,
    OrmRateLimiter,
    OrmRefreshStore,
    OrmSessionStore,
    OrmUserRepository,
)
from phzyx.auth.service import AuthService
from phzyx.auth.tokens import JwtService
from phzyx.orm.session_sync import Session

SessionFactory = Callable[[], Session]


def durable_auth_service(
    session_factory: SessionFactory,
    *,
    secret: str,
    production: bool = False,
) -> AuthService:
    """Return an ``AuthService`` whose identity lives in the database.

    ``session_factory`` opens a sync :class:`phzyx.orm.Session` on the
    same database as the application. Push ``AUTH_MODELS`` before the
    first request. ``production=True`` still rejects a weak secret, and
    it does not fall back to process memory.
    """
    config = AuthConfig(
        secret=secret,
        production=production,
        cookie_secure=production,
        csrf_protect=True,
    )
    users = HybridUserMap(repo=OrmUserRepository(session_factory=session_factory))
    refresh_tokens = OrmRefreshStore(session_factory=session_factory)
    return AuthService(
        config=config,
        sessions=OrmSessionStore(session_factory=session_factory),
        api_keys=OrmAPIKeyStore(session_factory=session_factory),
        password_reset_store=OrmPasswordResetStore(session_factory=session_factory),
        rate_limiter=OrmRateLimiter(session_factory=session_factory),
        users=users,  # type: ignore[arg-type]
        jwt=JwtService(secret=secret, refresh_store=refresh_tokens),
    )
