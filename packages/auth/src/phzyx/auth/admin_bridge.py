"""AdminBoard Authz bridge — map Principal permissions to resource:action."""

from __future__ import annotations

from typing import Any

from phzyx.auth.principal import Principal


class PhzyxAuthz:
    """Implements phzyx.admin.auth.Authz protocol.

    Rules:
    - superuser / ``*:*`` → allow all
    - staff required for admin access when ``require_staff=True``
    - permission code ``{resource}:{action}`` or ``{resource}:*``
    """

    def __init__(self, *, require_staff: bool = True) -> None:
        self.require_staff = require_staff

    def authorize(self, principal: Any | None, action: str, resource: str) -> bool:
        if principal is None:
            return False
        is_super = bool(getattr(principal, "is_superuser", False))
        if is_super:
            return True
        if self.require_staff and not bool(getattr(principal, "is_staff", False)):
            return False
        perms = getattr(principal, "permissions", None) or frozenset()
        pset = set(perms) if isinstance(perms, (set, frozenset, list, tuple)) else set()
        if "*:*" in pset or f"{resource}:*" in pset:
            return True
        code = f"{resource}:{action}"
        if code in pset:
            return True
        # bulk actions use bulk:name
        return bool(action.startswith("bulk:") and f"{resource}:bulk" in pset)


def principal_as_admin(principal: Principal | None) -> Principal | None:
    """Identity passthrough for AdminBoard service principal field."""
    return principal


class PhzyxFieldAuthz:
    """Field-level RBAC: ``{resource}:field:{name}:read|write`` or ``*:*``.

    Superuser / ``*:*`` always allowed. Missing codes default to allow when
    ``default_allow=True`` (dev-friendly); set False for deny-by-default.
    """

    def __init__(self, *, default_allow: bool = True) -> None:
        self.default_allow = default_allow

    def _perms(self, principal: object | None) -> set[str]:
        if principal is None:
            return set()
        if bool(getattr(principal, "is_superuser", False)):
            return {"*:*"}
        perms = getattr(principal, "permissions", None) or frozenset()
        return set(perms) if isinstance(perms, (set, frozenset, list, tuple)) else set()

    def allow_read(self, principal: object | None, resource: str, field: str) -> bool:
        pset = self._perms(principal)
        if "*:*" in pset or f"{resource}:*" in pset:
            return True
        code = f"{resource}:field:{field}:read"
        if code in pset or f"{resource}:field:{field}:*" in pset:
            return True
        # also accept write as implying read
        if f"{resource}:field:{field}:write" in pset:
            return True
        return self.default_allow and principal is not None

    def allow_write(self, principal: object | None, resource: str, field: str) -> bool:
        pset = self._perms(principal)
        if "*:*" in pset or f"{resource}:*" in pset:
            return True
        code = f"{resource}:field:{field}:write"
        if code in pset or f"{resource}:field:{field}:*" in pset:
            return True
        return self.default_allow and principal is not None
