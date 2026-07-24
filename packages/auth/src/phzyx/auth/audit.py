"""Auth audit recording (in-memory + optional ORM)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AuditLog:
    """Collect auth events; optionally flush to a list for tests."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        ip_hash: str | None = None,
        **meta: Any,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "actor_id": actor_id,
                "ip_hash": ip_hash,
                "meta": meta,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def meta_json(self, **meta: Any) -> str:
        return json.dumps(meta, default=str)
