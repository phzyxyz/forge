"""JWT access + rotating refresh tokens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import jwt
from phzyx.auth.crypto import hash_token
from phzyx.auth.ids import uuid7
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass
class MemoryRefreshStore:
    """In-memory refresh token families for tests and single-process dev."""

    _by_jti: dict[str, dict[str, Any]] = field(default_factory=dict)
    _family_revoked: set[str] = field(default_factory=set)
    _lock: RLock = field(default_factory=RLock)

    def save(
        self,
        *,
        jti: str,
        family_id: str,
        user_id: str,
        expires_at: datetime,
        scopes: str,
        secret: str,
    ) -> None:
        with self._lock:
            self._by_jti[hash_token(jti, secret=secret)] = {
                "family_id": family_id,
                "user_id": user_id,
                "expires_at": expires_at,
                "scopes": scopes,
                "revoked": False,
                "raw_jti": jti,
                "receipt_request_id": None,
                "receipt_access": None,
                "receipt_refresh": None,
                "receipt_expires_in": None,
            }

    def get(self, refresh_token: str, *, secret: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._by_jti.get(hash_token(refresh_token, secret=secret))
            if rec is None:
                return None
            family_revoked = rec["family_id"] in self._family_revoked
            receipt = not family_revoked
            return {
                "family_id": rec["family_id"],
                "user_id": rec["user_id"],
                "expires_at": rec["expires_at"],
                "scopes": rec["scopes"],
                "revoked": bool(rec["revoked"] or family_revoked),
                "receipt_request_id": rec.get("receipt_request_id") if receipt else None,
                "receipt_access": rec.get("receipt_access") if receipt else None,
                "receipt_refresh": rec.get("receipt_refresh") if receipt else None,
                "receipt_expires_in": rec.get("receipt_expires_in") if receipt else None,
            }

    def mark_consumed(self, refresh_token: str, *, secret: str, request_id: str = "") -> bool:
        with self._lock:
            rec = self._by_jti.get(hash_token(refresh_token, secret=secret))
            if rec is None or rec["revoked"] or rec["family_id"] in self._family_revoked:
                return False
            rec["revoked"] = True
            if request_id:
                rec["receipt_request_id"] = request_id
            return True

    def save_receipt(
        self,
        refresh_token: str,
        *,
        secret: str,
        request_id: str,
        access_token: str,
        refresh_token_next: str,
        expires_in: int,
    ) -> None:
        """Store the successor pair under the request id that created it."""
        with self._lock:
            rec = self._by_jti.get(hash_token(refresh_token, secret=secret))
            if rec is None:
                return
            rec["receipt_request_id"] = request_id
            rec["receipt_access"] = access_token
            rec["receipt_refresh"] = refresh_token_next
            rec["receipt_expires_in"] = expires_in

    def consume(self, refresh_token: str, *, secret: str) -> dict[str, Any] | None:
        rec = self.get(refresh_token, secret=secret)
        if rec is None or rec["revoked"]:
            return None
        exp = _as_utc(rec["expires_at"])
        if exp is None or exp < datetime.now(UTC):
            return None
        if not self.mark_consumed(refresh_token, secret=secret):
            return None
        return rec

    def revoke_family(self, family_id: str) -> None:
        with self._lock:
            self._family_revoked.add(family_id)
            for rec in self._by_jti.values():
                if rec["family_id"] == family_id:
                    rec["revoked"] = True
                    rec["receipt_request_id"] = None
                    rec["receipt_access"] = None
                    rec["receipt_refresh"] = None
                    rec["receipt_expires_in"] = None


@dataclass
class JwtService:
    """Issue and verify access JWTs; rotate refresh inside one family.

    A retry is identified by ``Refresh-Request-Id``, not by a clock.
    The same id presented again returns the pair from the first call.
    A different id, or no id, on an already consumed token revokes the family.
    """

    secret: str
    issuer: str = "phzyx-auth"
    access_ttl: int = 900
    refresh_ttl: int = 60 * 60 * 24 * 30
    refresh_store: Any = field(default_factory=MemoryRefreshStore)

    def issue_pair(
        self,
        principal: Principal,
        *,
        scopes: list[str] | None = None,
        family_id: str | None = None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        scope_list = scopes if scopes is not None else sorted(principal.scopes)
        scope_str = " ".join(scope_list)
        access = jwt.encode(
            {
                "sub": principal.id,
                "email": principal.email,
                "is_staff": principal.is_staff,
                "is_superuser": principal.is_superuser,
                "permissions": sorted(principal.permissions),
                "scope": scope_str,
                "iss": self.issuer,
                "iat": now,
                "exp": now + timedelta(seconds=self.access_ttl),
                "amr": [principal.auth_method],
            },
            self.secret,
            algorithm="HS256",
        )
        jti = generate_token(24)
        family = family_id or uuid7()
        self.refresh_store.save(
            jti=jti,
            family_id=family,
            user_id=principal.id,
            expires_at=now + timedelta(seconds=self.refresh_ttl),
            scopes=scope_str,
            secret=self.secret,
        )
        return TokenPair(
            access_token=access,
            refresh_token=jti,
            expires_in=self.access_ttl,
        )

    def decode_access(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self.secret,
            algorithms=["HS256"],
            issuer=self.issuer,
        )

    def principal_from_access(self, token: str) -> Principal:
        data = self.decode_access(token)
        perms = data.get("permissions") or []
        scope = data.get("scope") or ""
        scopes = frozenset(s for s in scope.split() if s)
        return Principal(
            id=str(data["sub"]),
            email=data.get("email"),
            is_staff=bool(data.get("is_staff")),
            is_superuser=bool(data.get("is_superuser")),
            permissions=frozenset(perms),
            scopes=scopes,
            auth_method="jwt",
        )

    def _receipt_for_request(self, record: dict[str, Any], request_id: str) -> TokenPair | None:
        """Successor pair saved for this exact ``Refresh-Request-Id``.

        An empty id never matches. A different id never matches. The pair
        has to have been stored already; a consume that has not saved one
        yet is not a replay.
        """
        if not request_id or record.get("receipt_request_id") != request_id:
            return None
        access_token = record.get("receipt_access")
        next_refresh_token = record.get("receipt_refresh")
        if not access_token or not next_refresh_token:
            return None
        expires_in = record.get("receipt_expires_in") or self.access_ttl
        return TokenPair(
            access_token=str(access_token),
            refresh_token=str(next_refresh_token),
            expires_in=int(expires_in),
        )

    def refresh(
        self,
        refresh_token: str,
        *,
        principal_loader,
        request_id: str | None = None,
    ) -> TokenPair:
        """Rotate refresh inside the same family.

        ``principal_loader(user_id)`` returns a :class:`Principal`.
        ``request_id`` is the ``Refresh-Request-Id`` header. The same id
        returns the pair already issued. Any other presentation of a
        consumed token revokes the family.
        """
        presented_request_id = (request_id or "").strip()
        now = datetime.now(UTC)
        record = self.refresh_store.get(refresh_token, secret=self.secret)
        if record is None:
            raise ValueError("invalid_refresh")

        if record["revoked"]:
            replayed = self._receipt_for_request(record, presented_request_id)
            if replayed is not None:
                return replayed
            self.refresh_store.revoke_family(record["family_id"])
            raise ValueError("invalid_refresh")

        expires_at = _as_utc(record["expires_at"])
        if expires_at is None or expires_at < now:
            raise ValueError("invalid_refresh")

        consumed = self.refresh_store.mark_consumed(
            refresh_token,
            secret=self.secret,
            request_id=presented_request_id,
        )
        if not consumed:
            raced = self.refresh_store.get(refresh_token, secret=self.secret)
            if raced is not None:
                replayed = self._receipt_for_request(raced, presented_request_id)
                if replayed is not None:
                    return replayed
                self.refresh_store.revoke_family(raced["family_id"])
            raise ValueError("invalid_refresh")

        principal = principal_loader(record["user_id"])
        scope_text = record.get("scopes") or ""
        scopes = [scope for scope in scope_text.split() if scope]
        pair = self.issue_pair(principal, scopes=scopes, family_id=record["family_id"])
        if presented_request_id:
            self.refresh_store.save_receipt(
                refresh_token,
                secret=self.secret,
                request_id=presented_request_id,
                access_token=pair.access_token,
                refresh_token_next=pair.refresh_token,
                expires_in=pair.expires_in,
            )
        return pair
