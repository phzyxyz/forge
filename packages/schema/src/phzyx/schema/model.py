"""Phzyx ``Model`` — Pydantic base with table metadata (``__phzyx_table__``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from phzyx.schema.errors import SchemaError
from phzyx.schema.field import ColumnMeta, get_column_meta
from pydantic import BaseModel, ConfigDict

_CAMEL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    """Convert ``UserProfile`` → ``user_profile`` for default table names."""
    step = _CAMEL_1.sub(r"\1_\2", name)
    return _CAMEL_2.sub(r"\1_\2", step).lower()


@dataclass(frozen=True, slots=True)
class TableInfo:
    """Resolved table identity and column metadata for a :class:`Model` subclass."""

    name: str
    schema_name: str | None
    columns: MappingProxyType[str, ColumnMeta]
    primary_key: tuple[str, ...]
    model_qualname: str

    @property
    def qualified_name(self) -> str:
        """``schema.name`` when schema is set, else bare table name."""
        if self.schema_name:
            return f"{self.schema_name}.{self.name}"
        return self.name


class Model(BaseModel):
    """Pydantic model base that materializes Phzyx table metadata.

    Subclasses receive ``__phzyx_table__``: a :class:`TableInfo` describing the
    SQL table name, optional schema, column :class:`~phzyx.schema.field.ColumnMeta`
    map, and primary-key field names (in declaration order).

    Configure the table via:

    * nested ``class Meta`` with ``table``, ``schema``, and/or ``abstract``
    * or subclass kwargs: ``class User(Model, table="users")``

    Concrete models must declare at least one primary key (single or composite).
    Concrete models auto-register unless ``Meta.register = False``.
    """

    model_config = ConfigDict(from_attributes=True)

    __phzyx_table__: ClassVar[TableInfo | None] = None

    def __init_subclass__(
        cls,
        table: str | None = None,
        schema: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Accept table/schema class kwargs; construction runs in __pydantic_init_subclass__.
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(
        cls,
        table: str | None = None,
        schema: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Build ``__phzyx_table__`` after Pydantic has finalized ``model_fields``."""
        super().__pydantic_init_subclass__(**kwargs)

        meta_cls = cls.__dict__.get("Meta")
        is_abstract = bool(getattr(meta_cls, "abstract", False))
        if is_abstract:
            cls.__phzyx_table__ = None
            return

        table_name = table
        schema_name = schema
        should_register = True
        if meta_cls is not None:
            if table_name is None:
                table_name = getattr(meta_cls, "table", None) or getattr(
                    meta_cls, "table_name", None
                )
            if schema_name is None:
                schema_name = getattr(meta_cls, "schema", None) or getattr(
                    meta_cls, "schema_name", None
                )
            should_register = bool(getattr(meta_cls, "register", True))

        if not table_name:
            table_name = camel_to_snake(cls.__name__)

        if not isinstance(table_name, str) or not table_name.strip():
            raise TypeError(f"{cls.__qualname__}: table name must be a non-empty string")

        meta_pk = getattr(meta_cls, "primary_key", None) if meta_cls is not None else None
        columns, primary_key = _collect_columns(cls, meta_primary_key=meta_pk)

        if not primary_key:
            raise SchemaError(
                f"{cls.__qualname__} must declare at least one primary key column. "
                f"Use Field(primary_key=True) on one or more fields, or set "
                f"Meta.primary_key = ('col', ...) for a composite key."
            )

        cls.__phzyx_table__ = TableInfo(
            name=table_name.strip(),
            schema_name=schema_name.strip() if isinstance(schema_name, str) else None,
            columns=MappingProxyType(columns),
            primary_key=tuple(primary_key),
            model_qualname=f"{cls.__module__}.{cls.__qualname__}",
        )

        if should_register:
            # Local import avoids circular dependency at module load.
            from phzyx.schema.registry import get_registry

            get_registry().register(cls, replace=True)


def _collect_columns(
    cls: type[BaseModel],
    *,
    meta_primary_key: Any = None,
) -> tuple[dict[str, ColumnMeta], list[str]]:
    columns: dict[str, ColumnMeta] = {}
    field_pk: list[str] = []
    for field_name, field_info in cls.model_fields.items():
        meta = get_column_meta(field_info) or ColumnMeta()
        columns[field_name] = meta
        if meta.primary_key:
            field_pk.append(field_name)

    if meta_primary_key is None:
        return columns, field_pk

    if isinstance(meta_primary_key, str):
        meta_pk_list = [meta_primary_key]
    else:
        try:
            meta_pk_list = list(meta_primary_key)
        except TypeError as exc:
            raise SchemaError(
                f"{cls.__qualname__}.Meta.primary_key must be a string or sequence of strings"
            ) from exc

    if not meta_pk_list:
        raise SchemaError(f"{cls.__qualname__}.Meta.primary_key must not be empty")

    for name in meta_pk_list:
        if not isinstance(name, str) or not name.strip():
            raise SchemaError(
                f"{cls.__qualname__}.Meta.primary_key entries must be non-empty strings"
            )
        if name not in columns:
            raise SchemaError(
                f"{cls.__qualname__}.Meta.primary_key refers to unknown field {name!r}"
            )

    # Meta.primary_key is authoritative for order; ensure ColumnMeta flags match.
    pk_set = set(meta_pk_list)
    adjusted: dict[str, ColumnMeta] = {}
    for name, meta in columns.items():
        if name in pk_set and not meta.primary_key:
            adjusted[name] = ColumnMeta(
                primary_key=True,
                unique=meta.unique,
                index=meta.index,
                foreign_key=meta.foreign_key,
                on_delete=meta.on_delete,
                server_default=meta.server_default,
                db_type=meta.db_type,
                renamed_from=meta.renamed_from,
                archive_on_remove=meta.archive_on_remove,
                admin_hidden=meta.admin_hidden,
                admin_readonly=meta.admin_readonly,
                admin_exclude=meta.admin_exclude,
                file_kind=meta.file_kind,
            )
        else:
            adjusted[name] = meta
    return adjusted, meta_pk_list


def get_table_info(model: type[Model] | Model) -> TableInfo:
    """Return ``__phzyx_table__`` for a model class or instance.

    Raises
    ------
    TypeError
        If the model is abstract or has no table metadata.
    """
    cls = model if isinstance(model, type) else type(model)
    if not issubclass(cls, Model):
        raise TypeError(f"expected a Phzyx Model subclass, got {cls!r}")
    info = getattr(cls, "__phzyx_table__", None)
    if info is None:
        raise TypeError(f"{cls.__qualname__} has no __phzyx_table__ (abstract or incomplete)")
    return info
