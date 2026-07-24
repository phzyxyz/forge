"""Manifest IR — desired-state schema graph (versioned, JSON-serializable)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from phzyx.schema.errors import SchemaError
from phzyx.schema.field import OnDelete
from phzyx.schema.model import Model, get_table_info
from phzyx.schema.types import LogicalType, infer_logical_type

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


@dataclass(frozen=True, slots=True)
class IndexDef:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True, slots=True)
class ConstraintDef:
    """Named table constraint (currently foreign keys)."""

    name: str
    kind: Literal["foreign_key"]
    columns: tuple[str, ...]
    ref_table: str
    ref_columns: tuple[str, ...]
    on_delete: str | None = None


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

        nullable = False if col_meta.primary_key else (not field_info.is_required())

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
                server_default=col_meta.server_default,
                db_type=col_meta.db_type,
                renamed_from=col_meta.renamed_from,
                archive_on_remove=col_meta.archive_on_remove,
                admin_hidden=col_meta.admin_hidden,
                admin_readonly=col_meta.admin_readonly,
                admin_exclude=col_meta.admin_exclude,
                file_kind=col_meta.file_kind,
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

    return TableDef(
        name=info.name,
        schema_name=info.schema_name,
        columns=tuple(columns),
        primary_key=info.primary_key,
        indexes=tuple(indexes),
        constraints=tuple(constraints),
        model_qualname=info.model_qualname,
    )


def _on_delete_str(value: OnDelete | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, OnDelete):
        return value.value
    return value


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
            columns=tuple(c["columns"]),
            ref_table=c["ref_table"],
            ref_columns=tuple(c["ref_columns"]),
            on_delete=c.get("on_delete"),
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
