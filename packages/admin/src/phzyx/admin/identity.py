"""Composite / single PK identity encode-decode for admin routes."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, unquote

from phzyx.admin.errors import ValidationAdminError
from phzyx.schema.model import Model, get_table_info


def encode_identity(model: type[Model], key: Any) -> str:
    """Encode PK to a URL-safe identity string.

    Single PK: string form of the value.
    Composite: JSON object of column→value, URL-encoded.
    """
    info = get_table_info(model)
    pk = info.primary_key
    if len(pk) == 1:
        val = key[pk[0]] if isinstance(key, dict) else key
        return quote(str(val), safe="")
    if isinstance(key, dict):
        data = {c: key[c] for c in pk}
    elif isinstance(key, (tuple, list)):
        data = dict(zip(pk, key, strict=True))
    else:
        raise ValidationAdminError("composite identity requires dict or tuple")
    return quote(json.dumps(data, separators=(",", ":"), sort_keys=True), safe="")


def decode_identity(model: type[Model], identity: str) -> Any:
    """Decode URL identity back to get() key (scalar or dict)."""
    info = get_table_info(model)
    pk = info.primary_key
    raw = unquote(identity)
    if len(pk) == 1:
        # try int coercion for int PKs (including Optional[int] / int | None)
        field = model.model_fields[pk[0]]
        ann = field.annotation
        core = ann
        origin = getattr(ann, "__origin__", None)
        if origin is not None:
            args = [a for a in getattr(ann, "__args__", ()) if a is not type(None)]
            if len(args) == 1:
                core = args[0]
        if core is int or ann is int:
            try:
                return int(raw)
            except ValueError as exc:
                raise ValidationAdminError(f"invalid integer identity: {raw}") from exc
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationAdminError("invalid composite identity JSON") from exc
    if not isinstance(data, dict):
        raise ValidationAdminError("composite identity must be a JSON object")
    for col in pk:
        if col not in data:
            raise ValidationAdminError(f"composite identity missing {col!r}")
    return data
