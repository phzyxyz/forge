"""Principal — authenticated identity for guards and AdminBoard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AuthMethod = Literal["session", "jwt", "api_key", "oauth", "password", "unknown"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Resolved auth context (not the ORM row)."""

    id: str
    email: str | None = None
    username: str | None = None
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    permissions: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[str] = field(default_factory=frozenset)
    scopes: frozenset[str] = field(default_factory=frozenset)
    auth_method: AuthMethod = "unknown"
    raw: Any | None = None

    def has_perm(self, code: str) -> bool:
        if self.is_superuser:
            return True
        if "*:*" in self.permissions:
            return True
        return code in self.permissions

    def has_any_perm(self, *codes: str) -> bool:
        return any(self.has_perm(c) for c in codes)

    def has_all_perms(self, *codes: str) -> bool:
        return all(self.has_perm(c) for c in codes)

    def has_scope(self, scope: str) -> bool:
        if self.is_superuser:
            return True
        if not self.scopes:
            # empty scopes on session = full user perms path
            return True
        return scope in self.scopes or "*:*" in self.scopes

    def has_all_scopes(self, *scopes: str) -> bool:
        return all(self.has_scope(s) for s in scopes)


def principal_from_user(
    user: Any,
    *,
    permissions: frozenset[str] | set[str] | None = None,
    roles: frozenset[str] | set[str] | None = None,
    scopes: frozenset[str] | set[str] | None = None,
    auth_method: AuthMethod = "unknown",
) -> Principal:
    """Build Principal from a User-like object."""
    return Principal(
        id=str(user.id),
        email=getattr(user, "email", None),
        username=getattr(user, "username", None),
        is_active=bool(getattr(user, "is_active", True)),
        is_staff=bool(getattr(user, "is_staff", False)),
        is_superuser=bool(getattr(user, "is_superuser", False)),
        permissions=frozenset(permissions or ()),
        roles=frozenset(roles or ()),
        scopes=frozenset(scopes or ()),
        auth_method=auth_method,
        raw=user,
    )
