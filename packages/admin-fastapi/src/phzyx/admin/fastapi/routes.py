"""FastAPI routes for AdminBoard headless API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from phzyx.admin.errors import AdminError
from phzyx.admin.opener import open_meta_for_key
from phzyx.admin.service import AdminService
from phzyx.admin.themes import PRIMARY_THEMES

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

if TYPE_CHECKING:
    from .board import AdminBoard


def create_admin_router(board: AdminBoard) -> APIRouter:
    router = APIRouter(tags=["adminboard"])

    def service() -> AdminService:
        from phzyx.admin.auth import AllowAllFields

        return AdminService(
            resources=board.resources,
            session=board.session_factory(),
            authz=board.authz,
            field_authz=getattr(board, "field_authz", None) or AllowAllFields(),
            audit=getattr(board, "audit", None),
        )

    def principal(request: Request, x_api_key: str | None = None) -> Any:
        """Prefer phzyx-auth middleware principal; fall back to X-API-Key stub."""
        p = getattr(request.state, "principal", None)
        if p is not None:
            return p
        if x_api_key:
            svc = getattr(request.app.state, "phzyx_auth", None)
            if svc is not None:
                resolved = svc.principal_from_api_key(x_api_key)
                if resolved is not None:
                    return resolved
            return type(
                "P",
                (),
                {
                    "id": str(x_api_key),
                    "is_staff": True,
                    "is_superuser": True,
                    "permissions": frozenset(),
                },
            )()
        return None

    @router.get("/meta")
    def meta() -> dict[str, Any]:
        settings = board.settings_store.get()
        return {
            "theme": board.theme,
            "themes": list(PRIMARY_THEMES) + ["system-ambient"],
            "prefix": board.prefix,
            "version": "0.1.0",
            "branding": settings.branding.to_dict(),
            "features": {
                "filter_ops": True,
                "schema_status": True,
                "export_include": True,
                "field_authz": True,
                "audit": True,
                "trust": True,
                "branding": True,
            },
        }

    @router.get("/audit")
    def audit_list(
        request: Request,
        limit: int = 100,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """Diamond D7 — admin write/export audit events (newest last)."""
        from phzyx.admin.auth import require_authz

        p = principal(request, x_api_key)
        try:
            require_authz(board.authz, p, "list", "audit")
        except Exception:
            # superuser/staff gate: if authz denies, also try staff flag
            if p is None or not (
                bool(getattr(p, "is_superuser", False)) or bool(getattr(p, "is_staff", False))
            ):
                return JSONResponse(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Not allowed to list audit events",
                            "details": {"action": "list", "resource": "audit"},
                        }
                    },
                    status_code=403,
                )
        limit = max(1, min(int(limit or 100), 500))
        audit = getattr(board, "audit", None)
        events: list[dict[str, Any]] = []
        if audit is not None:
            events.extend([e.to_dict() for e in audit.list(limit=limit)])
        # merge auth audit if present
        auth_svc = getattr(request.app.state, "phzyx_auth", None)
        if auth_svc is not None and getattr(auth_svc, "audit", None) is not None:
            for ev in list(auth_svc.audit.events)[-limit:]:
                events.append(
                    {
                        "action": ev.get("event_type", "auth"),
                        "resource": "auth",
                        "principal_id": ev.get("actor_id"),
                        "at": ev.get("created_at"),
                        "details": ev.get("meta") or {},
                        "source": "auth",
                    }
                )
        events.sort(key=lambda e: str(e.get("at") or ""))
        return {"items": events[-limit:], "total": len(events[-limit:])}

    @router.get("/schema/status")
    def schema_status(request: Request, x_api_key: str | None = Header(default=None)) -> Any:
        """Diamond D8 — read-only dialect + migration + plan summary."""
        _ = principal(request, x_api_key)
        svc = getattr(board, "schema_status", None)
        if svc is None:
            return {
                "ok": False,
                "error": "schema status not configured",
                "migrations": {"applied": [], "pending": []},
            }
        return svc.snapshot()

    @router.get("/resources")
    def resources(
        request: Request, x_api_key: str | None = Header(default=None)
    ) -> list[dict[str, Any]]:
        p = principal(request, x_api_key)
        return service().list_resources(principal=p)

    @router.get("/resources/{name}")
    def resource_schema(
        request: Request, name: str, x_api_key: str | None = Header(default=None)
    ) -> dict[str, Any]:
        p = principal(request, x_api_key)
        return service().public_schema(name, principal=p)

    def _parse_filters(request: Request) -> dict[str, str]:
        """Parse ``filter.<field>=value`` or ``filter.<field>__op=value`` (D2.5)."""
        out: dict[str, str] = {}
        for key, val in request.query_params.multi_items():
            if key.startswith("filter.") and val != "":
                out[key.removeprefix("filter.")] = val
        return out

    @router.get("/resources/{name}/records")
    def list_records(
        name: str,
        request: Request,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        cursor: str | None = None,
        pagination: str = "offset",
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        try:
            filters = _parse_filters(request)
            mode = pagination if pagination in {"offset", "keyset"} else "offset"
            result = service().list(
                name,
                page=page,
                page_size=page_size,
                search=search,
                cursor=cursor,
                filters=filters or None,
                pagination=mode,
                principal=principal(request, x_api_key),
            )
            return {
                "items": result.items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "next_cursor": result.next_cursor,
                "prev_cursor": result.prev_cursor,
                "has_more": result.has_more,
                "pagination": result.pagination,
                "filters": filters,
            }
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)  # type: ignore[return-value]

    @router.get("/resources/{name}/actions")
    def list_actions(
        request: Request,
        name: str,
        scope: str | None = None,
        x_api_key: str | None = Header(default=None),
    ) -> list[dict[str, Any]]:
        """Action catalog (row/bulk/global). Diamond D5.

        ``scope`` filters: row | bulk | global. Omit for full catalog.
        """
        _ = principal(request, x_api_key)
        try:
            sc = scope if scope in {"row", "bulk", "global"} else None
            return service().list_actions(name, scope=sc)
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)  # type: ignore[return-value]

    @router.get("/resources/{name}/autocomplete")
    def autocomplete(
        request: Request,
        name: str,
        q: str = "",
        limit: int = 20,
        x_api_key: str | None = Header(default=None),
    ) -> list[dict[str, Any]]:
        """FK typeahead options (Diamond D4)."""
        try:
            return service().autocomplete(
                name, q=q, limit=limit, principal=principal(request, x_api_key)
            )
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)  # type: ignore[return-value]

    @router.post("/resources/{name}/actions/run")
    def run_action(
        request: Request,
        name: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """Run a server-side row/bulk action (Diamond D5)."""
        try:
            action = str(body.get("action") or "")
            identities = body.get("identities") or []
            if identities is not None and not isinstance(identities, list):
                raise AdminError("validation_error", "identities must be a list", status=422)
            return service().run_action(
                name,
                action,
                [str(i) for i in identities] if identities else None,
                principal=principal(request, x_api_key),
            )
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.post("/resources/{name}/bulk")
    def bulk_action(
        request: Request,
        name: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        try:
            action = str(body.get("action") or "")
            identities = body.get("identities") or []
            if not isinstance(identities, list):
                raise AdminError("validation_error", "identities must be a list", status=422)
            return service().bulk_action(
                name,
                action,
                [str(i) for i in identities],
                principal=principal(request, x_api_key),
            )
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/resources/{name}/records/{identity}/relations/{relation}")
    def list_relation(
        request: Request,
        name: str,
        identity: str,
        relation: str,
        page: int = 1,
        page_size: int = 50,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """Has-many or M2M related rows (Diamond D4 / D4.5)."""
        try:
            result = service().list_relation(
                name,
                identity,
                relation,
                page=page,
                page_size=page_size,
                principal=principal(request, x_api_key),
            )
            parent = service().get_resource(name)
            rel = parent.relation(relation)
            return {
                "items": result.items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "relation": relation,
                "kind": rel.kind if rel else "has_many",
            }
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/resources/{name}/records/{identity}/m2m/{relation}")
    def get_m2m(
        request: Request,
        name: str,
        identity: str,
        relation: str,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """M2M selected IDs for multi-select form (Diamond D4.5)."""
        try:
            ids = service().get_m2m_ids(
                name, identity, relation, principal=principal(request, x_api_key)
            )
            return {"relation": relation, "ids": ids}
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.put("/resources/{name}/records/{identity}/m2m/{relation}")
    def put_m2m(
        request: Request,
        name: str,
        identity: str,
        relation: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """Replace M2M memberships (Diamond D4.5 save round-trip)."""
        try:
            ids = body.get("ids") or body.get("values") or []
            if not isinstance(ids, list):
                raise AdminError("validation_error", "ids must be a list", status=422)
            return service().set_m2m(
                name,
                identity,
                relation,
                ids,
                principal=principal(request, x_api_key),
            )
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/resources/{name}/records/{identity}")
    def get_record(
        request: Request, name: str, identity: str, x_api_key: str | None = Header(default=None)
    ) -> Any:
        try:
            return service().get(name, identity, principal=principal(request, x_api_key))
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.post("/resources/{name}/records")
    def create_record(
        request: Request,
        name: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        try:
            return service().create(name, body, principal=principal(request, x_api_key))
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.patch("/resources/{name}/records/{identity}")
    def update_record(
        request: Request,
        name: str,
        identity: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        try:
            return service().update(name, identity, body, principal=principal(request, x_api_key))
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.delete("/resources/{name}/records/{identity}")
    def delete_record(
        request: Request, name: str, identity: str, x_api_key: str | None = Header(default=None)
    ) -> Any:
        try:
            service().delete(name, identity, principal=principal(request, x_api_key))
            return Response(status_code=204)
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/resources/{name}/export")
    def export_records(
        request: Request,
        name: str,
        fmt: str = "json",
        search: str | None = None,
        stream: bool = False,
        include: str | None = None,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        try:
            p = principal(request, x_api_key)
            filters = _parse_filters(request) or None
            include_list = [x.strip() for x in (include or "").split(",") if x.strip()]
            if stream or fmt in {"jsonl", "xlsx", "excel"}:
                media, body = service().export_stream(name, fmt=fmt, search=search, principal=p)
                if isinstance(body, (bytes, bytearray)):
                    return Response(content=bytes(body), media_type=media)
                return Response(content="".join(body), media_type=media)
            media, body = service().export(
                name,
                fmt=fmt,
                search=search,
                filters=filters,
                include=include_list or None,
                principal=p,
            )
            if fmt == "csv":
                return PlainTextResponse(body, media_type=media)
            return Response(content=body, media_type=media)
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.post("/resources/{name}/copy")
    def copy_records(
        request: Request,
        name: str,
        body: dict[str, Any] | None = None,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        body = body or {}
        try:
            text = service().copy(
                name,
                fmt=body.get("fmt", "json"),
                identities=body.get("identities"),
                principal=principal(request, x_api_key),
            )
            return {"payload": text}
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/files/open-meta")
    def file_open_meta(
        request: Request, key: str, x_api_key: str | None = Header(default=None)
    ) -> Any:
        _ = principal(request, x_api_key)
        meta = open_meta_for_key(key)
        return {
            "key": meta.key,
            "content_type": meta.content_type,
            "mode": meta.mode,
            "label": meta.label,
        }

    @router.get("/files/download")
    def file_download(
        request: Request, key: str, x_api_key: str | None = Header(default=None)
    ) -> Any:
        from phzyx.admin.auth import require_authz

        try:
            require_authz(board.authz, principal(request, x_api_key), "download", "files")
            data = board.storage.open(key)
            meta = open_meta_for_key(key)
            return Response(content=data, media_type=meta.content_type)
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)
        except Exception as exc:
            return JSONResponse(
                {"error": {"code": "file_error", "message": str(exc), "details": {}}},
                status_code=404,
            )

    @router.post("/files/upload")
    async def file_upload(request: Request, x_api_key: str | None = Header(default=None)) -> Any:
        from phzyx.admin.auth import require_authz

        try:
            require_authz(board.authz, principal(request, x_api_key), "upload", "files")
            form = await request.form()
            key = str(form.get("key") or "")
            upload = form.get("file")
            if not key or upload is None:
                raise AdminError("validation_error", "key and file required", status=422)
            data = await upload.read()  # type: ignore[union-attr]
            ctype = getattr(upload, "content_type", None)
            close = getattr(upload, "close", None)
            if callable(close):
                close()
            item = board.media.add(key, data, content_type=ctype)
            meta = open_meta_for_key(item.key, content_type=item.content_type)
            return {
                "key": item.key,
                "size": item.size,
                "open": {
                    "key": meta.key,
                    "content_type": meta.content_type,
                    "mode": meta.mode,
                    "label": meta.label,
                },
                "item": board.media.to_public(item),
            }
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.get("/files/library")
    def file_library(
        request: Request,
        folder: str = "",
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        """D6 media library listing (storage scan + index)."""
        from phzyx.admin.auth import require_authz

        try:
            require_authz(board.authz, principal(request, x_api_key), "list", "files")
            items = board.media.refresh_from_storage(folder)
            return {
                "folder": folder,
                "items": [board.media.to_public(i) for i in items],
                "total": len(items),
            }
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)

    @router.delete("/files")
    def file_delete(
        request: Request,
        key: str,
        x_api_key: str | None = Header(default=None),
    ) -> Any:
        from phzyx.admin.auth import require_authz

        try:
            require_authz(board.authz, principal(request, x_api_key), "delete", "files")
            board.media.delete(key)
            return Response(status_code=204)
        except AdminError as exc:
            return JSONResponse(exc.to_dict(), status_code=exc.status)
        except Exception as exc:
            return JSONResponse(
                {"error": {"code": "file_error", "message": str(exc), "details": {}}},
                status_code=404,
            )

    @router.get("/settings")
    def get_settings() -> dict[str, Any]:
        return board.settings_store.get().to_dict()

    @router.put("/settings")
    def put_settings(
        request: Request,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from phzyx.admin.settings import AdminSettings

        p = principal(request, x_api_key)
        # Branding changes require superuser (open demos may have no principal).
        if "branding" in body and p is not None and not bool(getattr(p, "is_superuser", False)):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "forbidden",
                        "message": "Only superusers may change branding",
                        "details": {},
                    }
                },
            )
        return board.settings_store.put(AdminSettings.from_dict(body)).to_dict()

    @router.get("/layouts/{resource}")
    def get_layout(
        request: Request, resource: str, x_api_key: str | None = Header(default=None)
    ) -> dict[str, Any]:
        p = principal(request, x_api_key)
        pid = str(getattr(p, "id", "anonymous") if p is not None else "anonymous")
        prefs = board.layout_store.get(resource, pid)
        if prefs is None:
            return {"resource": resource, "principal_id": pid, "columns": [], "hidden": []}
        return prefs.to_dict()

    @router.put("/layouts/{resource}")
    def put_layout(
        request: Request,
        resource: str,
        body: dict[str, Any],
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from phzyx.admin.layouts import LayoutPrefs

        p = principal(request, x_api_key)
        pid = str(getattr(p, "id", "anonymous") if p is not None else "anonymous")
        prefs = LayoutPrefs.from_dict({**body, "resource": resource, "principal_id": pid})
        return board.layout_store.put(prefs).to_dict()

    return router
