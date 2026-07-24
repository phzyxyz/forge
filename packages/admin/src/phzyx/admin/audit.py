"""Audit log for admin writes and exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    action: str
    resource: str
    principal_id: str | None
    at: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLog:
    """In-memory audit log (host apps can wrap to persist)."""

    def __init__(self, *, max_events: int = 10_000) -> None:
        self.max_events = max_events
        self._events: list[AuditEvent] = []

    def record(
        self,
        action: str,
        resource: str,
        *,
        principal_id: str | None = None,
        **details: Any,
    ) -> AuditEvent:
        ev = AuditEvent(
            action=action,
            resource=resource,
            principal_id=principal_id,
            at=datetime.now(UTC).isoformat(),
            details=details,
        )
        self._events.append(ev)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events :]
        return ev

    def list(self, *, limit: int = 100) -> list[AuditEvent]:
        return list(self._events[-limit:])
