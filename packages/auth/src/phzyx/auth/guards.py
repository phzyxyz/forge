"""Framework-agnostic authorization checks on Principal."""

from __future__ import annotations

from collections.abc import Iterable

from phzyx.auth.errors import ForbiddenError, UnauthorizedError
from phzyx.auth.principal import Principal
from phzyx.auth.rbac import check_permissions, check_scopes


def ensure_authenticated(principal: Principal | None) -> Principal:
    if principal is None:
        raise UnauthorizedError()
    if not principal.is_active:
        raise ForbiddenError("Account inactive", reason="inactive")
    return principal


def ensure_staff(principal: Principal | None) -> Principal:
    p = ensure_authenticated(principal)
    if not p.is_staff and not p.is_superuser:
        raise ForbiddenError("Staff access required", reason="staff")
    return p


def ensure_superuser(principal: Principal | None) -> Principal:
    p = ensure_authenticated(principal)
    if not p.is_superuser:
        raise ForbiddenError("Superuser access required", reason="superuser")
    return p


def ensure_permissions(
    principal: Principal | None,
    codes: Iterable[str],
    *,
    any_of: bool = False,
) -> Principal:
    p = ensure_authenticated(principal)
    codes_t = tuple(codes)
    if codes_t and not check_permissions(p, codes_t, any_of=any_of):
        raise ForbiddenError(
            "Missing permission",
            reason="permission",
            required=list(codes_t),
            any_of=any_of,
        )
    return p


def ensure_scopes(
    principal: Principal | None,
    scopes: Iterable[str],
    *,
    any_of: bool = False,
) -> Principal:
    p = ensure_authenticated(principal)
    scopes_t = tuple(scopes)
    if scopes_t and not check_scopes(p, scopes_t, any_of=any_of):
        raise ForbiddenError(
            "Missing scope",
            reason="scope",
            required=list(scopes_t),
            any_of=any_of,
        )
    return p
