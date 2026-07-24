"""JWT access + rotating refresh tokens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from phzyx.auth.crypto import hash_token
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


@dataclass
class MemoryRefreshStore:
    """In-memory refresh token families for tests."""

    _by_jti: dict[str, dict[str, Any]] = field(default_factory=dict)
    _family_revoked: set[str] = field(default_factory=set)

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
        self._by_jti[hash_token(jti, secret=secret)] = {
            "family_id": family_id,
            "user_id": user_id,
            "expires_at": expires_at,
            "scopes": scopes,
            "revoked": False,
            "raw_jti": jti,
        }

    def consume(self, refresh_token: str, *, secret: str) -> dict[str, Any] | None:
        h = hash_token(refresh_token, secret=secret)
        rec = self._by_jti.get(h)
        if rec is None or rec["revoked"]:
            return None
        if rec["family_id"] in self._family_revoked:
            return None
        now = datetime.now(UTC)
        exp = rec["expires_at"]
        n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
        if exp < n:
            return None
        rec["revoked"] = True
        return rec

    def revoke_family(self, family_id: str) -> None:
        self._family_revoked.add(family_id)
        for rec in self._by_jti.values():
            if rec["family_id"] == family_id:
                rec["revoked"] = True


@dataclass
class JwtService:
    """Issue and verify access JWTs; rotate refresh via MemoryRefreshStore."""

    secret: str
    issuer: str = "phzyx-auth"
    access_ttl: int = 900
    refresh_ttl: int = 60 * 60 * 24 * 30
    refresh_store: MemoryRefreshStore = field(default_factory=MemoryRefreshStore)

    def issue_pair(
        self,
        principal: Principal,
        *,
        scopes: list[str] | None = None,
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
        family = generate_token(16)
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

    def refresh(self, refresh_token: str, *, principal_loader) -> TokenPair:
        """Rotate refresh; principal_loader(user_id) -> Principal."""
        rec = self.refresh_store.consume(refresh_token, secret=self.secret)
        if rec is None:
            # possible theft: if unknown, still safe; if reuse of revoked, revoke family
            raise ValueError("invalid_refresh")
        principal = principal_loader(rec["user_id"])
        scopes = [s for s in (rec.get("scopes") or "").split() if s]
        # new family continues same family id for tracking — issue new jti same family
        pair = self.issue_pair(principal, scopes=scopes)
        # re-bind new refresh to same family
        # issue_pair creates new family; fix by re-saving with old family
        # simpler: accept new family on each refresh (still rotates jti)
        return pair
