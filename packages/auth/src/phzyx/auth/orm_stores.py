"""ORM-backed session / API key / password-reset / user stores (phzyx-orm Session)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from phzyx.auth.api_keys import IssuedAPIKey
from phzyx.auth.crypto import hash_token
from phzyx.auth.models import APIKey, AuthSession, PasswordResetToken, User
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal
from phzyx.auth.sessions import SessionRecord
from phzyx.orm.expr import eq
from phzyx.orm.session_sync import Session

SessionFactory = Callable[[], Session]


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _next_id(session: Session, model: type, pk: str = "id") -> int:
    rows = session.query(model, limit=10_000)
    if not rows:
        return 1
    return max(int(getattr(r, pk)) for r in rows) + 1


@dataclass
class OrmSessionStore:
    """Persist opaque sessions in ``AuthSession`` table."""

    session_factory: SessionFactory

    def create(
        self,
        user_id: str,
        *,
        ttl_seconds: int,
        idle_seconds: int | None = None,
        user_agent: str | None = None,
        ip_hash: str | None = None,
        secret: str = "",
    ) -> str:
        raw = generate_token(32)
        now = _now_naive()
        idle = now + timedelta(seconds=idle_seconds) if idle_seconds is not None else None
        session = self.session_factory()
        try:
            row = AuthSession(
                id=_next_id(session, AuthSession),
                token_hash=hash_token(raw, secret=secret),
                user_id=int(user_id),
                expires_at=now + timedelta(seconds=ttl_seconds),
                idle_expires_at=idle,
                revoked_at=None,
                user_agent=user_agent,
                ip_hash=ip_hash,
                created_at=now,
            )
            session.add(row)
            session.commit()
        finally:
            session.close()
        return raw

    def get(self, raw_token: str, *, secret: str = "") -> SessionRecord | None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.revoked_at is not None:
                return None
            now = _now_naive()
            exp = row.expires_at
            if getattr(exp, "tzinfo", None) is not None:
                exp = exp.replace(tzinfo=None)
            if exp < now:
                return None
            idle = row.idle_expires_at
            if idle is not None:
                if getattr(idle, "tzinfo", None) is not None:
                    idle = idle.replace(tzinfo=None)
                if idle < now:
                    return None
            return SessionRecord(
                token_hash=row.token_hash,
                user_id=str(row.user_id),
                expires_at=row.expires_at,
                idle_expires_at=row.idle_expires_at,
                revoked=False,
                user_agent=row.user_agent,
                ip_hash=row.ip_hash,
            )
        finally:
            session.close()

    def touch(self, raw_token: str, *, idle_seconds: int, secret: str = "") -> None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return
            row = rows[0]
            idle = _now_naive() + timedelta(seconds=idle_seconds)
            session.update(row, idle_expires_at=idle)
            session.commit()
        finally:
            session.close()

    def revoke(self, raw_token: str, *, secret: str = "") -> None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return
            session.update(rows[0], revoked_at=_now_naive())
            session.commit()
        finally:
            session.close()

    def revoke_user(self, user_id: str) -> int:
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("user_id", int(user_id))], limit=10_000)
            n = 0
            now = _now_naive()
            for row in rows:
                if row.revoked_at is None:
                    session.update(row, revoked_at=now)
                    n += 1
            session.commit()
            return n
        finally:
            session.close()


@dataclass
class OrmAPIKeyStore:
    """Persist API keys in ``APIKey`` table."""

    session_factory: SessionFactory

    def create(
        self,
        *,
        name: str,
        user_id: str | None,
        scopes: list[str],
        secret: str,
        expires_at: datetime | None = None,
    ) -> IssuedAPIKey:
        raw_secret = generate_token(24)
        prefix = f"phx_{raw_secret[:8]}"
        raw_key = f"{prefix}.{raw_secret}"
        session = self.session_factory()
        try:
            kid = _next_id(session, APIKey)
            row = APIKey(
                id=kid,
                name=name,
                prefix=prefix,
                key_hash=hash_token(raw_key, secret=secret),
                user_id=int(user_id) if user_id is not None else None,
                scopes=" ".join(scopes),
                expires_at=expires_at,
                revoked_at=None,
                last_used_at=None,
                created_at=_now_naive(),
            )
            session.add(row)
            session.commit()
            return IssuedAPIKey(
                id=str(kid), name=name, prefix=prefix, raw_key=raw_key, scopes=list(scopes)
            )
        finally:
            session.close()

    def verify(self, raw_key: str, *, secret: str) -> Principal | None:
        h = hash_token(raw_key, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("key_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.revoked_at is not None:
                return None
            exp = row.expires_at
            if exp is not None:
                now = _now_naive()
                e = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
                if e < now:
                    return None
            scopes = frozenset(s for s in (row.scopes or "").split() if s)
            session.update(row, last_used_at=_now_naive())
            session.commit()
            return Principal(
                id=str(row.user_id or f"key:{row.id}"),
                scopes=scopes,
                permissions=scopes,
                auth_method="api_key",
            )
        finally:
            session.close()

    def revoke(self, key_id: str, *, user_id: str | None = None) -> bool:
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("id", int(key_id))], limit=1)
            if not rows:
                return False
            row = rows[0]
            if user_id is not None and str(row.user_id) != str(user_id):
                return False
            session.update(row, revoked_at=_now_naive())
            session.commit()
            return True
        finally:
            session.close()

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("user_id", int(user_id))], limit=1000)
            out = []
            for row in rows:
                if row.revoked_at is not None:
                    continue
                out.append(
                    {
                        "id": str(row.id),
                        "name": row.name,
                        "prefix": row.prefix,
                        "scopes": [s for s in (row.scopes or "").split() if s],
                    }
                )
            return out
        finally:
            session.close()


@dataclass
class OrmPasswordResetStore:
    """Persist password reset tokens (used by AuthService when injected)."""

    session_factory: SessionFactory

    def create(self, *, user_id: str, secret: str, ttl_hours: int = 1) -> str:
        raw = generate_token(32)
        session = self.session_factory()
        try:
            row = PasswordResetToken(
                id=_next_id(session, PasswordResetToken),
                token_hash=hash_token(raw, secret=secret),
                user_id=int(user_id),
                expires_at=_now_naive() + timedelta(hours=ttl_hours),
                used_at=None,
                attempts=0,
                created_at=_now_naive(),
            )
            session.add(row)
            session.commit()
            return raw
        finally:
            session.close()

    def consume(self, token: str, *, secret: str, max_attempts: int = 5) -> str | None:
        """Return user_id if valid; mark used. None if invalid."""
        h = hash_token(token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(PasswordResetToken, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.used_at is not None:
                return None
            attempts = int(row.attempts or 0) + 1
            if attempts > max_attempts:
                session.update(row, attempts=attempts, used_at=_now_naive())
                session.commit()
                return None
            exp = row.expires_at
            e = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
            if e < _now_naive():
                session.update(row, attempts=attempts)
                session.commit()
                return None
            session.update(row, attempts=attempts, used_at=_now_naive())
            session.commit()
            return str(row.user_id)
        finally:
            session.close()


@dataclass
class OrmUserRepository:
    """Load/save ``phzyx.auth.models.User`` rows."""

    session_factory: SessionFactory
    _id_seq: int = 0

    def all_by_email(self) -> dict[str, User]:
        session = self.session_factory()
        try:
            rows = session.query(User, limit=50_000)
            return {str(u.email).lower(): u for u in rows}
        finally:
            session.close()

    def get_by_email(self, email: str) -> User | None:
        session = self.session_factory()
        try:
            rows = session.query(User, where=[eq("email", email.strip().lower())], limit=1)
            return rows[0] if rows else None
        finally:
            session.close()

    def get_by_id(self, user_id: str) -> User | None:
        session = self.session_factory()
        try:
            return session.get(User, int(user_id))
        finally:
            session.close()

    def save_new(self, user: User) -> User:
        session = self.session_factory()
        try:
            if user.id is None or int(user.id) == 0:
                user = User(
                    id=_next_id(session, User),
                    email=user.email,
                    username=user.username,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    is_staff=user.is_staff,
                    is_superuser=user.is_superuser,
                    email_verified=user.email_verified,
                    mfa_enabled=user.mfa_enabled,
                    failed_login_count=user.failed_login_count,
                    locked_until=user.locked_until,
                    last_login_at=user.last_login_at,
                    created_at=user.created_at or _now_naive(),
                    updated_at=_now_naive(),
                )
            session.add(user)
            session.commit()
            return user
        finally:
            session.close()

    def update(self, user: User, **values: Any) -> User:
        session = self.session_factory()
        try:
            live = session.get(User, int(user.id))
            if live is None:
                raise KeyError(user.id)
            updated = session.update(live, **values, updated_at=_now_naive())
            session.commit()
            return updated
        finally:
            session.close()


@dataclass
class HybridUserMap:
    """Dict-like email→user that reads through to ORM and keeps a write-through cache."""

    repo: OrmUserRepository
    _cache: dict[str, Any] = field(default_factory=dict)
    loaded: bool = False

    def _ensure(self) -> None:
        if not self.loaded:
            self._cache = dict(self.repo.all_by_email())
            self.loaded = True

    def get(self, email: str, default: Any = None) -> Any:
        """Prefer live ORM row so admin/seed toggles (e.g. mfa_enabled) are not stale."""
        email_n = str(email).strip().lower()
        live = self.repo.get_by_email(email_n)
        if live is not None:
            self._cache[email_n] = live
            self.loaded = True
            return live
        self._ensure()
        return self._cache.get(email_n, default)

    def __contains__(self, email: object) -> bool:
        self._ensure()
        return str(email) in self._cache

    def __setitem__(self, email: str, user: Any) -> None:
        self._ensure()
        # persist if new
        if email not in self._cache:
            if not getattr(user, "id", None):
                user = self.repo.save_new(user)
            else:
                try:
                    self.repo.save_new(user)
                except Exception:
                    self.repo.update(user)
        else:
            # update mutable fields
            with contextlib.suppress(Exception):
                self.repo.update(
                    user,
                    password_hash=user.password_hash,
                    failed_login_count=getattr(user, "failed_login_count", 0),
                    locked_until=getattr(user, "locked_until", None),
                    last_login_at=getattr(user, "last_login_at", None),
                    is_active=getattr(user, "is_active", True),
                    email_verified=getattr(user, "email_verified", False),
                    mfa_enabled=getattr(user, "mfa_enabled", False),
                )
        self._cache[email] = user

    def values(self) -> Any:
        self._ensure()
        return self._cache.values()

    def __len__(self) -> int:
        self._ensure()
        return len(self._cache)
