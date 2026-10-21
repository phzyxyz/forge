"""Default auth models — subclass AbstractUser to customize.

Flags ``is_staff`` / ``is_superuser`` are **not** separate user types
(Django-compatible). Use Groups + Permissions for RBAC.
"""

from __future__ import annotations

from datetime import datetime

from phzyx.orm import Field, Model


class AbstractUser(Model):
    """Base user fields for identity + security bookkeeping."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    username: str | None = Field(default=None, unique=True)
    password_hash: str | None = Field(default=None, admin_exclude=True)
    is_active: bool = Field(default=True)
    is_staff: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    email_verified: bool = Field(default=False)
    mfa_enabled: bool = Field(default=False)
    failed_login_count: int = Field(default=0)
    locked_until: datetime | None = Field(default=None)
    last_login_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)

    class Meta:
        abstract = True


class User(AbstractUser):
    """Concrete default user table (override via AuthConfig.user_model)."""

    class Meta:
        table = "phzyx_auth_users"
        register = False


class Group(Model):
    """Named group / role container."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    slug: str = Field(unique=True, index=True)

    class Meta:
        table = "phzyx_auth_groups"
        register = False


class Permission(Model):
    """Permission code e.g. ``posts:create``."""

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    label: str = Field(default="")

    class Meta:
        table = "phzyx_auth_permissions"
        register = False


class UserGroup(Model):
    """User ↔ Group membership."""

    user_id: int = Field(primary_key=True, foreign_key="phzyx_auth_users.id")
    group_id: int = Field(primary_key=True, foreign_key="phzyx_auth_groups.id")

    class Meta:
        table = "phzyx_auth_user_groups"
        register = False


class GroupPermission(Model):
    """Group ↔ Permission membership."""

    group_id: int = Field(primary_key=True, foreign_key="phzyx_auth_groups.id")
    permission_id: int = Field(primary_key=True, foreign_key="phzyx_auth_permissions.id")

    class Meta:
        table = "phzyx_auth_group_permissions"
        register = False


class UserPermission(Model):
    """Direct user permissions (beyond groups)."""

    user_id: int = Field(primary_key=True, foreign_key="phzyx_auth_users.id")
    permission_id: int = Field(primary_key=True, foreign_key="phzyx_auth_permissions.id")

    class Meta:
        table = "phzyx_auth_user_permissions"
        register = False


class AuthSession(Model):
    """Server-side opaque session (cookie value is raw id; only hash stored)."""

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(index=True, foreign_key="phzyx_auth_users.id")
    expires_at: datetime = Field()
    idle_expires_at: datetime | None = Field(default=None)
    revoked_at: datetime | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    ip_hash: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_sessions"
        register = False


class RefreshToken(Model):
    """Rotating refresh token family (JWT recipe)."""

    id: int | None = Field(default=None, primary_key=True)
    jti_hash: str = Field(unique=True, index=True)
    family_id: str = Field(index=True)
    user_id: int = Field(index=True, foreign_key="phzyx_auth_users.id")
    expires_at: datetime = Field()
    revoked_at: datetime | None = Field(default=None)
    scopes: str = Field(default="")  # space-separated
    # Short-lived lost-response receipt. Cleared when the grace window ends
    # or the family is revoked. Holds the replacement tokens so a retry of
    # the same refresh token returns the same pair instead of looking like theft.
    receipt_access: str | None = Field(default=None, admin_exclude=True)
    receipt_refresh: str | None = Field(default=None, admin_exclude=True)
    receipt_expires_at: datetime | None = Field(default=None)
    receipt_expires_in: int | None = Field(default=None)
    created_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_refresh_tokens"
        register = False


class APIKey(Model):
    """Hashed API key with scopes."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field()
    prefix: str = Field(index=True)
    key_hash: str = Field(unique=True)
    user_id: int | None = Field(default=None, foreign_key="phzyx_auth_users.id")
    scopes: str = Field(default="")  # space-separated
    expires_at: datetime | None = Field(default=None)
    revoked_at: datetime | None = Field(default=None)
    last_used_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_api_keys"
        register = False


class PasswordResetToken(Model):
    """Single-use password reset token (hashed)."""

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(index=True, foreign_key="phzyx_auth_users.id")
    expires_at: datetime = Field()
    used_at: datetime | None = Field(default=None)
    attempts: int = Field(default=0)
    created_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_password_resets"
        register = False


class AuditEvent(Model):
    """Auth audit trail."""

    id: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    actor_id: str | None = Field(default=None)
    ip_hash: str | None = Field(default=None)
    meta_json: str = Field(default="{}")
    created_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_audit"
        register = False


class OAuthAccount(Model):
    """Linked external IdP identity (Google, GitHub, …)."""

    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    provider_user_id: str = Field(index=True)
    user_id: int = Field(index=True, foreign_key="phzyx_auth_users.id")
    email: str | None = Field(default=None)
    granted_scopes: str = Field(default="")  # space-separated
    access_token_enc: str | None = Field(default=None, admin_exclude=True)
    refresh_token_enc: str | None = Field(default=None, admin_exclude=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_oauth_accounts"
        register = False


class RateLimitBucket(Model):
    """Fixed-window counter for :class:`OrmRateLimiter`. ``bucket`` is the key."""

    bucket: str = Field(primary_key=True)
    hits: int = Field(default=0)

    class Meta:
        table = "phzyx_auth_rate_limits"
        register = False


class MFAFactor(Model):
    """Second factor (TOTP / future WebAuthn)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="phzyx_auth_users.id")
    kind: str = Field(default="totp")  # totp | webauthn
    secret_encrypted: str = Field(
        admin_exclude=True
    )  # base32 secret (pepper-hashed store optional)
    label: str = Field(default="Authenticator")
    verified: bool = Field(default=False)
    created_at: datetime | None = Field(default=None)
    verified_at: datetime | None = Field(default=None)

    class Meta:
        table = "phzyx_auth_mfa_factors"
        register = False


AUTH_MODELS = (
    User,
    Group,
    Permission,
    UserGroup,
    GroupPermission,
    UserPermission,
    AuthSession,
    RefreshToken,
    APIKey,
    PasswordResetToken,
    RateLimitBucket,
    AuditEvent,
    OAuthAccount,
    MFAFactor,
)
