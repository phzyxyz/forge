"""Bulk insert helpers (chunked)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from phzyx.orm.session_sync import Session
from phzyx.orm.sql import build_insert
from phzyx.schema.model import Model

M = TypeVar("M", bound=Model)


def bulk_insert(
    session: Session,
    model: type[M],
    rows: Sequence[dict[str, Any]] | Iterable[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> int:
    """Insert many rows in chunks. Returns number of rows inserted."""
    count = 0
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= chunk_size:
            count += _flush(session, model, batch)
            batch.clear()
    if batch:
        count += _flush(session, model, batch)
    return count


def _flush(session: Session, model: type[Model], batch: list[dict[str, Any]]) -> int:
    for row in batch:
        frag = build_insert(model, row, dialect=session.dialect)
        session._execute(frag.sql, frag.params)  # noqa: SLF001 — intentional bulk path
    return len(batch)
