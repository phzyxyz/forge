"""Phzyx ORM — sessions and queries over Pydantic models."""

from phzyx.orm.bulk import bulk_insert
from phzyx.orm.engine_async import AsyncEngine, create_async_engine
from phzyx.orm.engine_sync import Engine, create_engine
from phzyx.orm.expr import (
    Filter,
    OrderBy,
    asc,
    desc,
    eq,
    gt,
    gte,
    ilike,
    in_,
    is_not_null,
    is_null,
    like,
    lt,
    lte,
    ne,
)
from phzyx.orm.files import FileField, ImageField, build_upload_to, sanitize_upload_key
from phzyx.orm.keyset import (
    KeysetPage,
    decode_cursor,
    default_order_columns,
    encode_cursor,
    keyset_filters_note,
    order_from_columns,
)
from phzyx.orm.relations import fetch_related, fetch_related_async
from phzyx.orm.session_async import AsyncSession, create_async_session
from phzyx.orm.session_sync import Session, create_session
from phzyx.orm.sql import (
    SqlFragment,
    build_delete,
    build_insert,
    build_select,
    build_select_by_pk,
    build_update,
)
from phzyx.schema import (
    Field,
    Model,
    ModelRegistry,
    OnDelete,
    RegistryError,
    TableInfo,
    get_column_meta,
    get_registry,
    get_table_info,
    register_model,
    unregister_model,
)

__version__ = "0.1.0"

__all__ = [
    "AsyncEngine",
    "AsyncSession",
    "Engine",
    "Field",
    "FileField",
    "Filter",
    "ImageField",
    "KeysetPage",
    "Model",
    "ModelRegistry",
    "OnDelete",
    "OrderBy",
    "RegistryError",
    "Session",
    "SqlFragment",
    "TableInfo",
    "__version__",
    "asc",
    "build_delete",
    "build_insert",
    "build_select",
    "build_select_by_pk",
    "build_update",
    "build_upload_to",
    "bulk_insert",
    "create_async_engine",
    "create_async_session",
    "create_engine",
    "create_session",
    "decode_cursor",
    "default_order_columns",
    "desc",
    "encode_cursor",
    "eq",
    "fetch_related",
    "fetch_related_async",
    "get_column_meta",
    "get_registry",
    "get_table_info",
    "gt",
    "gte",
    "ilike",
    "in_",
    "is_not_null",
    "is_null",
    "keyset_filters_note",
    "like",
    "lt",
    "lte",
    "ne",
    "order_from_columns",
    "register_model",
    "sanitize_upload_key",
    "unregister_model",
]
