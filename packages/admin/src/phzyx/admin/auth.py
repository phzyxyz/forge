"""Authn/Authz protocol for AdminBoard mutations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from phzyx.admin.errors import ForbiddenError


@runtime_checkable
class Principal(Protocol):
    """Authenticated principal (user/service)."""

    @property
    def id(self) -> str: ...


@runtime_checkable
class Authz(Protocol):
    """Authorization hook — return True to allow."""

    def authorize(self, principal: Any | None, action: str, resource: str) -> bool: ...


class AllowAll:
    """Dev default: allow everything (warn in production)."""

    def authorize(self, principal: Any | None, action: str, resource: str) -> bool:
        return True


class DenyWrites:
    """Example policy: allow reads, deny mutations."""

    def authorize(self, principal: Any | None, action: str, resource: str) -> bool:
        return action in {"list", "get", "export", "copy", "open_meta"}


def require_authz(
    authz: Authz,
    principal: Any | None,
    action: str,
    resource: str,
) -> None:
    if not authz.authorize(principal, action, resource):
        raise ForbiddenError(
            f"Not allowed to {action} on {resource}",
            action=action,
            resource=resource,
        )


@runtime_checkable
class FieldAuthz(Protocol):
    """Optional field-level read/write gate (Field-RBAC)."""

    def allow_read(self, principal: Any | None, resource: str, field: str) -> bool: ...

    def allow_write(self, principal: Any | None, resource: str, field: str) -> bool: ...


class AllowAllFields:
    """Default: no field restrictions."""

    def allow_read(self, principal: Any | None, resource: str, field: str) -> bool:
        return True

    def allow_write(self, principal: Any | None, resource: str, field: str) -> bool:
        return True
