"""Auth configuration — secure defaults, fail-loud in production."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from typing import Any

from phzyx.auth.models import User
from phzyx.auth.password import PasswordHasher

# HS256 / HMAC-SHA256: PyJWT warns below 32 bytes; enforce for all JWT recipes.
MIN_SECRET_BYTES = 32
_WEAK_SECRETS = frozenset({"change-me", "dev", "secret", ""})
_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-min-32b!!"  # 32+ chars, never production


@dataclass
class AuthConfig:
    """Runtime auth settings."""

    secret: str
    user_model: type[Any] = User
    password: PasswordHasher = field(default_factory=PasswordHasher)
    session_cookie_name: str = "phzyx_session"
    csrf_cookie_name: str = "phzyx_csrf"
    csrf_header_name: str = "x-csrf-token"
    session_ttl_seconds: int = 60 * 60 * 24 * 14
    session_idle_seconds: int = 60 * 60 * 24
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    cookie_httponly: bool = True
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    jwt_issuer: str = "phzyx-auth"
    max_failed_logins: int = 8
    lockout_seconds: int = 900
    csrf_protect: bool = True
    production: bool = False
    # WebAuthn / passkeys
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Phzyx"
    webauthn_origin: str = "http://localhost:8000"

    def __post_init__(self) -> None:
        secret = self.secret or ""
        if self.production:
            if secret in _WEAK_SECRETS or len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
                raise ValueError(
                    "AuthConfig.secret must be ≥32 bytes and not a placeholder in production "
                    "(set PHZYX_AUTH_SECRET)"
                )
        else:
            if secret in _WEAK_SECRETS or secret == "change-me":
                warnings.warn(
                    "AuthConfig using weak/dev secret — do not deploy",
                    UserWarning,
                    stacklevel=2,
                )
            if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
                raise ValueError(
                    f"AuthConfig.secret must be at least {MIN_SECRET_BYTES} bytes "
                    "(required for HS256 / session peppering)"
                )

    @classmethod
    def from_env(
        cls,
        *,
        user_model: type[Any] | None = None,
        production: bool | None = None,
    ) -> AuthConfig:
        env_prod = os.environ.get("PHZYX_ENV", "").lower() in {
            "prod",
            "production",
        } or os.environ.get("PHZYX_AUTH_PRODUCTION", "").lower() in {"1", "true", "yes"}
        is_prod = env_prod if production is None else production
        secret = os.environ.get("PHZYX_AUTH_SECRET", "")
        if not secret and not is_prod:
            secret = _DEV_DEFAULT_SECRET
        cookie_secure_env = os.environ.get("PHZYX_AUTH_COOKIE_SECURE")
        if cookie_secure_env is None:
            cookie_secure = is_prod
        else:
            cookie_secure = cookie_secure_env.lower() in {"1", "true", "yes"}
        return cls(
            secret=secret,
            user_model=user_model or User,
            production=is_prod,
            cookie_secure=cookie_secure,
        )
