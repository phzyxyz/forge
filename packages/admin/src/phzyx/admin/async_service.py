"""Async AdminService — battle-ready CRUD over AsyncSession."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from phzyx.admin.audit import AuditLog
from phzyx.admin.auth import AllowAll, AllowAllFields, Authz, FieldAuthz, require_authz
from phzyx.admin.errors import ConflictError, NotFoundError, ValidationAdminError
from phzyx.admin.filters import build_where
from phzyx.admin.identity import decode_identity, encode_identity
from phzyx.admin.resource import ResourceConfig
from phzyx.admin.security import assert_no_mass_assignment
from phzyx.admin.service import ListResult, _validation_error
from phzyx.admin.unique_checks import raise_if_unique_violations_async
from phzyx.orm.errors import ConflictError as OrmConflict
from phzyx.orm.insert_prep import utcnow
from phzyx.orm.keyset import default_order_columns, order_from_columns
from phzyx.orm.session_async import AsyncSession
from phzyx.schema.model import get_table_info


def _identity_key(model: type[Any], obj: Any) -> Any:
    pk = get_table_info(model).primary_key
    if len(pk) == 1:
        return getattr(obj, pk[0])
    return {c: getattr(obj, c) for c in pk}


def _serialize(model: type[Any], obj: Any) -> dict[str, Any]:
    data = obj.model_dump(mode="json")
    data["_identity"] = encode_identity(model, _identity_key(model, obj))
    return data


@dataclass
class AsyncAdminService:
    """Headless admin ops over AsyncSession (list/get/create/update/delete)."""

    resources: dict[str, ResourceConfig]
    session: AsyncSession
    authz: Authz = field(default_factory=AllowAll)
    field_authz: FieldAuthz = field(default_factory=AllowAllFields)
    audit: AuditLog | None = None
    storage: Any | None = None

    def get_resource(self, name: str) -> ResourceConfig:
        if name not in self.resources:
            raise NotFoundError(f"unknown resource {name}")
        return self.resources[name]

    def _where(
        self,
        res: ResourceConfig,
        *,
        search: str | None,
        filters: dict[str, str] | None,
    ) -> list[Any]:
        """Same filter rules as sync AdminService (shared ``build_where``)."""
        return build_where(res, search=search, filters=filters, hide_soft_deleted=True)

    async def list(
        self,
        name: str,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        filters: dict[str, str] | None = None,
        principal: Any | None = None,
    ) -> ListResult:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "list", name)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        where = self._where(res, search=search, filters=filters)
        order = order_from_columns(default_order_columns(res.model))
        rows = await self.session.query(
            res.model,
            where=where,
            order_by=order,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        # Efficient total when sync count exists; async: bounded query length
        all_rows = await self.session.query(res.model, where=where)
        items = [_serialize(res.model, r) for r in rows]
        return ListResult(
            items=items,
            total=len(all_rows),
            page=page,
            page_size=page_size,
        )

    async def get(
        self,
        name: str,
        identity: str,
        *,
        principal: Any | None = None,
    ) -> dict[str, Any]:
        res = self.get_resource(name)
        require_authz(self.authz, principal, "get", name)
        key = decode_identity(res.model, identity)
        obj = await self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        return _serialize(res.model, obj)

    async def create(
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
        ai_pks: set[str] = set()
        for pk in res.primary_key:
            col = res.column(pk)
            if col and col.autoincrement and (pk not in clean or clean.get(pk) in (None, "")):
                clean.pop(pk, None)
                ai_pks.add(pk)
        # Drop generated fields from client payload
        for c in res.columns:
            meta = get_table_info(res.model).columns.get(c.name)
            if meta and meta.generated:
                clean.pop(c.name, None)
        try:
            obj = res.model.model_validate(clean)
        except Exception as exc:
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
        await raise_if_unique_violations_async(
            res.model,
            clean,
            query=lambda where: self.session.query(res.model, where=where, limit=5),
        )
        try:
            obj = await self.session.add(obj)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
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
        return _serialize(res.model, obj)

    async def update(
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
        obj = await self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        clean = assert_no_mass_assignment(res, data, partial=True)
        for c in res.columns:
            meta = get_table_info(res.model).columns.get(c.name)
            if meta and meta.generated:
                clean.pop(c.name, None)
        merged = {**_serialize(res.model, obj), **clean}
        merged.pop("_identity", None)
        await raise_if_unique_violations_async(
            res.model,
            merged,
            query=lambda where: self.session.query(res.model, where=where, limit=5),
            exclude_key=key,
        )
        try:
            updated = await self.session.update(obj, **clean)
            await self.session.commit()
        except OrmConflict as exc:
            await self.session.rollback()
            raise ConflictError(str(exc), resource=name, identity=identity) from exc
        except Exception as exc:
            await self.session.rollback()
            raise _validation_error(exc) from exc
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("update", name, principal_id=pid, identity=identity)
        return _serialize(res.model, updated)

    async def delete(
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
        obj = await self.session.get(res.model, key)
        if obj is None:
            raise NotFoundError(f"{name} {identity} not found")
        use_soft = soft if soft is not None else ("deleted_at" in res.model.model_fields)
        if use_soft and "deleted_at" in res.model.model_fields:
            await self.session.update(obj, deleted_at=utcnow().isoformat())
        else:
            await self.session.delete(obj)
        await self.session.commit()
        if self.audit:
            pid = getattr(principal, "id", None) if principal else None
            self.audit.record("delete", name, principal_id=pid, identity=identity)
