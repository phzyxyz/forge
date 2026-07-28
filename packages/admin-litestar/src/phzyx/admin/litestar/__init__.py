"""Phzyx AdminBoard — Litestar adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from phzyx.admin.auth import AllowAll, Authz
from phzyx.admin.errors import AdminError
from phzyx.admin.resource import ResourceConfig, infer_resource
from phzyx.admin.service import AdminService
from phzyx.admin.themes import DEFAULT_THEME, PRIMARY_THEMES, normalize_theme
from phzyx.orm.session_sync import Session
from phzyx.schema.model import Model

__version__ = "0.1.1"


class AdminBoardConfig:
    """Config object passed to Litestar router factory."""

    def __init__(
        self,
        *,
        models: list[type[Model]] | None = None,
        resources: list[ResourceConfig] | None = None,
        session_factory: Callable[[], Session],
        authz: Authz | None = None,
        theme: str = DEFAULT_THEME,
        prefix: str = "/admin",
    ) -> None:
        self.theme = normalize_theme(theme)
        self.prefix = prefix.rstrip("/") or "/admin"
        self.authz = authz or AllowAll()
        self.session_factory = session_factory
        res_list = list(resources or [])
        for m in models or []:
            res_list.append(infer_resource(m))
        if not res_list:
            raise ValueError("models or resources required")
        self.resources = {r.name: r for r in res_list}

    def service(self) -> AdminService:
        return AdminService(
            resources=self.resources,
            session=self.session_factory(),
            authz=self.authz,
        )


def create_admin_router(config: AdminBoardConfig) -> Any:
    """Return a Litestar Router for AdminBoard API (no SPA mount)."""
    try:
        from litestar import Router, delete, get, patch, post
        from litestar.response import Response
    except ImportError as exc:  # pragma: no cover
        raise ImportError("uv add phzyx-admin-litestar / litestar") from exc

    def svc() -> AdminService:
        return config.service()

    @get("/meta")
    async def meta() -> dict[str, Any]:
        return {
            "theme": config.theme,
            "themes": list(PRIMARY_THEMES) + ["system-ambient"],
            "framework": "litestar",
        }

    @get("/resources")
    async def resources() -> list[dict[str, Any]]:
        return svc().list_resources()

    @get("/resources/{name:str}/records")
    async def list_records(name: str, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        try:
            result = svc().list(name, page=page, page_size=page_size)
            return {
                "items": result.items,
                "total": result.total,
                "next_cursor": result.next_cursor,
                "has_more": result.has_more,
            }
        except AdminError as exc:
            return Response(exc.to_dict(), status_code=exc.status)  # type: ignore[return-value]

    @post("/resources/{name:str}/records")
    async def create_record(name: str, data: dict[str, Any]) -> Any:
        try:
            return svc().create(name, data)
        except AdminError as exc:
            return Response(exc.to_dict(), status_code=exc.status)

    @get("/resources/{name:str}/records/{identity:str}")
    async def get_record(name: str, identity: str) -> Any:
        try:
            return svc().get(name, identity)
        except AdminError as exc:
            return Response(exc.to_dict(), status_code=exc.status)

    @patch("/resources/{name:str}/records/{identity:str}")
    async def update_record(name: str, identity: str, data: dict[str, Any]) -> Any:
        try:
            return svc().update(name, identity, data)
        except AdminError as exc:
            return Response(exc.to_dict(), status_code=exc.status)

    @delete("/resources/{name:str}/records/{identity:str}", status_code=204)
    async def delete_record(name: str, identity: str) -> None:
        svc().delete(name, identity)

    return Router(
        path=f"{config.prefix}/api/v1",
        route_handlers=[
            meta,
            resources,
            list_records,
            create_record,
            get_record,
            update_record,
            delete_record,
        ],
        tags=["adminboard"],
    )


__all__ = ["AdminBoardConfig", "create_admin_router", "__version__"]
