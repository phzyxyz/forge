"""Global search across registered resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from phzyx.admin.identity import encode_identity
from phzyx.admin.resource import ResourceConfig
from phzyx.orm.expr import Filter, ilike, like, or_
from phzyx.orm.session_sync import Session
from phzyx.schema.model import get_table_info


@dataclass
class SearchHit:
    resource: str
    identity: str
    label: str
    score: float = 1.0
    row: dict[str, Any] | None = None


def _escape_like(q: str) -> str:
    """Escape LIKE wildcards in user input."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def global_search(
    session: Session,
    resources: dict[str, ResourceConfig],
    query: str,
    *,
    limit_per_resource: int = 5,
    dialect_ilike: bool = True,
) -> list[SearchHit]:
    """Search searchable columns across resources (simple OR-ilike)."""
    q = (query or "").strip()
    if not q:
        return []
    if len(q) > 200:
        q = q[:200]
    limit_per_resource = max(1, min(int(limit_per_resource), 50))
    needle = f"%{_escape_like(q)}%"
    hits: list[SearchHit] = []
    for name, res in resources.items():
        cols = [c.name for c in res.columns if c.searchable and not c.secret]
        if not cols:
            continue
        filters: list[Filter] = []
        for col in cols[:8]:
            filters.append(ilike(col, needle) if dialect_ilike else like(col, needle))
        where = [or_(*filters)] if len(filters) > 1 else filters
        try:
            rows = session.query(res.model, where=where, limit=limit_per_resource)
        except Exception:
            filters = [like(col, needle) for col in cols[:8]]
            where = [or_(*filters)] if len(filters) > 1 else filters
            try:
                rows = session.query(res.model, where=where, limit=limit_per_resource)
            except Exception:
                continue

        pk = get_table_info(res.model).primary_key
        for row in rows:
            data = row.model_dump(mode="json")
            label_parts = [str(data.get(c)) for c in cols[:3] if data.get(c) not in (None, "")]
            key = getattr(row, pk[0]) if len(pk) == 1 else {c: getattr(row, c) for c in pk}
            hits.append(
                SearchHit(
                    resource=name,
                    identity=encode_identity(res.model, key),
                    label=" · ".join(label_parts) or name,
                    row=data,
                )
            )
    return hits[: limit_per_resource * max(1, len(resources))]
