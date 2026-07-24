"""ResourceConfig — admin resource metadata inferred from models."""

from __future__ import annotations

import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, get_args, get_origin

from phzyx.schema.field import get_column_meta
from phzyx.schema.model import Model, get_table_info

# Diamond D3/D4 form widgets
WIDGET_TEXT = "text"
WIDGET_NUMBER = "number"
WIDGET_BOOL = "bool"
WIDGET_DATE = "date"
WIDGET_DATETIME = "datetime"
WIDGET_TEXTAREA = "textarea"
WIDGET_JSON = "json"
WIDGET_FILE = "file"
WIDGET_FK = "fk"
WIDGET_M2M = "m2m"


@dataclass(frozen=True, slots=True)
class ColumnConfig:
    name: str
    label: str
    readonly: bool = False
    searchable: bool = False
    sortable: bool = True
    exportable: bool = True
    hidden: bool = False
    file_kind: str | None = None
    secret: bool = False
    filterable: bool = False
    filter_type: str = "text"  # text | bool | number | choice
    filter_ops: tuple[str, ...] = ()  # empty → defaults by filter_type
    widget: str = WIDGET_TEXT
    required: bool = False
    autoincrement: bool = False  # single int PK — omit on create
    # Field-RBAC permission codes (optional)
    read_perm: str | None = None  # e.g. users:field:email:read
    write_perm: str | None = None
    # Diamond D4 — foreign key
    fk_resource: str | None = None
    fk_column: str | None = None
    fk_label_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FieldsetConfig:
    """Logical form section (Diamond D3)."""

    name: str
    label: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RelationConfig:
    """Relation panel / M2M multi-select (Diamond D4 / D4.5).

    * ``has_many`` — reverse FK: related resource has ``foreign_key`` → this.
    * ``m2m`` — through table: ``through`` resource with
      ``through_local`` → parent PK and ``through_remote`` → related PK.
    """

    name: str
    label: str
    resource: str
    foreign_key: str = ""  # has_many only
    kind: str = "has_many"  # has_many | m2m
    through: str | None = None  # m2m through resource name
    through_local: str | None = None  # column on through → parent
    through_remote: str | None = None  # column on through → related


@dataclass(frozen=True, slots=True)
class ResourceConfig:
    name: str
    model: type[Model]
    label: str
    columns: tuple[ColumnConfig, ...]
    primary_key: tuple[str, ...]
    searchable: tuple[str, ...] = ()
    filterable: tuple[str, ...] = ()
    fieldsets: tuple[FieldsetConfig, ...] = ()
    relations: tuple[RelationConfig, ...] = ()
    default_sort: str | None = None
    readonly: bool = False

    def column(self, name: str) -> ColumnConfig | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def relation(self, name: str) -> RelationConfig | None:
        for r in self.relations:
            if r.name == name:
                return r
        return None

    def exportable_columns(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.exportable and not c.secret and not c.hidden)

    def public_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "primary_key": list(self.primary_key),
            "readonly": self.readonly,
            "searchable": list(self.searchable),
            "filterable": list(self.filterable),
            "default_sort": self.default_sort,
            "fieldsets": [
                {"name": fs.name, "label": fs.label, "fields": list(fs.fields)}
                for fs in self.fieldsets
            ],
            "relations": [
                {
                    "name": r.name,
                    "label": r.label,
                    "resource": r.resource,
                    "foreign_key": r.foreign_key,
                    "kind": r.kind,
                    "through": r.through,
                    "through_local": r.through_local,
                    "through_remote": r.through_remote,
                }
                for r in self.relations
            ],
            "columns": [
                {
                    "name": c.name,
                    "label": c.label,
                    "readonly": c.readonly,
                    "searchable": c.searchable,
                    "sortable": c.sortable,
                    "exportable": c.exportable and not c.secret,
                    "hidden": c.hidden,
                    "file_kind": c.file_kind,
                    "filterable": c.filterable,
                    "filter_type": c.filter_type,
                    "filter_ops": list(c.filter_ops or _default_filter_ops(c.filter_type)),
                    "widget": c.widget,
                    "required": c.required and not c.autoincrement,
                    "autoincrement": c.autoincrement,
                    "read_perm": c.read_perm,
                    "write_perm": c.write_perm,
                    "fk_resource": c.fk_resource,
                    "fk_column": c.fk_column,
                    "fk_label_fields": list(c.fk_label_fields),
                }
                for c in self.columns
                if not c.secret
            ],
        }


def _default_filter_ops(filter_type: str) -> tuple[str, ...]:
    if filter_type == "bool":
        return ("eq", "ne")
    if filter_type == "number":
        return ("eq", "ne", "lt", "lte", "gt", "gte", "in", "is_null", "is_not_null")
    # text / date / choice
    return (
        "eq",
        "ne",
        "contains",
        "startswith",
        "endswith",
        "in",
        "is_null",
        "is_not_null",
    )


def _unwrap_optional(ann: Any) -> Any:
    origin = get_origin(ann)
    if origin is types.UnionType or str(origin) == "typing.Union":
        args = [a for a in get_args(ann) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return ann


def _parse_fk_ref(ref: str) -> tuple[str, str] | None:
    if not ref or "." not in ref:
        return None
    table, col = ref.split(".", 1)
    table, col = table.strip(), col.strip()
    if not table or not col:
        return None
    return table, col


def _infer_widget(
    ann: Any,
    *,
    file_kind: str | None,
    field_name: str,
    fk_resource: str | None,
) -> str:
    if fk_resource:
        return WIDGET_FK
    if file_kind:
        return WIDGET_FILE
    core = _unwrap_optional(ann)
    if core is bool:
        return WIDGET_BOOL
    if core is int or core is float:
        return WIDGET_NUMBER
    if core is date and core is not datetime:
        return WIDGET_DATE
    if core is datetime:
        return WIDGET_DATETIME
    lower = field_name.lower()
    if lower in {"notes", "description", "body", "bio", "content"}:
        return WIDGET_TEXTAREA
    if lower in {"meta", "metadata", "json", "payload", "config", "settings"}:
        return WIDGET_JSON
    if isinstance(core, type) and issubclass(core, dict):
        return WIDGET_JSON
    return WIDGET_TEXT


def _default_fieldsets(
    columns: Sequence[ColumnConfig],
    primary_key: Sequence[str],
) -> tuple[FieldsetConfig, ...]:
    visible = [c.name for c in columns if not c.hidden and not c.secret]
    if not visible:
        return ()
    pk_set = set(primary_key)
    identity = [n for n in visible if n in pk_set]
    details = [n for n in visible if n not in pk_set]
    sets: list[FieldsetConfig] = []
    if identity:
        sets.append(FieldsetConfig(name="identity", label="Identity", fields=tuple(identity)))
    if details:
        sets.append(FieldsetConfig(name="details", label="Details", fields=tuple(details)))
    if not sets:
        sets.append(FieldsetConfig(name="fields", label="Fields", fields=tuple(visible)))
    return tuple(sets)


def _default_label_fields(target: ResourceConfig | None) -> tuple[str, ...]:
    if target is None:
        return ("name", "email", "title")
    preferred = ("name", "email", "title", "label")
    out = [p for p in preferred if target.column(p) is not None]
    if out:
        return tuple(out)
    # first searchable / first non-pk
    for c in target.columns:
        if c.searchable and not c.hidden:
            return (c.name,)
    for c in target.columns:
        if c.name not in target.primary_key and not c.hidden:
            return (c.name,)
    return target.primary_key[:1]


def infer_resource(
    model: type[Model],
    *,
    name: str | None = None,
    label: str | None = None,
) -> ResourceConfig:
    """Auto-infer ResourceConfig from a Phzyx Model."""
    info = get_table_info(model)
    res_name = name or info.name
    columns: list[ColumnConfig] = []
    searchable: list[str] = []
    filterable: list[str] = []
    for field_name, field_info in model.model_fields.items():
        meta = get_column_meta(field_info)
        hidden = bool(meta and meta.admin_hidden)
        readonly = bool(meta and meta.admin_readonly)
        secret = bool(meta and meta.admin_exclude)
        file_kind = meta.file_kind if meta else None
        fk_resource: str | None = None
        fk_column: str | None = None
        if meta and meta.foreign_key:
            parsed = _parse_fk_ref(meta.foreign_key)
            if parsed:
                fk_resource, fk_column = parsed
        ann = field_info.annotation
        core = _unwrap_optional(ann)
        is_str = core is str or (isinstance(core, type) and issubclass(core, str))
        is_bool = core is bool
        is_int = core is int
        is_date = core is date and core is not datetime
        searchable_col = is_str and not secret and not hidden and not file_kind
        if searchable_col:
            searchable.append(field_name)
        filter_type = "text"
        filterable_col = False
        if not secret and not hidden and not file_kind:
            if is_bool:
                filterable_col = True
                filter_type = "bool"
            elif is_int and field_name not in info.primary_key and not fk_resource:
                filterable_col = True
                filter_type = "number"
            elif (is_str and field_name not in info.primary_key) or is_date:
                filterable_col = True
                filter_type = "text"
            elif fk_resource:
                filterable_col = True
                filter_type = "number" if is_int else "text"
        if filterable_col:
            filterable.append(field_name)
        widget = _infer_widget(
            ann, file_kind=file_kind, field_name=field_name, fk_resource=fk_resource
        )
        required = bool(field_info.is_required()) and not secret
        is_single_int_pk = (
            field_name in info.primary_key
            and len(info.primary_key) == 1
            and is_int
            and not fk_resource
        )
        columns.append(
            ColumnConfig(
                name=field_name,
                label=field_name.replace("_", " ").title(),
                readonly=readonly or field_name in info.primary_key,
                searchable=searchable_col,
                sortable=not secret,
                exportable=not secret,
                hidden=hidden,
                file_kind=file_kind,
                secret=secret,
                filterable=filterable_col,
                filter_type=filter_type,
                filter_ops=_default_filter_ops(filter_type) if filterable_col else (),
                widget=widget,
                required=required and not is_single_int_pk,
                autoincrement=is_single_int_pk,
                fk_resource=fk_resource,
                fk_column=fk_column,
            )
        )
    cols = tuple(columns)
    return ResourceConfig(
        name=res_name,
        model=model,
        label=label or res_name.replace("_", " ").title(),
        columns=cols,
        primary_key=info.primary_key,
        searchable=tuple(searchable),
        filterable=tuple(filterable),
        fieldsets=_default_fieldsets(cols, info.primary_key),
        default_sort=info.primary_key[0] if info.primary_key else None,
    )


def wire_relations(
    resources: Mapping[str, ResourceConfig],
) -> dict[str, ResourceConfig]:
    """Fill fk_label_fields + reverse has_many + auto-detect M2M through tables."""
    by_name = dict(resources)
    reverse: dict[str, list[RelationConfig]] = {k: [] for k in by_name}
    # table name → resource name (infer default uses table as name)
    by_table: dict[str, str] = {}
    for name, res in by_name.items():
        table = getattr(getattr(res.model, "Meta", None), "table", None) or name
        by_table[str(table)] = name
        by_table[name] = name

    for res in list(by_name.values()):
        new_cols: list[ColumnConfig] = []
        for c in res.columns:
            if c.fk_resource:
                # Resolve table name to resource name when possible
                target_name = by_table.get(c.fk_resource, c.fk_resource)
                target = by_name.get(target_name)
                labels = _default_label_fields(target)
                new_cols.append(
                    replace(
                        c,
                        fk_resource=target_name if target else c.fk_resource,
                        fk_label_fields=labels,
                        widget=WIDGET_FK,
                    )
                )
                side = target_name if target else c.fk_resource
                if side in reverse:
                    rel_name = res.name
                    if not any(r.name == rel_name for r in reverse[side]):
                        reverse[side].append(
                            RelationConfig(
                                name=rel_name,
                                label=res.label,
                                resource=res.name,
                                foreign_key=c.name,
                                kind="has_many",
                            )
                        )
            else:
                new_cols.append(c)
        by_name[res.name] = replace(res, columns=tuple(new_cols))

    # Auto-detect M2M: composite PK of exactly two FK columns to two different resources
    for through_name, through in list(by_name.items()):
        if len(through.primary_key) != 2:
            continue
        fk_cols = [c for c in through.columns if c.name in through.primary_key and c.fk_resource]
        if len(fk_cols) != 2:
            continue
        a, b = fk_cols[0], fk_cols[1]
        left = by_table.get(str(a.fk_resource), str(a.fk_resource))
        right = by_table.get(str(b.fk_resource), str(b.fk_resource))
        if left not in by_name or right not in by_name or left == right:
            continue
        # left → right via through
        reverse.setdefault(left, []).append(
            RelationConfig(
                name=right,
                label=by_name[right].label,
                resource=right,
                foreign_key="",
                kind="m2m",
                through=through_name,
                through_local=a.name,
                through_remote=b.name,
            )
        )
        reverse.setdefault(right, []).append(
            RelationConfig(
                name=left,
                label=by_name[left].label,
                resource=left,
                foreign_key="",
                kind="m2m",
                through=through_name,
                through_local=b.name,
                through_remote=a.name,
            )
        )

    for name, rels in reverse.items():
        if not rels or name not in by_name:
            continue
        base = by_name[name]
        existing = {r.name: r for r in base.relations}
        for r in rels:
            existing.setdefault(r.name, r)
        by_name[name] = replace(base, relations=tuple(existing.values()))

    return by_name


def m2m_relation(
    *,
    name: str,
    label: str | None = None,
    resource: str,
    through: str,
    through_local: str,
    through_remote: str,
) -> RelationConfig:
    """Explicit many-to-many relation descriptor (Diamond D4.5)."""
    return RelationConfig(
        name=name,
        label=label or name.replace("_", " ").title(),
        resource=resource,
        foreign_key="",
        kind="m2m",
        through=through,
        through_local=through_local,
        through_remote=through_remote,
    )


def override_resource(
    base: ResourceConfig,
    *,
    label: str | None = None,
    readonly: bool | None = None,
    hide: Sequence[str] = (),
    secrets: Sequence[str] = (),
    fieldsets: Sequence[FieldsetConfig] | None = None,
    relations: Sequence[RelationConfig] | None = None,
) -> ResourceConfig:
    """Apply explicit overrides on an inferred resource."""
    hide_set = set(hide)
    secret_set = set(secrets)
    cols = []
    for c in base.columns:
        cols.append(
            replace(
                c,
                hidden=c.hidden or c.name in hide_set,
                secret=c.secret or c.name in secret_set,
                exportable=c.exportable and c.name not in secret_set,
            )
        )
    return replace(
        base,
        label=label or base.label,
        readonly=base.readonly if readonly is None else readonly,
        columns=tuple(cols),
        fieldsets=tuple(fieldsets) if fieldsets is not None else base.fieldsets,
        relations=tuple(relations) if relations is not None else base.relations,
    )
