"""Thin relations — FK scalars first; optional simple fetch.

Non-goals vs SQLAlchemy: no full relationship graph, lazy-loading cascade,
or unit-of-work relationship tracking. Prefer explicit joins / ``fetch_related``.
"""

from __future__ import annotations

from typing import TypeVar

from phzyx.orm.session_async import AsyncSession
from phzyx.orm.session_sync import Session
from phzyx.schema.model import Model, get_table_info

M = TypeVar("M", bound=Model)


async def fetch_related_async(
    session: AsyncSession,
    instance: Model,
    *,
    fk_field: str,
    related_model: type[M],
    related_pk: str = "id",
) -> M | None:
    """Load a related row via a scalar FK field on ``instance``."""
    data = instance.model_dump()
    if fk_field not in data:
        raise ValueError(f"{type(instance).__name__} has no field {fk_field!r}")
    fk_val = data[fk_field]
    if fk_val is None:
        return None
    info = get_table_info(related_model)
    if len(info.primary_key) == 1:
        return await session.get(related_model, fk_val)
    return await session.get(related_model, {info.primary_key[0]: fk_val})


def fetch_related(
    session: Session,
    instance: Model,
    *,
    fk_field: str,
    related_model: type[M],
    related_pk: str = "id",
) -> M | None:
    """Sync variant of :func:`fetch_related_async`."""
    data = instance.model_dump()
    if fk_field not in data:
        raise ValueError(f"{type(instance).__name__} has no field {fk_field!r}")
    fk_val = data[fk_field]
    if fk_val is None:
        return None
    info = get_table_info(related_model)
    if len(info.primary_key) == 1:
        return session.get(related_model, fk_val)
    return session.get(related_model, {info.primary_key[0]: fk_val})
