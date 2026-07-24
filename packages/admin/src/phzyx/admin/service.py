"""AdminService — headless CRUD, export, copy (session-backed)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from phzyx.admin.audit import AuditLog
from phzyx.admin.auth import AllowAll, AllowAllFields, Authz, FieldAuthz, require_authz
from phzyx.admin.errors import NotFoundError, ValidationAdminError
from phzyx.admin.export_copy import copy_payload, export_csv, export_json
from phzyx.admin.identity import decode_identity, encode_identity
from phzyx.admin.resource import ResourceConfig
from phzyx.admin.security import assert_no_mass_assignment
from phzyx.admin.stream_export import (
    DEFAULT_EXPORT_POLICY,
    ExportPolicy,
    export_xlsx,
    stream_csv,
    stream_json_array,
    stream_jsonl,
)
from phzyx.orm.expr import (
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
    or_,
)
from phzyx.orm.keyset import default_order_columns, order_from_columns
from phzyx.orm.session_sync import Session

_FILTER_OPS = frozenset(
    {
        "eq",
        "ne",
        "lt",
        "lte",
        "gt",
        "gte",
        "like",
        "ilike",
        "contains",
        "startswith",
        "endswith",
        "in",
        "is_null",
        "is_not_null",
    }
)


@dataclass
class ListResult:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    pagination: str = "offset"


@dataclass
class AdminService:
    """Headless admin operations over registered resources + a sync Session."""

    resources: dict[str, ResourceConfig]
    session: Session
    authz: Authz = field(default_factory=AllowAll)
    field_authz: FieldAuthz = field(default_factory=AllowAllFields)
    audit: AuditLog | None = None

    def list_resources(self, *, principal: Any | None = None) -> list[dict[str, Any]]:
        return [self.public_schema(r.name, principal=principal) for r in self.resources.values()]

    def get_resource(self, name: str) -> ResourceConfig:
        if name not in self.resources:
            raise NotFoundError(f"unknown resource {name}")
        return self.resources[name]

    def public_schema(self, name: str, *, principal: Any | None = None) -> dict[str, Any]:
        res = self.get_resource(name)
        schema = res.public_schema()
        # Field-RBAC: drop unreadable columns from schema
        cols = []
        for c in schema.get("columns") or []:
            fname = c.get("name")
            if fname and not self.field_authz.allow_read(principal, name, str(fname)):
                continue
            cols.append(c)
        schema["columns"] = cols
        schema["filter_ops"] = sorted(_FILTER_OPS)
        return schema

    def _build_where(
        self,
        res: ResourceConfig,
        *,
        search: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[Any]:
        where: list[Any] = []
        if search and res.searchable:
            q = f"%{search}%"
            parts = [ilike(col, q) for col in res.searchable]
            where.append(parts[0] if len(parts) == 1 else or_(*parts))
        if filters:
            allowed = set(res.filterable) | {c.name for c in res.columns if c.filterable}
            for key, raw in filters.items():
                col, op = self._parse_filter_key(key)
                if col not in allowed:
                    continue
                cfg = res.column(col)
                if cfg is None:
                    continue
                filt = self._filter_expr(col, op, raw, cfg.filter_type)
                if filt is not None:
                    where.append(filt)
        return where

    def _parse_filter_key(self, key: str) -> tuple[str, str]:
        """field or field__op → (field, op). Default op eq."""
        if "__" in key:
            col, op = key.rsplit("__", 1)
            op = op.lower()
            if op in _FILTER_OPS:
                return col, op
        # value form op:value handled in _filter_expr when op is eq
        return key, "eq"

    def _filter_expr(self, col: str, op: str, raw: str, filter_type: str) -> Any | None:
        # Allow filter.field=contains:foo shorthand when op is eq
        if op == "eq" and ":" in raw:
            maybe_op, rest = raw.split(":", 1)
            if maybe_op.lower() in _FILTER_OPS:
                op, raw = maybe_op.lower(), rest
        if op in {"is_null", "isnull"}:
            return is_null(col)
        if op in {"is_not_null", "isnotnull"}:
            return is_not_null(col)
        if op == "in":
            parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
            vals: list[Any] = []
            for p in parts:
                vals.append(self._coerce_filter_val(p, filter_type))
            return in_(col, vals)
        val = self._coerce_filter_val(raw, filter_type)
        if op == "eq":
            return eq(col, val)
        if op == "ne":
            return ne(col, val)
        if op == "lt":
            return lt(col, val)
        if op == "lte":
            return lte(col, val)
        if op == "gt":
            return gt(col, val)
        if op == "gte":
            return gte(col, val)
        if op == "like":
            return like(col, str(val))
        if op == "ilike":
            return ilike(col, str(val))
        if op == "contains":
            return ilike(col, f"%{val}%")
        if op == "startswith":
            return ilike(col, f"{val}%")
        if op == "endswith":
            return ilike(col, f"%{val}")
        return eq(col, val)

    def _coerce_filter_val(self, raw: str, filter_type: str) -> Any:
        if filter_type == "bool":
            return raw.lower() in {"1", "true", "yes", "on"}
        if filter_type == "number":
            try:
                return int(raw) if "." not in raw else float(raw)
            except ValueError:
                return raw
        return raw

    def list(
        self,
        name: str,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        cursor: str | None = None,
        filters: dict[str, str] | None = None,
        pagination: str = "offset",
        principal: Any | None = None,
    ) -> ListResult:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "list", name)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        where = self._build_where(res, search=search, filters=filters)
        order = order_from_columns(default_order_columns(res.model))
        use_keyset = pagination == "keyset" or cursor is not None
        if use_keyset:
            page_data = self.session.query_keyset(
                res.model,
                where=where,
                order_by=order,
                limit=page_size,
                cursor=cursor,
            )
            items = [self._serialize(res, r, principal=principal) for r in page_data.items]
            total = len(self.session.query(res.model, where=where))
            return ListResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                next_cursor=page_data.next_cursor,
                prev_cursor=page_data.prev_cursor,
                has_more=page_data.has_more,
                pagination="keyset",
            )
        rows = self.session.query(
            res.model,
            where=where,
            order_by=order,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        all_rows = self.session.query(res.model, where=where)
        items = [self._serialize(res, r, principal=principal) for r in rows]
        return ListResult(
            items=items,
            total=len(all_rows),
            page=page,
            page_size=page_size,
            pagination="offset",
        )

    def bulk_action(
        self,
        name: str,
        action: str,
        identities: Sequence[str],
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        from phzyx.admin.actions import run_bulk_action

        return run_bulk_action(self, name, action, identities, principal=principal)

    def run_action(
        self,
        name: str,
        action: str,
        identities: Sequence[str] | None = None,
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        """Run row/bulk server action (Diamond D5)."""
        from phzyx.admin.actions import run_admin_action

        return run_admin_action(self, name, action, identities, principal=principal)

    def list_bulk_actions(self, name: str) -> list[dict[str, Any]]:
        from phzyx.admin.actions import list_bulk_actions

        res = self.get_resource(name)
        has_active = any(c.name == "active" for c in res.columns)
        return list_bulk_actions(name, has_active)

    def list_actions(self, name: str, *, scope: str | None = None) -> list[dict[str, Any]]:
        """List action catalog for SPA menus (Diamond D5)."""
        from phzyx.admin.actions import list_admin_actions

        res = self.get_resource(name)
        has_active = any(c.name == "active" for c in res.columns)
        return list_admin_actions(name, has_active=has_active, scope=scope)

    def autocomplete(
        self,
        name: str,
        *,
        q: str = "",
        limit: int = 20,
        principal: Any | None = None,
    ) -> list[dict[str, Any]]:
        """FK typeahead options for a resource (Diamond D4)."""
        res = self.get_resource(name)
        require_authz(self.authz, principal, "list", name)
        limit = min(max(1, limit), 50)
        listed = self.list(
            name,
            page=1,
            page_size=limit,
            search=q or None,
            principal=principal,
        )
        label_fields = (
            list(res.searchable)
            or [c.name for c in res.columns if c.name not in res.primary_key and not c.hidden][:3]
        )
        out: list[dict[str, Any]] = []
        for item in listed.items:
            if len(res.primary_key) == 1:
                value = item.get(res.primary_key[0])
            else:
                value = item.get("_identity")
            parts = [str(item.get(f) or "") for f in label_fields if item.get(f) not in (None, "")]
            label = " · ".join(parts) if parts else str(value)
            out.append(
                {
                    "value": value,
                    "label": label,
                    "identity": item.get("_identity"),
                    "record": item,
                }
            )
        return out

    def list_relation(
        self,
        name: str,
        identity: str,
        relation: str,
        *,
        page: int = 1,
        page_size: int = 50,
        principal: Any | None = None,
    ) -> ListResult:
        """List has-many or M2M related rows (Diamond D4 / D4.5)."""
        parent = self.get_resource(name)
        require_authz(self.authz, principal, "list", name)
        rel = parent.relation(relation)
        if rel is None:
            raise NotFoundError(f"unknown relation {relation}")
        parent_row = self.get(name, identity, principal=principal)
        if len(parent.primary_key) == 1:
            local_pk = parent_row.get(parent.primary_key[0])
        else:
            local_pk = parent_row.get(parent.primary_key[0])

        if rel.kind == "m2m":
            return self._list_m2m(
                parent,
                local_pk,
                rel,
                page=page,
                page_size=page_size,
                principal=principal,
            )

        if not rel.foreign_key:
            raise ValidationAdminError("relation missing foreign_key")
        return self.list(
            rel.resource,
            page=page,
            page_size=page_size,
            filters={rel.foreign_key: str(local_pk)},
            principal=principal,
        )

    def _coerce_pk(self, v: Any) -> Any:
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v

    def _through_link_objs(
        self,
        through: ResourceConfig,
        local_col: str,
        local_pk: Any,
    ) -> list[Any]:
        """Load through-table rows for one parent side (always applies local filter)."""
        return self.session.query(
            through.model,
            where=[eq(local_col, self._coerce_pk(local_pk))],
            limit=10_000,
        )

    def _list_m2m(
        self,
        parent: ResourceConfig,
        local_pk: Any,
        rel: Any,
        *,
        page: int,
        page_size: int,
        principal: Any | None,
    ) -> ListResult:
        if not rel.through or not rel.through_local or not rel.through_remote:
            raise ValidationAdminError("m2m relation requires through/local/remote")
        through = self.get_resource(rel.through)
        require_authz(self.authz, principal, "list", rel.through)
        link_objs = self._through_link_objs(through, rel.through_local, local_pk)
        remote_ids = [
            str(getattr(obj, rel.through_remote))
            for obj in link_objs
            if getattr(obj, rel.through_remote, None) is not None
        ]
        related = self.get_resource(rel.resource)
        require_authz(self.authz, principal, "list", rel.resource)
        if not remote_ids:
            return ListResult(items=[], total=0, page=page, page_size=page_size)
        # fetch related rows; filter in memory (portable across dialects)
        all_rows = self.list(rel.resource, page=1, page_size=10_000, principal=principal).items
        pk = related.primary_key[0] if related.primary_key else "id"
        id_set = set(remote_ids)
        matched = [r for r in all_rows if str(r.get(pk)) in id_set]
        total = len(matched)
        start = (max(1, page) - 1) * page_size
        end = start + page_size
        return ListResult(
            items=matched[start:end],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_m2m_ids(
        self,
        name: str,
        identity: str,
        relation: str,
        *,
        principal: Any | None = None,
    ) -> list[str]:
        """Return related PKs for an M2M relation (for multi-select forms)."""
        parent = self.get_resource(name)
        require_authz(self.authz, principal, "get", name)
        rel = parent.relation(relation)
        if rel is None or rel.kind != "m2m":
            raise NotFoundError(f"unknown m2m relation {relation}")
        if not rel.through or not rel.through_local or not rel.through_remote:
            raise ValidationAdminError("m2m relation incomplete")
        through = self.get_resource(rel.through)
        require_authz(self.authz, principal, "list", rel.through)
        parent_row = self.get(name, identity, principal=principal)
        local_pk = parent_row.get(parent.primary_key[0])
        link_objs = self._through_link_objs(through, rel.through_local, local_pk)
        return [
            str(getattr(obj, rel.through_remote))
            for obj in link_objs
            if getattr(obj, rel.through_remote, None) is not None
        ]

    def set_m2m(
        self,
        name: str,
        identity: str,
        relation: str,
        ids: Sequence[str | int],
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        """Replace M2M links for parent identity (Diamond D4.5 save round-trip)."""
        parent = self.get_resource(name)
        require_authz(self.authz, principal, "update", name)
        rel = parent.relation(relation)
        if rel is None or rel.kind != "m2m":
            raise NotFoundError(f"unknown m2m relation {relation}")
        if not rel.through or not rel.through_local or not rel.through_remote:
            raise ValidationAdminError("m2m relation incomplete")
        through = self.get_resource(rel.through)
        require_authz(self.authz, principal, "update", rel.through)
        require_authz(self.authz, principal, "delete", rel.through)
        require_authz(self.authz, principal, "create", rel.through)
        parent_row = self.get(name, identity, principal=principal)
        local_pk = parent_row.get(parent.primary_key[0])
        # delete existing links via composite identity
        for obj in self._through_link_objs(through, rel.through_local, local_pk):
            key = {pk: getattr(obj, pk) for pk in through.primary_key}
            rid = encode_identity(through.model, key)
            try:
                self.delete(rel.through, rid, principal=principal)
            except Exception:
                self.session.delete(obj)
                self.session.commit()
        # insert new (dedupe preserve order)
        seen: set[str] = set()
        wanted: list[str] = []
        for i in ids:
            s = str(i).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            wanted.append(s)
        created = 0
        for remote_id in wanted:
            data = {
                rel.through_local: self._coerce_pk(local_pk),
                rel.through_remote: self._coerce_pk(remote_id),
            }
            self.create(rel.through, data, principal=principal)
            created += 1
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record(
                "m2m.set",
                name,
                principal_id=pid,
                relation=relation,
                ids=wanted,
                created=created,
            )
        return {"ok": True, "relation": relation, "ids": wanted, "count": created}

    def iter_records(
        self,
        name: str,
        *,
        search: str | None = None,
        filters: dict[str, str] | None = None,
        principal: Any | None = None,
        chunk_size: int = 500,
    ):
        """Iterate all records via keyset (for streaming export)."""
        res = self.get_resource(name)
        require_authz(self.authz, principal, "export", name)
        where = self._build_where(res, search=search, filters=filters)
        for obj in self.session.iter_query(res.model, where=where, chunk_size=chunk_size):
            yield self._serialize(res, obj, principal=principal)

    def export_stream(
        self,
        name: str,
        *,
        fmt: str = "csv",
        search: str | None = None,
        principal: Any | None = None,
        policy: ExportPolicy | None = None,
    ):
        """Return (media_type, iterator_or_bytes) for streaming formats."""
        res = self.get_resource(name)
        require_authz(self.authz, principal, "export", name)
        pol = policy or DEFAULT_EXPORT_POLICY
        rows = self.iter_records(
            name, search=search, principal=principal, chunk_size=pol.chunk_size
        )
        if fmt == "csv":
            return "text/csv", stream_csv(res, rows, policy=pol)
        if fmt == "jsonl":
            return "application/x-ndjson", stream_jsonl(res, rows, policy=pol)
        if fmt == "json":
            return "application/json", stream_json_array(res, rows, policy=pol)
        if fmt in {"xlsx", "excel"}:
            data = export_xlsx(res, rows, policy=pol)
            return (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                data,
            )
        raise ValidationAdminError("fmt must be csv, json, jsonl, or xlsx")

    def get(
        self,
        name: str,
        identity: str,
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "get", name)
        key = decode_identity(res.model, identity)
        obj = self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        return self._serialize(res, obj, principal=principal)

    def create(
        self,
        name: str,
        data: dict[str, Any],
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "create", name)
        if res.readonly:
            raise ValidationAdminError("resource is readonly")
        clean = assert_no_mass_assignment(res, data, partial=False)
        clean = self._filter_write(res, clean, principal=principal)
        # Autoincrement single int PK
        for pk in res.primary_key:
            col = res.column(pk)
            if col and col.autoincrement and (pk not in clean or clean.get(pk) in (None, "")):
                clean[pk] = self._next_pk(res, pk)
        try:
            obj = res.model.model_validate(clean)
        except Exception as exc:
            raise _validation_error(exc) from exc
        self.session.add(obj)
        self.session.commit()
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("create", name, principal_id=pid)
        return self._serialize(res, obj, principal=principal)

    def _next_pk(self, res: ResourceConfig, pk: str) -> int:
        rows = self.session.query(res.model, limit=50_000)
        if not rows:
            return 1
        return max(int(getattr(r, pk) or 0) for r in rows) + 1

    def update(
        self,
        name: str,
        identity: str,
        data: dict[str, Any],
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "update", name)
        if res.readonly:
            raise ValidationAdminError("resource is readonly")
        key = decode_identity(res.model, identity)
        obj = self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        clean = assert_no_mass_assignment(res, data, partial=True)
        clean = self._filter_write(res, clean, partial=True, principal=principal)
        try:
            # Validate partial merge against model for field-level 422s
            merged = {**self._serialize(res, obj, principal=principal), **clean}
            merged.pop("_identity", None)
            res.model.model_validate(merged)
        except Exception as exc:
            raise _validation_error(exc) from exc
        try:
            updated = self.session.update(obj, **clean)
        except Exception as exc:
            raise _validation_error(exc) from exc
        self.session.commit()
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("update", name, principal_id=pid, identity=identity)
        return self._serialize(res, updated, principal=principal)

    def delete(
        self,
        name: str,
        identity: str,
        *,
        principal: Any | None = None,
    ) -> None:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "delete", name)
        if res.readonly:
            raise ValidationAdminError("resource is readonly")
        key = decode_identity(res.model, identity)
        obj = self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        self.session.delete(obj)
        self.session.commit()
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("delete", name, principal_id=pid, identity=identity)

    def export(
        self,
        name: str,
        *,
        fmt: str = "json",
        principal: Any | None = None,
        search: str | None = None,
        filters: dict[str, str] | None = None,
        include: Sequence[str] | None = None,
    ) -> tuple[str, str]:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "export", name)
        listed = self.list(
            name,
            page=1,
            page_size=10_000,
            search=search,
            filters=filters,
            principal=principal,
        )
        items = listed.items
        if fmt == "json":
            if include:
                import json as _json

                # Keep exportable columns + nested relations (not stripped by rows_for_export)
                expanded = []
                for row in items:
                    base = {c: row.get(c) for c in res.exportable_columns()}
                    base["_identity"] = row.get("_identity")
                    attached = self._attach_relations(
                        res, {**row, **base}, include, principal=principal
                    )
                    if "_relations" in attached:
                        base["_relations"] = attached["_relations"]
                    base.pop("_identity", None)
                    expanded.append(base)
                body = _json.dumps(expanded, indent=2, default=str)
            else:
                body = export_json(res, items)
            media = "application/json"
        elif fmt == "csv":
            body = export_csv(res, items)
            media = "text/csv"
        else:
            raise ValidationAdminError("fmt must be json or csv")
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("export", name, principal_id=pid, fmt=fmt)
        return media, body

    def _attach_relations(
        self,
        res: ResourceConfig,
        row: dict[str, Any],
        include: Sequence[str],
        *,
        principal: Any | None,
        max_children: int = 100,
    ) -> dict[str, Any]:
        out = dict(row)
        rels: dict[str, Any] = {}
        identity = str(row.get("_identity") or "")
        for rel_name in include:
            rel = res.relation(rel_name)
            if rel is None or not identity:
                continue
            try:
                child = self.list_relation(
                    res.name,
                    identity,
                    rel_name,
                    page=1,
                    page_size=max_children,
                    principal=principal,
                )
                rels[rel_name] = child.items
            except Exception:
                rels[rel_name] = []
        if rels:
            out["_relations"] = rels
        return out

    def copy(
        self,
        name: str,
        *,
        fmt: str = "json",
        identities: Sequence[str] | None = None,
        principal: Any | None = None,
    ) -> str:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "copy", name)
        if identities:
            rows = [self.get(name, i, principal=principal) for i in identities]
        else:
            rows = self.list(name, page=1, page_size=100, principal=principal).items
        return copy_payload(res, rows, fmt=fmt)

    def _serialize(
        self,
        res: ResourceConfig,
        obj: Any,
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        data = obj.model_dump()
        for c in res.columns:
            if c.secret or c.hidden:
                data.pop(c.name, None)
                continue
            if not self.field_authz.allow_read(principal, res.name, c.name):
                data.pop(c.name, None)
        data["_identity"] = encode_identity(res.model, self._key_from_obj(res, obj))
        return data

    def _key_from_obj(self, res: ResourceConfig, obj: Any) -> Any:
        data = obj.model_dump()
        if len(res.primary_key) == 1:
            return data[res.primary_key[0]]
        return {c: data[c] for c in res.primary_key}

    def _filter_write(
        self,
        res: ResourceConfig,
        data: dict[str, Any],
        *,
        partial: bool = False,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        allowed = {c.name for c in res.columns if not c.secret and not c.readonly and not c.hidden}
        # allow setting non-readonly pk on create (unless autoincrement)
        if not partial:
            for pk in res.primary_key:
                col = res.column(pk)
                if col and not col.secret and not col.autoincrement:
                    allowed.add(pk)
        clean = {k: v for k, v in data.items() if k in allowed}
        if not partial:
            for pk in res.primary_key:
                if pk not in clean and pk in data:
                    col = res.column(pk)
                    if col and col.autoincrement:
                        continue
                    clean[pk] = data[pk]
        # Field-RBAC write gate
        denied = [
            k for k in list(clean) if not self.field_authz.allow_write(principal, res.name, k)
        ]
        for k in denied:
            clean.pop(k, None)
        return clean


def _validation_error(exc: BaseException) -> ValidationAdminError:
    """Map pydantic / generic validation failures to field-level 422 details."""
    fields: dict[str, str] = {}
    errors_fn = getattr(exc, "errors", None)
    if callable(errors_fn):
        try:
            for err in errors_fn():
                loc = err.get("loc") or ()
                key = ".".join(str(x) for x in loc) if loc else "_form"
                msg = str(err.get("msg") or "invalid")
                fields[key] = msg if key not in fields else f"{fields[key]}; {msg}"
        except Exception:
            fields = {}
    if fields:
        return ValidationAdminError("Validation failed", fields=fields)
    return ValidationAdminError(str(exc) or "Validation failed")
