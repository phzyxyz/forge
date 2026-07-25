"""Dashboard widget helpers (counts / simple metrics)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from phzyx.admin.resource import ResourceConfig
from phzyx.orm.session_sync import Session


@dataclass
class CountWidget:
    id: str
    label: str
    resource: str
    value: int
    kind: str = "count"


def resource_count_widgets(
    session: Session,
    resources: dict[str, ResourceConfig],
    *,
    resource_names: list[str] | None = None,
) -> list[CountWidget]:
    """Return count widgets for each resource (or a subset)."""
    names = resource_names or list(resources.keys())
    out: list[CountWidget] = []
    for name in names:
        res = resources.get(name)
        if res is None:
            continue
        try:
            if hasattr(session, "count"):
                total = int(session.count(res.model))
            else:
                total = len(session.query(res.model))
        except Exception:
            total = 0
        out.append(
            CountWidget(
                id=f"count:{name}",
                label=res.label or name,
                resource=name,
                value=total,
            )
        )
    return out


def widgets_to_dict(widgets: list[CountWidget]) -> list[dict[str, Any]]:
    return [
        {
            "id": w.id,
            "label": w.label,
            "resource": w.resource,
            "value": w.value,
            "kind": w.kind,
        }
        for w in widgets
    ]
