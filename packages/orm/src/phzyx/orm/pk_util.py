"""Primary-key helpers shared by sync/async sessions."""

from __future__ import annotations

from typing import Any

from phzyx.schema.model import Model, get_table_info


def primary_key_map(model: type[Model], key: Any) -> dict[str, Any]:
    """Normalize a scalar or composite PK into a column→value mapping."""
    info = get_table_info(model)
    pk = info.primary_key
    if not pk:
        raise ValueError(f"{model.__name__} has no primary key")
    if len(pk) == 1:
        val = key[pk[0]] if isinstance(key, dict) else key
        return {pk[0]: val}
    if not isinstance(key, dict):
        raise ValueError(f"{model.__name__} composite key requires a dict")
    out: dict[str, Any] = {}
    for col in pk:
        if col not in key:
            raise ValueError(f"composite key missing {col!r}")
        out[col] = key[col]
    return out


def optimistic_columns(model: type[Model]) -> list[str]:
    info = get_table_info(model)
    return [name for name, meta in info.columns.items() if meta.optimistic]


def reject_optimistic_for_by_pk(model: type[Model]) -> None:
    """``update_by_pk`` cannot see the prior version without a loaded row."""
    cols = optimistic_columns(model)
    if cols:
        raise ValueError(
            f"{model.__name__} has optimistic column(s) {cols!r}; "
            "use session.update(instance, ...) so the expected version comes "
            "from the loaded row"
        )
