"""Soft-delete helpers (deleted_at column convention)."""

from __future__ import annotations

from datetime import UTC, datetime

from phzyx.orm.expr import Filter, is_not_null, is_null
from phzyx.orm.session_sync import Session
from phzyx.schema.model import Model


def soft_delete_filter(
    column: str = "deleted_at", *, include_deleted: bool = False
) -> list[Filter]:
    """WHERE helpers for soft-deleted rows."""
    if include_deleted:
        return []
    return [is_null(column)]


def only_deleted_filter(column: str = "deleted_at") -> list[Filter]:
    return [is_not_null(column)]


def soft_delete(
    session: Session,
    instance: Model,
    *,
    column: str = "deleted_at",
    when: datetime | None = None,
) -> Model:
    """Set deleted_at (or custom column) instead of hard DELETE.

    Uses naive UTC by default so MySQL ``DATETIME`` accepts the value without
    a tz-aware conversion error. Pass ``when=`` for an explicit timestamp.
    """
    if when is None:
        ts = datetime.now(UTC).replace(tzinfo=None)
    else:
        ts = when
        if ts.tzinfo is not None:
            ts = ts.astimezone(UTC).replace(tzinfo=None)
    return session.update(instance, **{column: ts})


def restore(
    session: Session,
    instance: Model,
    *,
    column: str = "deleted_at",
) -> Model:
    """Clear soft-delete marker."""
    return session.update(instance, **{column: None})
