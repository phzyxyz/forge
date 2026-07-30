"""AuthService — register, login, logout, password reset, keys, OAuth, MFA (sync)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from phzyx.auth.api_keys import IssuedAPIKey, MemoryAPIKeyStore
from phzyx.auth.audit import AuditLog
from phzyx.auth.config import AuthConfig
from phzyx.auth.crypto import hash_ip, hash_token
from phzyx.auth.errors import (
    InvalidCredentialsError,
    LockedError,
    UnauthorizedError,
    ValidationAuthError,
)
from phzyx.auth.oauth import OAuthProvider
from phzyx.auth.passkeys import (
    PasskeyBackend,
    default_passkey_backend,
)
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal, principal_from_user
from phzyx.auth.rate_limit import MemoryRateLimiter, RateLimiter
from phzyx.auth.rbac import resolve_permissions, user_is_locked
from phzyx.auth.sessions import MemorySessionStore, SessionStore
from phzyx.auth.tokens import JwtService, TokenPair
from phzyx.auth.totp import generate_totp_secret, provisioning_uri, verify_totp


@dataclass
class MfaChallenge:
    """Pending MFA step after password success (no session yet)."""

    challenge_id: str
    user_id: str
    expires_at: datetime
    ip_hash: str | None = None
    user_agent: str | None = None
    issue_jwt: bool = False


@dataclass
class AuthResult:
    principal: Principal
    session_token: str | None = None
    tokens: TokenPair | None = None
    mfa_challenge_id: str | None = None

    @property
    def mfa_required(self) -> bool:
        return self.mfa_challenge_id is not None and self.session_token is None


@dataclass
class AuthService:
    """Synchronous auth operations.

    Default storage is in-memory (tests / single-process). Swap session store
    or wire ``permission_loader`` for ORM-backed deployments.
    """

    config: AuthConfig
    sessions: SessionStore = field(default_factory=MemorySessionStore)
    users: dict[str, Any] = field(default_factory=dict)  # email -> user-like
    jwt: JwtService | None = None
    api_keys: MemoryAPIKeyStore = field(default_factory=MemoryAPIKeyStore)
    rate_limiter: RateLimiter = field(default_factory=MemoryRateLimiter)
    audit: AuditLog = field(default_factory=AuditLog)
    reset_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    email_verify_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Optional ORM-backed password reset store (OrmPasswordResetStore)
    password_reset_store: Any | None = None
    # OAuth: name -> provider; oauth_accounts keyed by "provider:provider_user_id"
    oauth_providers: dict[str, OAuthProvider] = field(default_factory=dict)
    oauth_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    oauth_accounts: dict[str, dict[str, Any]] = field(default_factory=dict)
    # MFA
    mfa_factors: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # user_id -> factors
    mfa_pending: dict[str, dict[str, Any]] = field(default_factory=dict)  # setup pending by user
    mfa_challenges: dict[str, MfaChallenge] = field(default_factory=dict)
    # Passkeys / WebAuthn
    passkeys: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )  # user_id -> credentials
    passkey_challenges: dict[str, dict[str, Any]] = field(default_factory=dict)
    passkey_backend: PasskeyBackend | None = None
    _id_seq: int = 0
    _factor_seq: int = 0
    permission_loader: Callable[[Any], frozenset[str]] | None = None

    def __post_init__(self) -> None:
        if self.jwt is None:
            self.jwt = JwtService(
                secret=self.config.secret,
                issuer=self.config.jwt_issuer,
                access_ttl=self.config.jwt_access_ttl_seconds,
                refresh_ttl=self.config.jwt_refresh_ttl_seconds,
            )
        if self.passkey_backend is None:
            self.passkey_backend = default_passkey_backend()

    def _next_id(self) -> int:
        self._id_seq += 1
        return self._id_seq

    def _perms_for(self, user: Any) -> frozenset[str]:
        if self.permission_loader:
            return self.permission_loader(user)
        return resolve_permissions(is_superuser=bool(getattr(user, "is_superuser", False)))

    def _principal(self, user: Any, *, method: str = "session") -> Principal:
        return principal_from_user(
            user,
            permissions=self._perms_for(user),
            auth_method=method,  # type: ignore[arg-type]
        )

    def _persist_user(self, user: Any) -> None:
        """Write-through for HybridUserMap / custom user maps."""
        email = str(getattr(user, "email", "") or "").lower()
        if not email:
            return
        with contextlib.suppress(Exception):
            self.users[email] = user

    def register(
        self,
        email: str,
        password: str,
        *,
        username: str | None = None,
        is_staff: bool = False,
        is_superuser: bool = False,
        user_id: int | None = None,
        reject_placeholders: bool | None = None,
        username_soft: bool = False,
    ) -> Principal:
        from phzyx.auth.policy import validate_email, validate_username

        # Explicit reject_placeholders wins (demos/tests). Else superuser/staff
        # default to strict; normal register follows the hasher flag.
        if reject_placeholders is not None:
            strict = reject_placeholders
        elif is_superuser or is_staff:
            strict = True
        else:
            strict = self.config.password.reject_placeholders
        email_n = validate_email(email, reject_placeholders=strict)
        username_n = validate_username(
            username,
            reject_placeholders=strict,
            soft=username_soft,
        )
        if email_n in self.users:
            raise ValidationAuthError("email already registered", field="email")
        uid = user_id if user_id is not None else self._next_id()
        model = self.config.user_model
        # Temporarily honor strict flag for this hash even if hasher is lax in tests.
        hasher = self.config.password
        if strict and not hasher.reject_placeholders:
            from dataclasses import replace

            hasher = replace(hasher, reject_placeholders=True)
        user = model(
            id=uid,
            email=email_n,
            username=username_n,
            password_hash=hasher.hash(
                password,
                email=email_n,
                username=username_n,
            ),
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.users[email_n] = user
        # HybridUserMap may reassign id on insert
        stored = self.users.get(email_n, user)
        self.audit.record("register", actor_id=str(getattr(stored, "id", uid)))
        return self._principal(stored, method="password")

    def login(
        self,
        email: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
        issue_jwt: bool = False,
    ) -> AuthResult:
        email_n = email.strip().lower()
        ip_h = hash_ip(ip)
        if not self.rate_limiter.hit(f"login:ip:{ip_h or 'unknown'}", limit=20, window_seconds=60):
            self.audit.record("login.rate_limited", ip_hash=ip_h)
            raise InvalidCredentialsError("Too many attempts")
        if not self.rate_limiter.hit(f"login:email:{email_n}", limit=10, window_seconds=60):
            raise InvalidCredentialsError("Too many attempts")

        user = self.users.get(email_n)
        if user is None or not getattr(user, "password_hash", None):
            self.audit.record("login.failed", ip_hash=ip_h, email=email_n)
            raise InvalidCredentialsError()
        if not getattr(user, "is_active", True):
            raise InvalidCredentialsError()
        if user_is_locked(user):
            self.audit.record("login.locked", actor_id=str(user.id), ip_hash=ip_h)
            raise LockedError()

        if not self.config.password.verify(user.password_hash, password):
            fails = int(getattr(user, "failed_login_count", 0)) + 1
            user.failed_login_count = fails
            if fails >= self.config.max_failed_logins:
                user.locked_until = (
                    datetime.now(UTC) + timedelta(seconds=self.config.lockout_seconds)
                ).replace(tzinfo=None)
                self.audit.record("login.locked", actor_id=str(user.id), ip_hash=ip_h, fails=fails)
            self._persist_user(user)
            self.audit.record("login.failed", actor_id=str(user.id), ip_hash=ip_h)
            raise InvalidCredentialsError()

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
        self._persist_user(user)
        principal = self._principal(user, method="session")

        # MFA step-up: password ok but session deferred
        if bool(getattr(user, "mfa_enabled", False)):
            challenge_id = generate_token(24)
            self.mfa_challenges[challenge_id] = MfaChallenge(
                challenge_id=challenge_id,
                user_id=str(user.id),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                ip_hash=ip_h,
                user_agent=user_agent,
                issue_jwt=issue_jwt,
            )
            self.audit.record("login.mfa_required", actor_id=str(user.id), ip_hash=ip_h)
            return AuthResult(
                principal=principal,
                session_token=None,
                tokens=None,
                mfa_challenge_id=challenge_id,
            )

        return self._issue_login_result(
            principal,
            ip_hash=ip_h,
            user_agent=user_agent,
            issue_jwt=issue_jwt,
        )

    def _issue_login_result(
        self,
        principal: Principal,
        *,
        ip_hash: str | None,
        user_agent: str | None,
        issue_jwt: bool,
        method: str = "session",
    ) -> AuthResult:
        raw = self.sessions.create(
            principal.id,
            ttl_seconds=self.config.session_ttl_seconds,
            idle_seconds=self.config.session_idle_seconds,
            user_agent=user_agent,
            ip_hash=ip_hash,
            secret=self.config.secret,
        )
        tokens = None
        out_principal = principal
        if issue_jwt and self.jwt:
            tokens = self.jwt.issue_pair(principal)
            out_principal = Principal(
                id=principal.id,
                email=principal.email,
                username=principal.username,
                is_active=principal.is_active,
                is_staff=principal.is_staff,
                is_superuser=principal.is_superuser,
                permissions=principal.permissions,
                roles=principal.roles,
                scopes=principal.scopes,
                auth_method="jwt",
                raw=principal.raw,
            )
        elif method == "oauth":
            out_principal = Principal(
                id=principal.id,
                email=principal.email,
                username=principal.username,
                is_active=principal.is_active,
                is_staff=principal.is_staff,
                is_superuser=principal.is_superuser,
                permissions=principal.permissions,
                roles=principal.roles,
                scopes=principal.scopes,
                auth_method="oauth",
                raw=principal.raw,
            )
        self.audit.record("login.ok", actor_id=out_principal.id, ip_hash=ip_hash)
        return AuthResult(principal=out_principal, session_token=raw, tokens=tokens)

    def logout(self, session_token: str | None) -> None:
        if session_token:
            self.sessions.revoke(session_token, secret=self.config.secret)
            self.audit.record("logout")

    def revoke_all_sessions(self, user_id: str) -> int:
        n = self.sessions.revoke_user(str(user_id))
        self.audit.record("sessions.revoke_all", actor_id=str(user_id), count=n)
        return n

    def principal_from_session(self, session_token: str | None) -> Principal | None:
        if not session_token:
            return None
        rec = self.sessions.get(session_token, secret=self.config.secret)
        if rec is None:
            return None
        self.sessions.touch(
            session_token,
            idle_seconds=self.config.session_idle_seconds,
            secret=self.config.secret,
        )
        user = self._user_by_id(rec.user_id)
        if user is None or not getattr(user, "is_active", True):
            return None
        return self._principal(user, method="session")

    def principal_from_bearer(self, authorization: str | None) -> Principal | None:
        if not authorization or not self.jwt:
            return None
        parts = authorization.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        try:
            return self.jwt.principal_from_access(parts[1])
        except Exception:
            return None

    def principal_from_api_key(self, raw_key: str | None) -> Principal | None:
        if not raw_key:
            return None
        return self.api_keys.verify(raw_key, secret=self.config.secret)

    def resolve_principal(
        self,
        *,
        session_token: str | None = None,
        authorization: str | None = None,
        api_key: str | None = None,
    ) -> Principal | None:
        """Composite resolution order: API key → Bearer → session cookie."""
        p = self.principal_from_api_key(api_key)
        if p:
            return p
        p = self.principal_from_bearer(authorization)
        if p:
            return p
        return self.principal_from_session(session_token)

    def _user_by_id(self, user_id: str) -> Any | None:
        for u in self.users.values():
            if str(u.id) == str(user_id):
                return u
        return None

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        *,
        revoke_sessions: bool = True,
    ) -> None:
        user = self._user_by_id(user_id)
        if user is None or not getattr(user, "password_hash", None):
            raise InvalidCredentialsError()
        if not self.config.password.verify(user.password_hash, current_password):
            raise InvalidCredentialsError()
        user.password_hash = self.config.password.hash(new_password)
        self._persist_user(user)
        if revoke_sessions:
            self.sessions.revoke_user(str(user.id))
        self.audit.record("password.change", actor_id=str(user.id))

    def request_password_reset(self, email: str, *, ip: str | None = None) -> str | None:
        """Anti-enum: callers always show success; raw token only when user exists (dev/tests)."""
        email_n = email.strip().lower()
        if not self.rate_limiter.hit(
            f"forgot:{hash_ip(ip) or email_n}", limit=5, window_seconds=3600
        ):
            return None
        user = self.users.get(email_n)
        if user is None:
            self.audit.record("password.forgot", email=email_n, found=False)
            return None
        if self.password_reset_store is not None:
            raw = self.password_reset_store.create(user_id=str(user.id), secret=self.config.secret)
        else:
            raw = generate_token(32)
            self.reset_tokens[hash_token(raw, secret=self.config.secret)] = {
                "user_id": str(user.id),
                "expires_at": datetime.now(UTC) + timedelta(hours=1),
                "attempts": 0,
                "used": False,
            }
        self.audit.record("password.forgot", actor_id=str(user.id), found=True)
        return raw

    def reset_password(self, token: str, new_password: str) -> None:
        if self.password_reset_store is not None:
            uid = self.password_reset_store.consume(token, secret=self.config.secret)
            if uid is None:
                raise InvalidCredentialsError("Invalid or expired reset token")
            user = self._user_by_id(uid)
            if user is None:
                raise InvalidCredentialsError("Invalid or expired reset token")
            user.password_hash = self.config.password.hash(new_password)
            self._persist_user(user)
            self.sessions.revoke_user(str(user.id))
            self.audit.record("password.reset", actor_id=str(user.id))
            return

        h = hash_token(token, secret=self.config.secret)
        rec = self.reset_tokens.get(h)
        if rec is None or rec["used"]:
            raise InvalidCredentialsError("Invalid or expired reset token")
        rec["attempts"] += 1
        if rec["attempts"] > 5:
            rec["used"] = True
            raise InvalidCredentialsError("Invalid or expired reset token")
        now = datetime.now(UTC)
        exp = rec["expires_at"]
        n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
        if exp < n:
            raise InvalidCredentialsError("Invalid or expired reset token")
        user = self._user_by_id(rec["user_id"])
        if user is None:
            raise InvalidCredentialsError("Invalid or expired reset token")
        user.password_hash = self.config.password.hash(new_password)
        self._persist_user(user)
        rec["used"] = True
        self.sessions.revoke_user(str(user.id))
        self.audit.record("password.reset", actor_id=str(user.id))

    def request_email_verification(self, user_id: str) -> str:
        user = self._user_by_id(user_id)
        if user is None:
            raise ValidationAuthError("user not found")
        raw = generate_token(32)
        self.email_verify_tokens[hash_token(raw, secret=self.config.secret)] = {
            "user_id": str(user.id),
            "expires_at": datetime.now(UTC) + timedelta(hours=24),
            "used": False,
        }
        self.audit.record("email.verify_request", actor_id=str(user.id))
        return raw

    def verify_email(self, token: str) -> None:
        h = hash_token(token, secret=self.config.secret)
        rec = self.email_verify_tokens.get(h)
        if rec is None or rec["used"]:
            raise InvalidCredentialsError("Invalid or expired verification token")
        now = datetime.now(UTC)
        exp = rec["expires_at"]
        n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
        if exp < n:
            raise InvalidCredentialsError("Invalid or expired verification token")
        user = self._user_by_id(rec["user_id"])
        if user is None:
            raise InvalidCredentialsError("Invalid or expired verification token")
        user.email_verified = True
        self._persist_user(user)
        rec["used"] = True
        self.audit.record("email.verified", actor_id=str(user.id))

    def create_api_key(
        self,
        *,
        name: str,
        user_id: str | None,
        scopes: list[str],
    ) -> IssuedAPIKey:
        if self.config.production and not scopes:
            raise ValidationAuthError("scopes required in production", field="scopes")
        issued = self.api_keys.create(
            name=name,
            user_id=user_id,
            scopes=scopes,
            secret=self.config.secret,
        )
        self.audit.record("api_key.create", actor_id=user_id, name=name)
        return issued

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        return self.api_keys.list_for_user(user_id)

    def revoke_api_key(self, key_id: str, *, user_id: str | None = None) -> bool:
        ok = self.api_keys.revoke(key_id, user_id=user_id)
        if ok:
            self.audit.record("api_key.revoke", actor_id=user_id, key_id=key_id)
        return ok

    def refresh_jwt(self, refresh_token: str) -> TokenPair:
        assert self.jwt is not None

        def loader(uid: str) -> Principal:
            user = self._user_by_id(uid)
            if user is None:
                raise UnauthorizedError()
            return self._principal(user, method="jwt")

        try:
            return self.jwt.refresh(refresh_token, principal_loader=loader)
        except ValueError as exc:
            raise InvalidCredentialsError("Invalid refresh token") from exc

    # ── OAuth ──────────────────────────────────────────────────────────────

    def register_oauth_provider(self, provider: OAuthProvider) -> None:
        self.oauth_providers[provider.name] = provider

    def oauth_start(
        self,
        provider: str,
        *,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> dict[str, str]:
        """Create CSRF state and return authorization URL + state."""
        name = provider.strip().lower()
        prov = self.oauth_providers.get(name)
        if prov is None:
            raise ValidationAuthError(f"Unknown OAuth provider '{provider}'", field="provider")
        state = generate_token(24)
        self.oauth_states[state] = {
            "provider": name,
            "redirect_uri": redirect_uri,
            "scopes": list(scopes) if scopes else [],
            "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        }
        url = prov.authorization_url(state=state, redirect_uri=redirect_uri)
        self.audit.record("oauth.start", provider=name)
        return {"authorization_url": url, "state": state}

    def oauth_callback(
        self,
        provider: str,
        *,
        code: str,
        state: str,
        redirect_uri: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        link_user_id: str | None = None,
        issue_jwt: bool = False,
    ) -> AuthResult:
        """Exchange code, link/create user, issue session."""
        name = provider.strip().lower()
        prov = self.oauth_providers.get(name)
        if prov is None:
            raise ValidationAuthError(f"Unknown OAuth provider '{provider}'", field="provider")
        st = self.oauth_states.pop(state, None)
        if st is None or st.get("provider") != name:
            raise InvalidCredentialsError("Invalid OAuth state")
        now = datetime.now(UTC)
        exp = st["expires_at"]
        n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
        if exp < n:
            raise InvalidCredentialsError("OAuth state expired")
        redir = redirect_uri or str(st.get("redirect_uri") or "")
        if not code:
            raise InvalidCredentialsError("Missing OAuth code")
        profile = prov.exchange_code(code=code, redirect_uri=redir)
        provider_user_id = str(profile.get("provider_user_id") or "")
        if not provider_user_id:
            raise InvalidCredentialsError("OAuth provider did not return user id")
        email = (profile.get("email") or "").strip().lower() or None
        granted = profile.get("granted_scopes") or []
        if isinstance(granted, str):
            granted_list = [s for s in granted.split() if s]
        else:
            granted_list = [str(s) for s in granted]

        key = f"{name}:{provider_user_id}"
        existing = self.oauth_accounts.get(key)
        user: Any | None = None
        if existing is not None:
            user = self._user_by_id(str(existing["user_id"]))
        elif link_user_id:
            user = self._user_by_id(link_user_id)
        elif email and email in self.users:
            # same-email link policy
            user = self.users[email]

        if user is None:
            if not email:
                raise ValidationAuthError(
                    "OAuth account has no email and no existing link",
                    field="email",
                )
            # create user without password (provider-trusted email; soft username)
            principal = self.register(
                email,
                generate_token(24) + "Aa1!",  # satisfies policy; never used for oauth-only
                username=profile.get("name"),
                reject_placeholders=False,
                username_soft=True,
            )
            user = self.users[email]
            # clear password so password login does not work unless set later
            user.password_hash = None
            user.email_verified = True
            self._persist_user(user)
            principal = self._principal(user, method="oauth")
        else:
            if not getattr(user, "is_active", True):
                raise InvalidCredentialsError()
            principal = self._principal(user, method="oauth")

        self.oauth_accounts[key] = {
            "provider": name,
            "provider_user_id": provider_user_id,
            "user_id": str(user.id),
            "email": email,
            "granted_scopes": " ".join(granted_list),
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
        ip_h = hash_ip(ip)
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
        self._persist_user(user)
        self.audit.record("oauth.callback", actor_id=str(user.id), provider=name)
        return self._issue_login_result(
            principal,
            ip_hash=ip_h,
            user_agent=user_agent,
            issue_jwt=issue_jwt,
            method="oauth",
        )

    # ── MFA / TOTP ─────────────────────────────────────────────────────────

    def mfa_totp_setup(self, user_id: str) -> dict[str, str]:
        """Begin TOTP enrollment — returns secret + otpauth URI (confirm next)."""
        user = self._user_by_id(user_id)
        if user is None:
            raise ValidationAuthError("user not found")
        secret = generate_totp_secret()
        account = getattr(user, "email", None) or str(user_id)
        uri = provisioning_uri(secret, account_name=str(account), issuer=self.config.jwt_issuer)
        self.mfa_pending[str(user_id)] = {
            "secret": secret,
            "created_at": datetime.now(UTC),
        }
        self.audit.record("mfa.totp.setup", actor_id=str(user_id))
        return {"secret": secret, "provisioning_uri": uri}

    def mfa_totp_confirm(self, user_id: str, code: str) -> None:
        """Confirm enrollment with a valid code; enables MFA on the user."""
        user = self._user_by_id(user_id)
        if user is None:
            raise ValidationAuthError("user not found")
        pending = self.mfa_pending.get(str(user_id))
        if pending is None:
            raise ValidationAuthError("No pending TOTP setup")
        secret = str(pending["secret"])
        if not verify_totp(secret, code):
            raise InvalidCredentialsError("Invalid TOTP code")
        self._factor_seq += 1
        factor = {
            "id": self._factor_seq,
            "user_id": str(user_id),
            "kind": "totp",
            "secret": secret,
            "verified": True,
            "label": "Authenticator",
            "verified_at": datetime.now(UTC).replace(tzinfo=None),
        }
        self.mfa_factors.setdefault(str(user_id), []).append(factor)
        self.mfa_pending.pop(str(user_id), None)
        user.mfa_enabled = True
        self._persist_user(user)
        self.audit.record("mfa.totp.confirm", actor_id=str(user_id))

    def mfa_totp_verify_challenge(
        self,
        challenge_id: str,
        code: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Complete login after MFA code verification."""
        ch = self.mfa_challenges.get(challenge_id)
        if ch is None:
            raise InvalidCredentialsError("Invalid or expired MFA challenge")
        now = datetime.now(UTC)
        exp = ch.expires_at
        n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
        if exp < n:
            self.mfa_challenges.pop(challenge_id, None)
            raise InvalidCredentialsError("Invalid or expired MFA challenge")
        if not self.rate_limiter.hit(f"mfa:{ch.user_id}", limit=5, window_seconds=300):
            raise InvalidCredentialsError("Too many MFA attempts")
        factors = self.mfa_factors.get(ch.user_id) or []
        ok = False
        for fac in factors:
            if (
                fac.get("kind") == "totp"
                and fac.get("verified")
                and verify_totp(str(fac["secret"]), code)
            ):
                ok = True
                break
        if not ok:
            self.audit.record("mfa.totp.fail", actor_id=ch.user_id)
            raise InvalidCredentialsError("Invalid TOTP code")
        self.mfa_challenges.pop(challenge_id, None)
        user = self._user_by_id(ch.user_id)
        if user is None or not getattr(user, "is_active", True):
            raise InvalidCredentialsError()
        principal = self._principal(user, method="session")
        ip_h = hash_ip(ip) if ip else ch.ip_hash
        self.audit.record("mfa.totp.ok", actor_id=ch.user_id)
        return self._issue_login_result(
            principal,
            ip_hash=ip_h,
            user_agent=user_agent or ch.user_agent,
            issue_jwt=ch.issue_jwt,
        )

    # ── Passkeys / WebAuthn ────────────────────────────────────────────────

    def _passkey_backend(self) -> PasskeyBackend:
        assert self.passkey_backend is not None
        return self.passkey_backend

    def passkey_register_begin(self, user_id: str) -> dict[str, Any]:
        user = self._user_by_id(user_id)
        if user is None:
            raise ValidationAuthError("user not found")
        existing = [c["credential_id"] for c in (self.passkeys.get(str(user_id)) or [])]
        opts = self._passkey_backend().registration_options(
            user_id=str(user_id),
            user_name=str(getattr(user, "email", None) or user_id),
            user_display=str(
                getattr(user, "username", None) or getattr(user, "email", None) or user_id
            ),
            exclude_credential_ids=existing,
            rp_id=self.config.webauthn_rp_id,
            rp_name=self.config.webauthn_rp_name,
        )
        challenge = str(opts.get("challenge") or "")
        self.passkey_challenges[f"reg:{user_id}"] = {
            "challenge": challenge,
            "user_id": str(user_id),
            "kind": "registration",
            "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        }
        self.audit.record("passkey.register.begin", actor_id=str(user_id))
        return opts

    def passkey_register_complete(self, user_id: str, credential: dict[str, Any]) -> dict[str, Any]:
        user = self._user_by_id(user_id)
        if user is None:
            raise ValidationAuthError("user not found")
        pending = self.passkey_challenges.pop(f"reg:{user_id}", None)
        if pending is None:
            raise ValidationAuthError("No pending passkey registration")
        try:
            verified = self._passkey_backend().verify_registration(
                credential=credential,
                expected_challenge=str(pending["challenge"]),
                expected_origin=self.config.webauthn_origin,
                expected_rp_id=self.config.webauthn_rp_id,
            )
        except Exception as exc:
            raise InvalidCredentialsError(f"Passkey registration failed: {exc}") from exc
        rec = {
            "credential_id": verified.credential_id,
            "public_key": verified.public_key,
            "sign_count": verified.sign_count,
            "transports": list(verified.transports),
            "user_id": str(user_id),
            "created_at": datetime.now(UTC).replace(tzinfo=None),
        }
        self.passkeys.setdefault(str(user_id), []).append(rec)
        # Also as MFA factor so login.mfa_enabled can use passkeys
        self._factor_seq += 1
        self.mfa_factors.setdefault(str(user_id), []).append(
            {
                "id": self._factor_seq,
                "user_id": str(user_id),
                "kind": "webauthn",
                "credential_id": verified.credential_id,
                "verified": True,
                "label": "Passkey",
            }
        )
        user.mfa_enabled = True
        self._persist_user(user)
        self.audit.record("passkey.register.ok", actor_id=str(user_id))
        return {
            "ok": True,
            "credential_id": verified.credential_id,
            "mfa_enabled": True,
        }

    def passkey_auth_begin(
        self, *, email: str | None = None, user_id: str | None = None
    ) -> dict[str, Any]:
        user = None
        if user_id:
            user = self._user_by_id(user_id)
        elif email:
            user = self.users.get(email.strip().lower())
        if user is None:
            # anti-enum: still return a challenge shape
            opts = self._passkey_backend().authentication_options(
                allow_credential_ids=[],
                rp_id=self.config.webauthn_rp_id,
            )
            self.passkey_challenges[str(opts.get("challenge"))] = {
                "challenge": opts.get("challenge"),
                "user_id": None,
                "kind": "authentication",
                "expires_at": datetime.now(UTC) + timedelta(minutes=5),
            }
            return opts
        uid = str(user.id)
        creds = self.passkeys.get(uid) or []
        allow = [c["credential_id"] for c in creds]
        opts = self._passkey_backend().authentication_options(
            allow_credential_ids=allow,
            rp_id=self.config.webauthn_rp_id,
        )
        challenge = str(opts.get("challenge") or "")
        self.passkey_challenges[challenge] = {
            "challenge": challenge,
            "user_id": uid,
            "kind": "authentication",
            "expires_at": datetime.now(UTC) + timedelta(minutes=5),
            "issue_jwt": False,
        }
        self.audit.record("passkey.auth.begin", actor_id=uid)
        return opts

    def passkey_auth_complete(
        self,
        credential: dict[str, Any],
        *,
        challenge: str | None = None,
        mfa_challenge_id: str | None = None,
        issue_jwt: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        """Complete passwordless login or MFA step-up with a passkey."""
        ch_key = challenge
        mfa_ch: MfaChallenge | None = None
        if mfa_challenge_id:
            mfa_ch = self.mfa_challenges.get(mfa_challenge_id)
            if mfa_ch is None:
                raise InvalidCredentialsError("Invalid or expired MFA challenge")
            # create auth options challenge stored under mfa link
            pending = self.passkey_challenges.get(f"mfa:{mfa_challenge_id}")
            if pending is None:
                raise ValidationAuthError("Call passkey MFA begin first")
            ch_key = str(pending["challenge"])
            user_id = mfa_ch.user_id
            issue_jwt = mfa_ch.issue_jwt
        else:
            if not ch_key:
                # try embed from clientData or top-level
                ch_key = str(
                    credential.get("challenge")
                    or (credential.get("response") or {}).get("challenge")
                    or ""
                )
            pending = self.passkey_challenges.get(str(ch_key)) if ch_key else None
            if pending is None:
                raise InvalidCredentialsError("Invalid or expired passkey challenge")
            user_id = pending.get("user_id")
            if not user_id:
                raise InvalidCredentialsError("Invalid passkey")

        creds = self.passkeys.get(str(user_id)) or []
        cid = str(credential.get("id") or credential.get("rawId") or "")
        stored = next((c for c in creds if c["credential_id"] == cid), None)
        if stored is None:
            raise InvalidCredentialsError("Unknown passkey")
        try:
            verified = self._passkey_backend().verify_authentication(
                credential=credential,
                expected_challenge=str(ch_key),
                expected_origin=self.config.webauthn_origin,
                expected_rp_id=self.config.webauthn_rp_id,
                credential_public_key=str(stored["public_key"]),
                sign_count=int(stored.get("sign_count") or 0),
            )
        except Exception as exc:
            self.audit.record("passkey.auth.fail", actor_id=str(user_id))
            raise InvalidCredentialsError(f"Passkey authentication failed: {exc}") from exc
        stored["sign_count"] = verified.new_sign_count
        # cleanup challenges
        self.passkey_challenges.pop(str(ch_key), None)
        if mfa_challenge_id:
            self.mfa_challenges.pop(mfa_challenge_id, None)
            self.passkey_challenges.pop(f"mfa:{mfa_challenge_id}", None)
        user = self._user_by_id(str(user_id))
        if user is None or not getattr(user, "is_active", True):
            raise InvalidCredentialsError()
        principal = self._principal(user, method="session")
        self.audit.record("passkey.auth.ok", actor_id=str(user_id))
        return self._issue_login_result(
            principal,
            ip_hash=hash_ip(ip),
            user_agent=user_agent,
            issue_jwt=issue_jwt,
        )

    def passkey_mfa_begin(self, mfa_challenge_id: str) -> dict[str, Any]:
        """Begin passkey assertion for an existing MFA challenge (after password)."""
        ch = self.mfa_challenges.get(mfa_challenge_id)
        if ch is None:
            raise InvalidCredentialsError("Invalid or expired MFA challenge")
        creds = self.passkeys.get(ch.user_id) or []
        allow = [c["credential_id"] for c in creds]
        opts = self._passkey_backend().authentication_options(
            allow_credential_ids=allow,
            rp_id=self.config.webauthn_rp_id,
        )
        challenge = str(opts.get("challenge") or "")
        self.passkey_challenges[f"mfa:{mfa_challenge_id}"] = {
            "challenge": challenge,
            "user_id": ch.user_id,
            "kind": "mfa",
        }
        self.passkey_challenges[challenge] = {
            "challenge": challenge,
            "user_id": ch.user_id,
            "kind": "mfa",
            "mfa_challenge_id": mfa_challenge_id,
        }
        return opts

    def list_passkeys(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {
                "credential_id": c["credential_id"],
                "sign_count": c.get("sign_count", 0),
                "transports": c.get("transports") or [],
                "created_at": c.get("created_at"),
            }
            for c in (self.passkeys.get(str(user_id)) or [])
        ]

    def revoke_passkey(self, user_id: str, credential_id: str) -> bool:
        creds = self.passkeys.get(str(user_id)) or []
        keep = [c for c in creds if c["credential_id"] != credential_id]
        if len(keep) == len(creds):
            return False
        self.passkeys[str(user_id)] = keep
        # drop matching mfa factors
        facs = self.mfa_factors.get(str(user_id)) or []
        self.mfa_factors[str(user_id)] = [
            f
            for f in facs
            if not (f.get("kind") == "webauthn" and f.get("credential_id") == credential_id)
        ]
        if not self.mfa_factors.get(str(user_id)) and not keep:
            user = self._user_by_id(user_id)
            if user is not None:
                user.mfa_enabled = False
                self._persist_user(user)
        self.audit.record("passkey.revoke", actor_id=str(user_id), credential_id=credential_id)
        return True
