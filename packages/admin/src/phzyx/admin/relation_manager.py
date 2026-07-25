"""Relation manager helpers — structured related CRUD descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from phzyx.admin.resource import RelationConfig, ResourceConfig

if TYPE_CHECKING:
    from phzyx.admin.service import AdminService


@dataclass
class RelationManager:
    """Descriptor for managing related rows from a parent record."""

    name: str
    parent_resource: str
    relation: RelationConfig
    child_resource: str

    def list_children(
        self,
        service: AdminService,
        parent_identity: str,
        *,
        page: int = 1,
        page_size: int = 50,
        principal: Any | None = None,
    ) -> Any:
        return service.list_relation(
            self.parent_resource,
            parent_identity,
            self.relation.name,
            page=page,
            page_size=page_size,
            principal=principal,
        )


def relation_managers_for(res: ResourceConfig) -> list[RelationManager]:
    """Build managers for each relation on a resource."""
    out: list[RelationManager] = []
    for rel in res.relations:
        out.append(
            RelationManager(
                name=f"{res.name}.{rel.name}",
                parent_resource=res.name,
                relation=rel,
                child_resource=rel.resource,
            )
        )
    return out


def all_relation_managers(
    resources: dict[str, ResourceConfig],
) -> list[RelationManager]:
    managers: list[RelationManager] = []
    for res in resources.values():
        managers.extend(relation_managers_for(res))
    return managers
