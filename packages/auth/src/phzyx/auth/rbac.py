"""RBAC helpers — permission code resolution."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from phzyx.auth.principal import Principal


def has_permission(principal: Principal | None, code: str) -> bool:
    if principal is None:
        return False
    return principal.has_perm(code)


def resolve_permissions(
    *,
    is_superuser: bool,
    group_permission_codes: Iterable[str] = (),
    direct_permission_codes: Iterable[str] = (),
) -> frozenset[str]:
    """Merge group + direct perms; superuser gets ``*:*``."""
    if is_superuser:
        return frozenset({"*:*"})
    return frozenset(set(group_permission_codes) | set(direct_permission_codes))


def check_permissions(
    principal: Principal,
    codes: Iterable[str],
    *,
    any_of: bool = False,
) -> bool:
    codes_t = tuple(codes)
    if not codes_t:
        return True
    if any_of:
        return principal.has_any_perm(*codes_t)
    return principal.has_all_perms(*codes_t)


def check_scopes(
    principal: Principal,
    scopes: Iterable[str],
    *,
    any_of: bool = False,
) -> bool:
    scopes_t = tuple(scopes)
    if not scopes_t:
        return True
    if any_of:
        return any(principal.has_scope(s) for s in scopes_t)
    return principal.has_all_scopes(*scopes_t)


def permission_code(resource: str, action: str) -> str:
    return f"{resource}:{action}"


def seed_resource_permissions(resource: str) -> list[tuple[str, str]]:
    """Default CRUD-ish codes for an AdminBoard resource."""
    actions = ("list", "get", "create", "update", "delete", "export", "bulk")
    return [(permission_code(resource, a), f"{resource} {a}") for a in actions]


def user_is_locked(user: Any, *, now: Any | None = None) -> bool:
    locked_until = getattr(user, "locked_until", None)
    if locked_until is None:
        return False
    from datetime import UTC, datetime

    n = now or datetime.now(UTC)
    if getattr(locked_until, "tzinfo", None) is None and getattr(n, "tzinfo", None) is not None:
        n = n.replace(tzinfo=None)
    return locked_until > n
