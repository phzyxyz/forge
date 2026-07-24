"""Opaque session store — memory default, ORM-backed optional."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from phzyx.auth.crypto import hash_token
from phzyx.auth.password import generate_token


@dataclass
class SessionRecord:
    token_hash: str
    user_id: str
    expires_at: datetime
    idle_expires_at: datetime | None = None
    revoked: bool = False
    user_agent: str | None = None
    ip_hash: str | None = None


class SessionStore(Protocol):
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
        """Create session; return raw token for cookie."""
        ...

    def get(self, raw_token: str, *, secret: str = "") -> SessionRecord | None: ...

    def touch(self, raw_token: str, *, idle_seconds: int, secret: str = "") -> None: ...

    def revoke(self, raw_token: str, *, secret: str = "") -> None: ...

    def revoke_user(self, user_id: str) -> int: ...


@dataclass
class MemorySessionStore:
    """Process-local sessions (tests + single-process apps)."""

    _by_hash: dict[str, SessionRecord] = field(default_factory=dict)
    _id_seq: int = 0

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
        now = datetime.now(UTC)
        idle = now + timedelta(seconds=idle_seconds) if idle_seconds is not None else None
        rec = SessionRecord(
            token_hash=hash_token(raw, secret=secret),
            user_id=str(user_id),
            expires_at=now + timedelta(seconds=ttl_seconds),
            idle_expires_at=idle,
            user_agent=user_agent,
            ip_hash=ip_hash,
        )
        self._by_hash[rec.token_hash] = rec
        return raw

    def get(self, raw_token: str, *, secret: str = "") -> SessionRecord | None:
        h = hash_token(raw_token, secret=secret)
        rec = self._by_hash.get(h)
        if rec is None or rec.revoked:
            return None
        now = datetime.now(UTC)
        exp = rec.expires_at
        if exp.tzinfo is None:
            now = now.replace(tzinfo=None)
        if exp < now:
            return None
        if rec.idle_expires_at is not None:
            idle = rec.idle_expires_at
            n = now if idle.tzinfo else now.replace(tzinfo=None)
            if idle < n:
                return None
        return rec

    def touch(self, raw_token: str, *, idle_seconds: int, secret: str = "") -> None:
        rec = self.get(raw_token, secret=secret)
        if rec is None:
            return
        now = datetime.now(UTC)
        if rec.idle_expires_at is not None and rec.idle_expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        rec.idle_expires_at = now + timedelta(seconds=idle_seconds)

    def revoke(self, raw_token: str, *, secret: str = "") -> None:
        h = hash_token(raw_token, secret=secret)
        rec = self._by_hash.get(h)
        if rec:
            rec.revoked = True

    def revoke_user(self, user_id: str) -> int:
        n = 0
        for rec in self._by_hash.values():
            if rec.user_id == str(user_id) and not rec.revoked:
                rec.revoked = True
                n += 1
        return n
