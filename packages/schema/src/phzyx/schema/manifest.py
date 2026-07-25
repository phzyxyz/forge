"""Manifest IR — desired-state schema graph (versioned, JSON-serializable)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from phzyx.schema.errors import SchemaError
from phzyx.schema.field import OnDelete
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import (
    LogicalType,
    enum_values,
    field_max_length,
    infer_logical_type,
)

MANIFEST_VERSION = 1

OnDeleteLiteral = Literal["CASCADE", "SET NULL", "RESTRICT", "NO ACTION", "SET DEFAULT"]


@dataclass(frozen=True, slots=True)
class ColumnDef:
    name: str
    logical_type: LogicalType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    foreign_key: str | None = None
    on_delete: str | None = None
    server_default: str | None = None
    db_type: str | None = None
    renamed_from: str | None = None
    archive_on_remove: bool | None = None
    admin_hidden: bool = False
    admin_readonly: bool = False
    admin_exclude: bool = False
    file_kind: str | None = None
    autoincrement: bool = False
    auto_now_add: bool = False
    auto_now: bool = False
    optimistic: bool = False
    max_length: int | None = None
    enum_values: tuple[Any, ...] | None = None
    generated: str | None = None
    on_update: str | None = None
    pg_enum_name: str | None = None


@dataclass(frozen=True, slots=True)
class IndexDef:
    name: str
    columns: tuple[str, ...] = ()
    unique: bool = False
    # Partial index predicate (PG/SQLite 3.8+ WHERE …)
    where: str | None = None
    # Index method: btree (default), gin, gist, hash (dialect-dependent)
    using: str | None = None
    # Expression index bodies when not simple columns (e.g. "lower(email)")
    expressions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConstraintDef:
    """Named table constraint (FK, CHECK, or multi-column UNIQUE)."""

    name: str
    kind: Literal["foreign_key", "check", "unique"]
    columns: tuple[str, ...] = ()
    ref_table: str = ""
    ref_columns: tuple[str, ...] = ()
    on_delete: str | None = None
    expression: str | None = None


@dataclass(frozen=True, slots=True)
class TableDef:
    name: str
    columns: tuple[ColumnDef, ...]
    primary_key: tuple[str, ...]
    indexes: tuple[IndexDef, ...] = ()
    constraints: tuple[ConstraintDef, ...] = ()
    schema_name: str | None = None
    model_qualname: str | None = None

    @property
    def qualified_name(self) -> str:
        if self.schema_name:
            return f"{self.schema_name}.{self.name}"
        return self.name


@dataclass(frozen=True, slots=True)
class Manifest:
    """Desired-state schema IR produced from Phzyx models."""

    tables: tuple[TableDef, ...]
    manifest_version: int = MANIFEST_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    def table(self, name: str, *, schema: str | None = None) -> TableDef:
        key = f"{schema}.{name}" if schema else name
        for t in self.tables:
            if t.qualified_name == key or (schema is None and t.name == name):
                return t
        raise KeyError(f"table not in manifest: {key}")


def build_manifest(
    models: Sequence[type[Model]] | Iterable[type[Model]],
    *,
    meta: dict[str, Any] | None = None,
) -> Manifest:
    """Build a :class:`Manifest` from concrete model classes."""
    tables: list[TableDef] = []
    seen: set[str] = set()
    for model in models:
        table = _table_def_from_model(model)
        if table.qualified_name in seen:
            raise SchemaError(
                f"duplicate table in manifest: {table.qualified_name} "
                f"(model {table.model_qualname})"
            )
        seen.add(table.qualified_name)
        tables.append(table)
    tables.sort(key=lambda t: t.qualified_name)
    return Manifest(tables=tuple(tables), meta=dict(meta or {}))


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    """JSON-friendly dict (enums/logical types as strings)."""
    return {
        "manifest_version": manifest.manifest_version,
        "meta": dict(manifest.meta),
        "tables": [_table_to_dict(t) for t in manifest.tables],
    }


def manifest_from_dict(data: dict[str, Any]) -> Manifest:
    """Parse a dict produced by :func:`manifest_to_dict`."""
    version = int(data.get("manifest_version", MANIFEST_VERSION))
    if version != MANIFEST_VERSION:
        raise SchemaError(
            f"unsupported manifest_version {version}; this build understands "
            f"{MANIFEST_VERSION} only"
        )
    tables = tuple(_table_from_dict(t) for t in data.get("tables", []))
    return Manifest(tables=tables, manifest_version=version, meta=dict(data.get("meta") or {}))


def manifest_to_json(manifest: Manifest, *, indent: int | None = 2) -> str:
    return json.dumps(manifest_to_dict(manifest), indent=indent, sort_keys=True) + (
        "\n" if indent is not None else ""
    )


def manifest_from_json(text: str) -> Manifest:
    return manifest_from_dict(json.loads(text))


def _table_def_from_model(model: type[Model]) -> TableDef:
    info = get_table_info(model)
    columns: list[ColumnDef] = []
    indexes: list[IndexDef] = []
    constraints: list[ConstraintDef] = []

    for field_name, field_info in model.model_fields.items():
        col_meta = info.columns[field_name]
        ann = field_info.annotation
        # File/Image fields store object-storage keys as strings, not blobs.
        logical = LogicalType.STR if col_meta.file_kind else infer_logical_type(ann)
        evalues = None if col_meta.file_kind else enum_values(ann)
        max_len = field_max_length(field_info)

        nullable = False if col_meta.primary_key else (not field_info.is_required())
        autoincrement = _resolve_autoincrement(
            col_meta,
            logical=logical,
            primary_key_cols=info.primary_key,
            field_name=field_name,
        )
        server_default = col_meta.server_default
        if server_default is None and col_meta.auto_now_add:
            # Portable-ish defaults; dialects refine at DDL emit.
            server_default = "CURRENT_TIMESTAMP"

        # Prefer VARCHAR when max_length is set (unless db_type override).
        db_type = col_meta.db_type
        if db_type is None and logical is LogicalType.STR and max_len:
            db_type = f"VARCHAR({max_len})"

        columns.append(
            ColumnDef(
                name=field_name,
                logical_type=logical,
                nullable=nullable,
                primary_key=col_meta.primary_key,
                unique=col_meta.unique,
                index=col_meta.index,
                foreign_key=col_meta.foreign_key,
                on_delete=_on_delete_str(col_meta.on_delete),
                server_default=server_default,
                db_type=db_type,
                renamed_from=col_meta.renamed_from,
                archive_on_remove=col_meta.archive_on_remove,
                admin_hidden=col_meta.admin_hidden,
                admin_readonly=col_meta.admin_readonly,
                admin_exclude=col_meta.admin_exclude,
                file_kind=col_meta.file_kind,
                autoincrement=autoincrement,
                auto_now_add=col_meta.auto_now_add,
                auto_now=col_meta.auto_now,
                optimistic=col_meta.optimistic,
                max_length=max_len,
                enum_values=evalues,
                generated=col_meta.generated,
                on_update=col_meta.on_update,
                pg_enum_name=(f"{info.name}_{field_name}_enum" if evalues is not None else None),
            )
        )

        if col_meta.unique and not col_meta.primary_key:
            indexes.append(
                IndexDef(
                    name=f"uq_{info.name}_{field_name}",
                    columns=(field_name,),
                    unique=True,
                )
            )
        elif col_meta.index and not col_meta.primary_key and not col_meta.unique:
            indexes.append(
                IndexDef(
                    name=f"ix_{info.name}_{field_name}",
                    columns=(field_name,),
                    unique=False,
                )
            )

        if col_meta.foreign_key:
            ref_table, ref_col = _split_fk(col_meta.foreign_key, model_name=model.__qualname__)
            constraints.append(
                ConstraintDef(
                    name=f"fk_{info.name}_{field_name}",
                    kind="foreign_key",
                    columns=(field_name,),
                    ref_table=ref_table,
                    ref_columns=(ref_col,),
                    on_delete=_on_delete_str(col_meta.on_delete),
                )
            )

        # CHECK enum for non-Postgres; PG uses CREATE TYPE (render_enum_ddl).
        if evalues is not None:
            literals = ", ".join(_sql_literal(v) for v in evalues)
            constraints.append(
                ConstraintDef(
                    name=f"ck_{info.name}_{field_name}_enum",
                    kind="check",
                    columns=(field_name,),
                    expression=f"{field_name} IN ({literals})",
                )
            )

    # Meta.unique_together / Meta.indexes / Meta.checks
    meta_cls = getattr(model, "Meta", None)
    if meta_cls is not None:
        _apply_meta_table_options(
            meta_cls,
            table=info.name,
            indexes=indexes,
            constraints=constraints,
        )

    return TableDef(
        name=info.name,
        schema_name=info.schema_name,
        columns=tuple(columns),
        primary_key=info.primary_key,
        indexes=tuple(indexes),
        constraints=tuple(constraints),
        model_qualname=info.model_qualname,
    )


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("'", "''")
    return f"'{s}'"


def _apply_meta_table_options(
    meta_cls: Any,
    *,
    table: str,
    indexes: list[IndexDef],
    constraints: list[ConstraintDef],
) -> None:
    """Meta.unique_together, Meta.indexes, Meta.checks."""
    for cols in getattr(meta_cls, "unique_together", ()) or ():
        col_t = tuple(cols) if not isinstance(cols, str) else (cols,)
        if not col_t:
            continue
        indexes.append(
            IndexDef(
                name=f"uq_{table}_{'_'.join(col_t)}"[:60],
                columns=col_t,
                unique=True,
            )
        )
    for cols in getattr(meta_cls, "indexes", ()) or ():
        # Allow dict form: {"columns": [...], "where": "...", "using": "gin"}
        if isinstance(cols, dict):
            col_t = tuple(cols.get("columns") or cols.get("expressions") or ())
            indexes.append(
                IndexDef(
                    name=str(cols.get("name") or f"ix_{table}_{'_'.join(map(str, col_t))}")[:60],
                    columns=tuple(cols.get("columns") or ()),
                    unique=bool(cols.get("unique", False)),
                    where=cols.get("where"),
                    using=cols.get("using"),
                    expressions=tuple(cols.get("expressions") or ()),
                )
            )
            continue
        col_t = tuple(cols) if not isinstance(cols, str) else (cols,)
        if not col_t:
            continue
        indexes.append(
            IndexDef(
                name=f"ix_{table}_{'_'.join(col_t)}"[:60],
                columns=col_t,
                unique=False,
            )
        )
    for i, expr in enumerate(getattr(meta_cls, "checks", ()) or ()):
        if not expr or not str(expr).strip():
            continue
        constraints.append(
            ConstraintDef(
                name=f"ck_{table}_{i}",
                kind="check",
                expression=str(expr).strip(),
            )
        )


def _on_delete_str(value: OnDelete | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, OnDelete):
        return value.value
    return value


def _resolve_autoincrement(
    col_meta: Any,
    *,
    logical: LogicalType,
    primary_key_cols: tuple[str, ...],
    field_name: str,
) -> bool:
    """Default: single integer PK is autoincrement unless explicitly disabled."""
    if col_meta.autoincrement is not None:
        return bool(col_meta.autoincrement)
    if not col_meta.primary_key:
        return False
    if len(primary_key_cols) != 1 or primary_key_cols[0] != field_name:
        return False
    if col_meta.foreign_key:
        return False
    return logical is LogicalType.INT


def _split_fk(ref: str, *, model_name: str) -> tuple[str, str]:
    if "." not in ref:
        raise SchemaError(f"{model_name}: foreign_key must be 'table.column', got {ref!r}")
    table, col = ref.split(".", 1)
    if not table or not col:
        raise SchemaError(f"{model_name}: invalid foreign_key {ref!r}")
    return table, col


def _table_to_dict(table: TableDef) -> dict[str, Any]:
    return {
        "name": table.name,
        "schema_name": table.schema_name,
        "model_qualname": table.model_qualname,
        "primary_key": list(table.primary_key),
        "columns": [
            {
                **{k: v for k, v in asdict(c).items() if k != "logical_type"},
                "logical_type": c.logical_type.value,
            }
            for c in table.columns
        ],
        "indexes": [asdict(i) | {"columns": list(i.columns)} for i in table.indexes],
        "constraints": [
            asdict(c)
            | {
                "columns": list(c.columns),
                "ref_columns": list(c.ref_columns),
            }
            for c in table.constraints
        ],
    }


def _table_from_dict(data: dict[str, Any]) -> TableDef:
    columns = tuple(
        ColumnDef(
            name=c["name"],
            logical_type=LogicalType(c["logical_type"]),
            nullable=bool(c.get("nullable", True)),
            primary_key=bool(c.get("primary_key", False)),
            unique=bool(c.get("unique", False)),
            index=bool(c.get("index", False)),
            foreign_key=c.get("foreign_key"),
            on_delete=c.get("on_delete"),
            server_default=c.get("server_default"),
            db_type=c.get("db_type"),
            renamed_from=c.get("renamed_from"),
            archive_on_remove=c.get("archive_on_remove"),
            admin_hidden=bool(c.get("admin_hidden", False)),
            admin_readonly=bool(c.get("admin_readonly", False)),
            admin_exclude=bool(c.get("admin_exclude", False)),
            file_kind=c.get("file_kind"),
            autoincrement=bool(c.get("autoincrement", False)),
            auto_now_add=bool(c.get("auto_now_add", False)),
            auto_now=bool(c.get("auto_now", False)),
            optimistic=bool(c.get("optimistic", False)),
            max_length=c.get("max_length"),
            enum_values=tuple(c["enum_values"]) if c.get("enum_values") is not None else None,
        )
        for c in data.get("columns", [])
    )
    indexes = tuple(
        IndexDef(
            name=i["name"],
            columns=tuple(i["columns"]),
            unique=bool(i.get("unique", False)),
        )
        for i in data.get("indexes", [])
    )
    constraints = tuple(
        ConstraintDef(
            name=c["name"],
            kind=c["kind"],
            columns=tuple(c.get("columns") or ()),
            ref_table=c.get("ref_table") or "",
            ref_columns=tuple(c.get("ref_columns") or ()),
            on_delete=c.get("on_delete"),
            expression=c.get("expression"),
        )
        for c in data.get("constraints", [])
    )
    return TableDef(
        name=data["name"],
        schema_name=data.get("schema_name"),
        columns=columns,
        primary_key=tuple(data.get("primary_key") or []),
        indexes=indexes,
        constraints=constraints,
        model_qualname=data.get("model_qualname"),
    )
