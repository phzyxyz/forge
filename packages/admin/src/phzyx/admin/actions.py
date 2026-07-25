"""Admin action registry — row / bulk / global (Diamond D2/D5)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from phzyx.admin.auth import require_authz
from phzyx.admin.errors import NotFoundError, ValidationAdminError
from phzyx.admin.identity import decode_identity

if TYPE_CHECKING:
    from phzyx.admin.service import AdminService

Scope = Literal["row", "bulk", "global"]

# client: SPA-side execution hint (no server mutation body required)
ClientKind = str | None  # export:csv | export:json | export:xlsx | copy:json | None


@dataclass(frozen=True, slots=True)
class AdminAction:
    """Declarative admin action (Diamond D5)."""

    name: str
    label: str
    description: str = ""
    scope: Scope = "bulk"
    confirm: bool = False
    danger: bool = False
    client: ClientKind = None  # if set, SPA runs client handler


# Backward-compatible alias
BulkAction = AdminAction

Handler = Callable[["AdminService", str, Sequence[str], Any | None], dict[str, Any]]


def action_deactivate(
    service: AdminService,
    resource: str,
    identities: Sequence[str],
    principal: Any | None = None,
) -> dict[str, Any]:
    """Set ``active=False`` on each identity when the model has that field."""
    res = service.get_resource(resource)
    if not any(c.name == "active" for c in res.columns):
        raise ValidationAdminError("resource has no active field")
    updated = 0
    for ident in identities:
        key = decode_identity(res.model, ident)
        obj = service.session.get(res.model, key)
        if obj is None:
            continue
        service.session.update(obj, active=False)
        updated += 1
    service.session.commit()
    if service.audit:
        pid = getattr(principal, "id", None) if principal else None
        service.audit.record(
            "bulk_deactivate",
            resource,
            principal_id=pid,
            count=updated,
        )
    return {"action": "deactivate", "updated": updated, "ok": True}


def action_activate(
    service: AdminService,
    resource: str,
    identities: Sequence[str],
    principal: Any | None = None,
) -> dict[str, Any]:
    """Set ``active=True`` on selected identities."""
    res = service.get_resource(resource)
    if not any(c.name == "active" for c in res.columns):
        raise ValidationAdminError("resource has no active field")
    updated = 0
    for ident in identities:
        key = decode_identity(res.model, ident)
        obj = service.session.get(res.model, key)
        if obj is None:
            continue
        service.session.update(obj, active=True)
        updated += 1
    service.session.commit()
    if service.audit:
        pid = getattr(principal, "id", None) if principal else None
        service.audit.record("bulk_activate", resource, principal_id=pid, count=updated)
    return {"action": "activate", "updated": updated, "ok": True}


DEFAULT_HANDLERS: dict[str, Handler] = {
    "deactivate": action_deactivate,
    "activate": action_activate,
}

# Prefer DEFAULT_HANDLERS; keep alias for D2 imports
DEFAULT_BULK_HANDLERS = DEFAULT_HANDLERS


def default_actions(*, has_active: bool) -> list[AdminAction]:
    """Built-in catalog: server mutations + client export/copy."""
    acts: list[AdminAction] = [
        AdminAction(
            name="export_csv",
            label="Export CSV",
            description="Download resource as CSV",
            scope="global",
            client="export:csv",
        ),
        AdminAction(
            name="export_json",
            label="Export JSON",
            description="Download resource as JSON",
            scope="global",
            client="export:json",
        ),
        AdminAction(
            name="export_xlsx",
            label="Export Excel",
            description="Download resource as Excel",
            scope="global",
            client="export:xlsx",
        ),
        AdminAction(
            name="copy_json",
            label="Copy JSON",
            description="Copy selection or all as JSON",
            scope="bulk",
            client="copy:json",
            confirm=False,
        ),
        AdminAction(
            name="copy_row_json",
            label="Copy JSON",
            description="Copy this row as JSON",
            scope="row",
            client="copy:json",
            confirm=False,
        ),
    ]
    if has_active:
        acts.extend(
            [
                AdminAction(
                    name="deactivate",
                    label="Deactivate",
                    description="Set active=false on selected rows",
                    scope="bulk",
                    confirm=True,
                    danger=False,
                ),
                AdminAction(
                    name="activate",
                    label="Activate",
                    description="Set active=true on selected rows",
                    scope="bulk",
                    confirm=True,
                ),
                AdminAction(
                    name="deactivate",
                    label="Deactivate",
                    description="Set active=false on this row",
                    scope="row",
                    confirm=True,
                ),
                AdminAction(
                    name="activate",
                    label="Activate",
                    description="Set active=true on this row",
                    scope="row",
                    confirm=True,
                ),
            ]
        )
    return acts


DEFAULT_BULK_ACTIONS: tuple[AdminAction, ...] = tuple(
    a for a in default_actions(has_active=True) if a.scope == "bulk" and not a.client
)


def _public(a: AdminAction) -> dict[str, Any]:
    return {
        "name": a.name,
        "label": a.label,
        "description": a.description,
        "scope": a.scope,
        "confirm": a.confirm,
        "danger": a.danger,
        "client": a.client,
    }


def list_admin_actions(
    resource_name: str,
    *,
    has_active: bool,
    scope: str | None = None,
) -> list[dict[str, Any]]:
    """Public action descriptors for SPA (Diamond D5)."""
    _ = resource_name
    out = [_public(a) for a in default_actions(has_active=has_active)]
    if scope:
        out = [a for a in out if a["scope"] == scope]
    return out


def list_bulk_actions(resource_name: str, has_active: bool) -> list[dict[str, Any]]:
    """Backward-compatible bulk-only list (D2)."""
    return list_admin_actions(resource_name, has_active=has_active, scope="bulk")


def run_admin_action(
    service: AdminService,
    resource: str,
    action: str,
    identities: Sequence[str] | None = None,
    *,
    principal: Any | None = None,
    handlers: dict[str, Handler] | None = None,
) -> dict[str, Any]:
    """Run a server-side action (row or bulk)."""
    require_authz(service.authz, principal, f"action:{action}", resource)
    # Client-only actions should not hit the server runner
    catalog = {
        a.name: a
        for a in default_actions(
            has_active=any(c.name == "active" for c in service.get_resource(resource).columns)
        )
        if a.client is None
    }
    reg_probe = handlers or DEFAULT_HANDLERS
    if action not in catalog and action not in reg_probe and action not in DEFAULT_HANDLERS:
        raise NotFoundError(f"unknown action {action}")

    idents = list(identities or [])
    if not idents:
        raise ValidationAdminError("identities required")
    reg = handlers or DEFAULT_HANDLERS
    handler = reg.get(action)
    if handler is None:
        raise NotFoundError(f"unknown action {action}")
    return handler(service, resource, idents, principal)


def run_bulk_action(
    service: AdminService,
    resource: str,
    action: str,
    identities: Sequence[str],
    *,
    principal: Any | None = None,
    handlers: dict[str, Handler] | None = None,
) -> dict[str, Any]:
    """Backward-compatible bulk runner (D2)."""
    return run_admin_action(
        service,
        resource,
        action,
        identities,
        principal=principal,
        handlers=handlers,
    )
