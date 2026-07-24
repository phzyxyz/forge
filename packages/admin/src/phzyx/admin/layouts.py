"""Admin layout preferences (column order/visibility) — GET/PUT model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LayoutPrefs:
    resource: str
    principal_id: str
    columns: list[str] = field(default_factory=list)  # visible order
    hidden: list[str] = field(default_factory=list)
    page_size: int = 50

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LayoutPrefs:
        return cls(
            resource=str(data["resource"]),
            principal_id=str(data.get("principal_id", "anonymous")),
            columns=list(data.get("columns") or []),
            hidden=list(data.get("hidden") or []),
            page_size=int(data.get("page_size", 50)),
        )


class LayoutStore:
    """In-memory layout store with debounce-friendly put."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], LayoutPrefs] = {}

    def key(self, resource: str, principal_id: str) -> tuple[str, str]:
        return (resource, principal_id or "anonymous")

    def get(self, resource: str, principal_id: str = "anonymous") -> LayoutPrefs | None:
        return self._data.get(self.key(resource, principal_id))

    def put(self, prefs: LayoutPrefs) -> LayoutPrefs:
        self._data[self.key(prefs.resource, prefs.principal_id)] = prefs
        return prefs
