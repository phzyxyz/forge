"""Phzyx Auth — identity, sessions, JWT, API keys, guards (batteries optional)."""

from __future__ import annotations

from typing import Any

from phzyx.auth.admin_bridge import PhzyxAuthz, PhzyxFieldAuthz
from phzyx.auth.api_keys import IssuedAPIKey, MemoryAPIKeyStore
from phzyx.auth.audit import AuditLog
from phzyx.auth.config import AuthConfig
from phzyx.auth.durable import durable_auth_service
from phzyx.auth.decorators import (
    require_auth,
    require_permissions,
    require_scopes,
    require_staff,
    require_superuser,
)
from phzyx.auth.errors import (
    AuthError,
    ForbiddenError,
    InvalidCredentialsError,
    LockedError,
    MfaRequiredError,
    UnauthorizedError,
    ValidationAuthError,
)
from phzyx.auth.models import (
    AUTH_MODELS,
    AbstractUser,
    Group,
    MFAFactor,
    OAuthAccount,
    Permission,
    User,
)
from phzyx.auth.oauth import (
    AuthlibOAuthProvider,
    OAuthNotConfiguredError,
    OAuthProviderConfig,
    StaticOAuthProvider,
    build_provider,
    preset_config,
)
from phzyx.auth.orm_stores import (
    HybridUserMap,
    OrmAPIKeyStore,
    OrmPasswordResetStore,
    OrmRateLimiter,
    OrmRefreshStore,
    OrmSessionStore,
    OrmUserRepository,
)
from phzyx.auth.passkeys import HmacPasskeyBackend, default_passkey_backend, sign_hmac_assertion
from phzyx.auth.password import PasswordHasher, generate_token, hash_password, verify_password
from phzyx.auth.principal import Principal, principal_from_user
from phzyx.auth.rate_limit import MemoryRateLimiter, RedisRateLimiter
from phzyx.auth.rbac import has_permission, resolve_permissions, seed_resource_permissions
from phzyx.auth.service import AuthResult, AuthService, MfaChallenge
from phzyx.auth.service_async import AsyncAuthService
from phzyx.auth.sessions import MemorySessionStore
from phzyx.auth.tokens import JwtService, TokenPair

__version__ = "0.1.8"

__all__ = [
    "AUTH_MODELS",
    "AbstractUser",
    "AsyncAuthService",
    "AuditLog",
    "AuthConfig",
    "AuthError",
    "AuthResult",
    "AuthService",
    "AuthlibOAuthProvider",
    "ForbiddenError",
    "Group",
    "HmacPasskeyBackend",
    "InvalidCredentialsError",
    "IssuedAPIKey",
    "JwtService",
    "LockedError",
    "HybridUserMap",
    "MFAFactor",
    "MemoryAPIKeyStore",
    "MemoryRateLimiter",
    "MemorySessionStore",
    "MfaChallenge",
    "MfaRequiredError",
    "OAuthAccount",
    "OAuthNotConfiguredError",
    "OAuthProviderConfig",
    "OrmAPIKeyStore",
    "OrmPasswordResetStore",
    "OrmRateLimiter",
    "OrmRefreshStore",
    "OrmSessionStore",
    "OrmUserRepository",
    "PasswordHasher",
    "Permission",
    "PhzyxAuthz",
    "PhzyxFieldAuthz",
    "Principal",
    "RedisRateLimiter",
    "StaticOAuthProvider",
    "TokenPair",
    "UnauthorizedError",
    "User",
    "ValidationAuthError",
    "__version__",
    "build_provider",
    "create_superuser",
    "default_passkey_backend",
    "durable_auth_service",
    "generate_token",
    "has_permission",
    "hash_password",
    "mount_auth",
    "mount_auth_litestar",
    "preset_config",
    "principal_from_user",
    "require_auth",
    "require_permissions",
    "require_scopes",
    "require_staff",
    "require_superuser",
    "resolve_permissions",
    "sign_hmac_assertion",
    "seed_resource_permissions",
    "verify_password",
]


def __getattr__(name: str) -> Any:
    if name == "mount_auth":
        from phzyx.auth.adapters.fastapi import mount_auth

        return mount_auth
    if name == "mount_auth_litestar":
        from phzyx.auth.adapters.litestar import mount_auth_litestar

        return mount_auth_litestar
    if name == "create_superuser":
        from phzyx.auth.cli import create_superuser

        return create_superuser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
