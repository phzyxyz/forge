"""Row → model hydration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from phzyx.schema.model import Model

M = TypeVar("M", bound=Model)


def row_to_model(model: type[M], row: Mapping[str, Any] | Sequence[Any]) -> M:
    """Hydrate a model from a mapping or ordered row tuple."""
    if isinstance(row, Mapping):
        data = {k: row[k] for k in model.model_fields if k in row}
        return model.model_validate(data)
    cols = list(model.model_fields.keys())
    if len(row) < len(cols):
        raise ValueError(f"row has {len(row)} values, model expects {len(cols)}")
    data = {col: row[i] for i, col in enumerate(cols)}
    return model.model_validate(data)


def model_to_row(instance: Model) -> dict[str, Any]:
    """Dump model fields for insert/update (exclude unset optional as needed)."""
    return instance.model_dump()
