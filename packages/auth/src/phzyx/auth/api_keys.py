"""API key create / verify (hashed at rest)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from phzyx.auth.crypto import hash_token
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal


@dataclass
class IssuedAPIKey:
    id: str
    name: str
    prefix: str
    raw_key: str  # show once
    scopes: list[str]


@dataclass
class MemoryAPIKeyStore:
    _keys: dict[str, dict[str, Any]] = field(default_factory=dict)
    _seq: int = 0

    def create(
        self,
        *,
        name: str,
        user_id: str | None,
        scopes: list[str],
        secret: str,
        expires_at: datetime | None = None,
    ) -> IssuedAPIKey:
        self._seq += 1
        raw_secret = generate_token(24)
        prefix = f"phx_{raw_secret[:8]}"
        raw_key = f"{prefix}.{raw_secret}"
        kid = str(self._seq)
        self._keys[hash_token(raw_key, secret=secret)] = {
            "id": kid,
            "name": name,
            "prefix": prefix,
            "user_id": user_id,
            "scopes": list(scopes),
            "expires_at": expires_at,
            "revoked": False,
        }
        return IssuedAPIKey(id=kid, name=name, prefix=prefix, raw_key=raw_key, scopes=list(scopes))

    def verify(self, raw_key: str, *, secret: str) -> Principal | None:
        rec = self._keys.get(hash_token(raw_key, secret=secret))
        if rec is None or rec["revoked"]:
            return None
        exp = rec.get("expires_at")
        if exp is not None:
            now = datetime.now(UTC)
            n = now if getattr(exp, "tzinfo", None) else now.replace(tzinfo=None)
            if exp < n:
                return None
        scopes = frozenset(rec["scopes"])
        return Principal(
            id=str(rec["user_id"] or f"key:{rec['id']}"),
            scopes=scopes,
            permissions=scopes,  # API keys: scopes act as granted abilities
            auth_method="api_key",
        )

    def revoke(self, key_id: str, *, user_id: str | None = None) -> bool:
        for rec in self._keys.values():
            if rec["id"] != key_id:
                continue
            if user_id is not None and str(rec.get("user_id")) != str(user_id):
                return False
            rec["revoked"] = True
            return True
        return False

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in self._keys.values():
            if str(rec.get("user_id")) != str(user_id) or rec["revoked"]:
                continue
            out.append(
                {
                    "id": rec["id"],
                    "name": rec["name"],
                    "prefix": rec["prefix"],
                    "scopes": list(rec["scopes"]),
                }
            )
        return out
