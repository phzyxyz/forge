"""Phzyx ``Field`` — Pydantic Field wrapper with a DB metadata namespace.

Metadata is stored under ``json_schema_extra["phzyx"]`` so it survives model
construction and is available to Manifest builders without a parallel registry.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field as PydanticField
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

# Key inside FieldInfo.json_schema_extra for Phzyx column metadata.
PHZYX_JSON_SCHEMA_KEY = "phzyx"

FileKind = Literal["file", "image"]


class OnDelete(StrEnum):
    """Referential action when a referenced row is deleted."""

    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    RESTRICT = "RESTRICT"
    NO_ACTION = "NO ACTION"
    SET_DEFAULT = "SET DEFAULT"


@dataclass(frozen=True, slots=True)
class ColumnMeta:
    """Database and admin metadata attached to a Phzyx :func:`Field`."""

    primary_key: bool = False
    unique: bool = False
    index: bool = False
    foreign_key: str | None = None
    on_delete: OnDelete | str | None = None
    server_default: str | None = None
    db_type: str | None = None
    renamed_from: str | None = None
    archive_on_remove: bool | None = None
    admin_hidden: bool = False
    admin_readonly: bool = False
    admin_exclude: bool = False
    file_kind: FileKind | None = None
    # None = default heuristic at manifest time (single int PK → True).
    autoincrement: bool | None = None
    # ORM-side timestamp helpers (also emit server defaults when possible).
    auto_now_add: bool = False
    auto_now: bool = False
    # Optimistic concurrency column (increment on update; WHERE old version).
    optimistic: bool = False
    # Generated column SQL expression (dialect-specific body).
    generated: str | None = None
    # MySQL-style ON UPDATE for timestamps (also used as hint for auto_now).
    on_update: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for ``json_schema_extra`` storage."""
        data = asdict(self)
        if isinstance(self.on_delete, OnDelete):
            data["on_delete"] = self.on_delete.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColumnMeta:
        """Deserialize from ``json_schema_extra["phzyx"]``."""
        on_delete: OnDelete | str | None = data.get("on_delete")
        if isinstance(on_delete, str):
            # Prefer enum; keep unknown dialect strings as-is.
            with suppress(ValueError):
                on_delete = OnDelete(on_delete)

        file_kind = data.get("file_kind")
        if file_kind is not None and file_kind not in ("file", "image"):
            raise ValueError(f"invalid file_kind in ColumnMeta: {file_kind!r}")

        autoincrement = data.get("autoincrement")
        if autoincrement is not None:
            autoincrement = bool(autoincrement)

        return cls(
            primary_key=bool(data.get("primary_key", False)),
            unique=bool(data.get("unique", False)),
            index=bool(data.get("index", False)),
            foreign_key=data.get("foreign_key"),
            on_delete=on_delete,
            server_default=data.get("server_default"),
            db_type=data.get("db_type"),
            renamed_from=data.get("renamed_from"),
            archive_on_remove=data.get("archive_on_remove"),
            admin_hidden=bool(data.get("admin_hidden", False)),
            admin_readonly=bool(data.get("admin_readonly", False)),
            admin_exclude=bool(data.get("admin_exclude", False)),
            file_kind=file_kind,
            autoincrement=autoincrement,
            auto_now_add=bool(data.get("auto_now_add", False)),
            auto_now=bool(data.get("auto_now", False)),
            optimistic=bool(data.get("optimistic", False)),
            generated=data.get("generated"),
            on_update=data.get("on_update"),
        )


def Field(  # noqa: N802 — public API mirrors pydantic.Field
    default: Any = PydanticUndefined,
    *,
    default_factory: Any = None,
    alias: str | None = None,
    title: str | None = None,
    description: str | None = None,
    # --- Phzyx DB / admin namespace ---
    primary_key: bool = False,
    unique: bool = False,
    index: bool = False,
    foreign_key: str | None = None,
    on_delete: OnDelete | str | None = None,
    server_default: str | None = None,
    db_type: str | None = None,
    renamed_from: str | None = None,
    archive_on_remove: bool | None = None,
    admin_hidden: bool = False,
    admin_readonly: bool = False,
    admin_exclude: bool = False,
    file_kind: FileKind | None = None,
    autoincrement: bool | None = None,
    auto_now_add: bool = False,
    auto_now: bool = False,
    optimistic: bool = False,
    generated: str | None = None,
    on_update: str | None = None,
    **kwargs: Any,
) -> Any:
    """Declare a model field with optional Phzyx column metadata.

    Standard validation/default kwargs are forwarded to Pydantic ``Field``.
    Phzyx keys are stored under ``json_schema_extra["phzyx"]`` and recovered with
    :func:`get_column_meta`.

    Parameters
    ----------
    primary_key:
        Column participates in the table primary key (composite when multiple).
    unique:
        Unique constraint on this column.
    index:
        Non-unique index (unique indexes use ``unique=True``).
    foreign_key:
        Target reference, typically ``"table.column"``.
    on_delete:
        FK delete action; requires ``foreign_key``.
    server_default:
        Database-side default expression (SQL fragment as string).
    db_type:
        Physical type override escape hatch (dialect-specific).
    renamed_from:
        Previous column name — schema engine emits rename instead of archive+add.
    archive_on_remove:
        Per-field override for archive-on-remove policy (``None`` = default policy).
    admin_hidden / admin_readonly / admin_exclude:
        AdminBoard presentation and export hints.
    file_kind:
        ``"file"`` or ``"image"`` when the column stores a storage key (not bytes).
    autoincrement:
        Integer PK identity. ``None`` defaults to True for a single int PK.
    auto_now_add:
        Set UTC timestamp on insert when value is missing.
    auto_now:
        Set UTC timestamp on every update.
    optimistic:
        Version column for optimistic concurrency (int; incremented on update).
    generated:
        SQL expression for a generated column (e.g. ``price * qty``).
    on_update:
        SQL ON UPDATE clause body (e.g. ``CURRENT_TIMESTAMP`` for MySQL).
    """
    if on_delete is not None and foreign_key is None:
        raise ValueError("on_delete requires foreign_key to be set")

    if file_kind is not None and file_kind not in ("file", "image"):
        raise ValueError(f"file_kind must be 'file' or 'image', got {file_kind!r}")

    if renamed_from is not None and not str(renamed_from).strip():
        raise ValueError("renamed_from must be a non-empty column name when set")

    if auto_now_add and auto_now:
        raise ValueError("auto_now_add and auto_now are mutually exclusive")

    if auto_now and on_update is None:
        on_update = "CURRENT_TIMESTAMP"

    meta = ColumnMeta(
        primary_key=primary_key,
        unique=unique,
        index=index,
        foreign_key=foreign_key,
        on_delete=on_delete,
        server_default=server_default,
        db_type=db_type,
        renamed_from=renamed_from,
        archive_on_remove=archive_on_remove,
        admin_hidden=admin_hidden,
        admin_readonly=admin_readonly,
        admin_exclude=admin_exclude,
        file_kind=file_kind,
        autoincrement=autoincrement,
        auto_now_add=auto_now_add,
        auto_now=auto_now,
        optimistic=optimistic,
        generated=generated,
        on_update=on_update,
    )

    existing_extra = kwargs.pop("json_schema_extra", None)
    field_kwargs: dict[str, Any] = {
        "json_schema_extra": _merge_json_schema_extra(existing_extra, meta),
        **kwargs,
    }
    if default_factory is not None:
        field_kwargs["default_factory"] = default_factory
    if alias is not None:
        field_kwargs["alias"] = alias
    if title is not None:
        field_kwargs["title"] = title
    if description is not None:
        field_kwargs["description"] = description

    if default is PydanticUndefined:
        return PydanticField(**field_kwargs)
    return PydanticField(default, **field_kwargs)


def get_column_meta(field_info: FieldInfo) -> ColumnMeta | None:
    """Return Phzyx :class:`ColumnMeta` from a Pydantic ``FieldInfo``, if present."""
    extra = field_info.json_schema_extra
    if extra is None or callable(extra):
        return None
    if not isinstance(extra, dict):
        return None
    raw = extra.get(PHZYX_JSON_SCHEMA_KEY)
    if not isinstance(raw, dict):
        return None
    return ColumnMeta.from_dict(raw)


def _merge_json_schema_extra(existing: Any, meta: ColumnMeta) -> dict[str, Any]:
    if existing is None:
        base: dict[str, Any] = {}
    elif callable(existing):
        raise TypeError(
            "Field(json_schema_extra=callable) is not supported together with Phzyx "
            "column metadata; pass a dict instead."
        )
    elif isinstance(existing, dict):
        base = dict(existing)
    else:
        raise TypeError(f"Unsupported json_schema_extra type: {type(existing)!r}")

    base[PHZYX_JSON_SCHEMA_KEY] = meta.to_dict()
    return base
