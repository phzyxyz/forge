"""AdminService — headless CRUD, export, copy (session-backed)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from phzyx.admin.actions import (
    list_admin_actions,
    list_bulk_actions,
    run_admin_action,
    run_bulk_action,
)
from phzyx.admin.audit import AuditLog
from phzyx.admin.auth import AllowAll, AllowAllFields, Authz, FieldAuthz, require_authz
from phzyx.admin.errors import ConflictError, NotFoundError, ValidationAdminError
from phzyx.admin.export_copy import copy_payload, export_csv, export_json
from phzyx.admin.filters import FILTER_OPS, build_where
from phzyx.admin.i18n import I18n
from phzyx.admin.identity import decode_identity, encode_identity
from phzyx.admin.relation_manager import relation_managers_for
from phzyx.admin.resource import ResourceConfig
from phzyx.admin.search import global_search
from phzyx.admin.security import assert_no_mass_assignment
from phzyx.admin.stream_export import (
    DEFAULT_EXPORT_POLICY,
    ExportPolicy,
    export_xlsx,
    stream_csv,
    stream_json_array,
    stream_jsonl,
)
from phzyx.admin.unique_checks import raise_if_unique_violations
from phzyx.admin.widgets import resource_count_widgets, widgets_to_dict
from phzyx.orm.errors import ConflictError as OrmConflict
from phzyx.orm.expr import eq
from phzyx.orm.files import sanitize_upload_key
from phzyx.orm.keyset import default_order_columns, order_from_columns
from phzyx.orm.session_sync import Session
from phzyx.orm.soft_delete import soft_delete
from phzyx.schema.model import get_table_info


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
    storage: Any | None = None

    def list_resources(self, *, principal: Any | None = None) -> list[dict[str, Any]]:
        return [self.public_schema(r.name, principal=principal) for r in self.resources.values()]

    def global_search(
        self,
        query: str,
        *,
        limit_per_resource: int = 5,
        principal: Any | None = None,
    ) -> list[dict[str, Any]]:
        """⌘K-style search across searchable columns of all resources."""
        # Authz: only searchable resources the principal may list
        allowed = {
            n: r for n, r in self.resources.items() if self.authz.authorize(principal, "list", n)
        }
        hits = global_search(
            self.session,
            allowed,
            query,
            limit_per_resource=limit_per_resource,
            dialect_ilike=self.session.dialect.value != "sqlite",
        )
        return [
            {
                "resource": h.resource,
                "identity": h.identity,
                "label": h.label,
                "score": h.score,
            }
            for h in hits
        ]

    def dashboard_widgets(
        self,
        *,
        principal: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Simple count widgets for the admin home dashboard."""
        allowed = {
            n: r for n, r in self.resources.items() if self.authz.authorize(principal, "list", n)
        }
        return widgets_to_dict(resource_count_widgets(self.session, allowed))

    def i18n_catalog(self, locale: str = "en") -> dict[str, str]:
        return I18n(locale=locale).catalog()

    def relation_managers(self, name: str) -> list[dict[str, Any]]:
        res = self.get_resource(name)
        return [
            {
                "name": m.name,
                "parent": m.parent_resource,
                "relation": m.relation.name,
                "child": m.child_resource,
                "kind": m.relation.kind,
            }
            for m in relation_managers_for(res)
        ]

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
        schema["filter_ops"] = sorted(FILTER_OPS)
        return schema

    def _build_where(
        self,
        res: ResourceConfig,
        *,
        search: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[Any]:
        """Build list WHERE clause (includes soft-delete hide by default)."""
        return build_where(res, search=search, filters=filters, hide_soft_deleted=True)

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
        return run_admin_action(self, name, action, identities, principal=principal)

    def list_bulk_actions(self, name: str) -> list[dict[str, Any]]:
        res = self.get_resource(name)
        has_active = any(c.name == "active" for c in res.columns)
        return list_bulk_actions(name, has_active)

    def list_actions(self, name: str, *, scope: str | None = None) -> list[dict[str, Any]]:
        """List action catalog for SPA menus (Diamond D5)."""
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
        table_info = get_table_info(res.model)
        for col_name, meta in table_info.columns.items():
            if meta.generated:
                clean.pop(col_name, None)
        # Autoincrement PK: omit so ORM/DB generates (never app max+1).
        ai_pks: set[str] = set()
        for pk in res.primary_key:
            col = res.column(pk)
            if col and col.autoincrement and (pk not in clean or clean.get(pk) in (None, "")):
                clean.pop(pk, None)
                ai_pks.add(pk)
        try:
            obj = res.model.model_validate(clean)
        except Exception as exc:
            # Allow missing AI PK on required-int models; still require other fields.
            missing = [
                fname
                for fname, finfo in res.model.model_fields.items()
                if fname not in ai_pks and finfo.is_required() and fname not in clean
            ]
            if missing or not ai_pks:
                raise _validation_error(exc) from exc
            try:
                obj = res.model.model_construct(**clean)
            except Exception as exc2:
                raise _validation_error(exc2) from exc2
        raise_if_unique_violations(
            res.model,
            clean,
            query=lambda where: self.session.query(res.model, where=where, limit=5),
        )
        try:
            obj = self.session.add(obj)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            # Race / dialect IntegrityError → same field-level shape when possible.
            msg = str(exc).lower()
            if "unique" in msg or "duplicate" in msg or "integrity" in msg:
                raise ValidationAdminError(
                    "Validation failed",
                    fields={"_": "unique constraint violated"},
                ) from exc
            raise
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("create", name, principal_id=pid)
        return self._serialize(res, obj, principal=principal)

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
        exclude = key
        raise_if_unique_violations(
            res.model,
            {**merged, **clean},
            query=lambda where: self.session.query(res.model, where=where, limit=5),
            exclude_key=exclude,
        )
        try:
            updated = self.session.update(obj, **clean)
            self.session.commit()
        except OrmConflict as exc:
            self.session.rollback()
            raise ConflictError(str(exc), resource=name, identity=identity) from exc
        except Exception as exc:
            self.session.rollback()
            msg = str(exc).lower()
            if "unique" in msg or "duplicate" in msg or "integrity" in msg:
                raise ValidationAdminError(
                    "Validation failed",
                    fields={"_": "unique constraint violated"},
                ) from exc
            raise _validation_error(exc) from exc
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
        soft: bool | None = None,
    ) -> None:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "delete", name)
        if res.readonly:
            raise ValidationAdminError("resource is readonly")
        key = decode_identity(res.model, identity)
        obj = self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        use_soft = soft if soft is not None else ("deleted_at" in res.model.model_fields)
        if use_soft and "deleted_at" in res.model.model_fields:
            soft_delete(self.session, obj, column="deleted_at")
        else:
            self.session.delete(obj)
        self.session.commit()
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("delete", name, principal_id=pid, identity=identity)

    def presign_upload(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """Return a presigned PUT target for direct-to-storage uploads."""
        store = getattr(self, "storage", None)
        if store is None:
            raise ValidationAdminError("no storage backend configured")
        safe = sanitize_upload_key(key)
        if hasattr(store, "presign_put"):
            url = store.presign_put(safe, expires_in=expires_in, content_type=content_type)
            return {"method": "PUT", "url": url, "key": safe, "expires_in": expires_in}
        if hasattr(store, "presign"):
            # S3-style get_object method name override for put
            try:
                url = store.presign(safe, expires_in=expires_in, method="put_object")
            except TypeError:
                url = store.presign(safe, expires_in=expires_in)
            return {"method": "PUT", "url": url, "key": safe, "expires_in": expires_in}
        # Local/memory: client must POST bytes to admin media upload endpoint
        return {
            "method": "POST",
            "url": f"/admin/api/v1/media/upload?key={safe}",
            "key": safe,
            "expires_in": expires_in,
            "note": "local storage — use admin media upload API",
        }

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
                body = json.dumps(expanded, indent=2, default=str)
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
            raw_errors = errors_fn()
            items = raw_errors if isinstance(raw_errors, list) else []
            for err in items:
                if not isinstance(err, dict):
                    continue
                loc = err.get("loc") or ()
                key = ".".join(str(x) for x in loc) if loc else "_form"
                msg = str(err.get("msg") or "invalid")
                fields[key] = msg if key not in fields else f"{fields[key]}; {msg}"
        except Exception:
            fields = {}
    if fields:
        return ValidationAdminError("Validation failed", fields=fields)
    return ValidationAdminError(str(exc) or "Validation failed")
