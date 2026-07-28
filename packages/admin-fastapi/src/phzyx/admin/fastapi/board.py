"""AdminBoard FastAPI one-liner mount."""

from __future__ import annotations

import os
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from phzyx.admin.audit import AuditLog
from phzyx.admin.auth import AllowAll, AllowAllFields, Authz, FieldAuthz
from phzyx.admin.branding import BrandingConfig
from phzyx.admin.layouts import LayoutStore
from phzyx.admin.media import MediaLibrary
from phzyx.admin.resource import ResourceConfig, infer_resource, wire_relations
from phzyx.admin.schema_status import SchemaStatusService
from phzyx.admin.security import csp_headers
from phzyx.admin.settings import AdminSettings, SettingsStore
from phzyx.admin.storage import LocalStorage, MemoryStorage, StorageBackend
from phzyx.admin.themes import DEFAULT_THEME, normalize_theme
from phzyx.orm.session_sync import Session
from phzyx.schema.model import Model

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import create_admin_router


class AdminBoard:
    """Mount AdminBoard API + SPA on a FastAPI app.

    Example::

        AdminBoard(app, models=[User, Order], session_factory=get_session, theme="stellar-dark")
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        models: Sequence[type[Model]] | None = None,
        resources: Sequence[ResourceConfig] | None = None,
        session_factory: Callable[[], Session],
        authz: Authz | None = None,
        field_authz: FieldAuthz | None = None,
        audit: AuditLog | None = None,
        theme: str = DEFAULT_THEME,
        prefix: str = "/admin",
        storage: StorageBackend | None = None,
        storage_root: str | Path | None = None,
        enable_csp: bool = True,
        database_url: str | None = None,
        branding: BrandingConfig | dict[str, Any] | None = None,
        openapi_path_prefix: str | None = None,
        openapi_exclude_prefix: str | None = None,
        mount_apiboard: bool = True,
        apiboard_path: str = "/apiboard",
        apidocs_redirect: bool = False,
    ) -> None:
        self.theme = normalize_theme(theme)
        self.prefix = prefix.rstrip("/") or "/admin"
        self.authz = authz or AllowAll()
        self.field_authz = field_authz or AllowAllFields()
        self.audit = audit if audit is not None else AuditLog()
        self.session_factory = session_factory
        self.openapi_path_prefix = openapi_path_prefix
        self.openapi_exclude_prefix = openapi_exclude_prefix
        self.mount_apiboard = mount_apiboard
        self.apiboard_path = (apiboard_path or "/apiboard").rstrip("/") or "/apiboard"
        self.apidocs_redirect = apidocs_redirect
        if isinstance(branding, BrandingConfig):
            brand = branding
        elif isinstance(branding, dict):
            brand = BrandingConfig.from_dict(branding)
        else:
            brand = BrandingConfig()
        self.settings_store = SettingsStore(AdminSettings(default_theme=self.theme, branding=brand))
        self.layout_store = LayoutStore()
        self.storage: StorageBackend = storage or (
            LocalStorage(storage_root or Path.cwd() / ".phzyx-media")
            if storage_root is not None
            else MemoryStorage()
        )
        self.media = MediaLibrary(storage=self.storage)
        self.database_url = database_url

        res_list: list[ResourceConfig] = list(resources or [])
        model_list: list[type[Model]] = list(models or [])
        if models:
            for m in models:
                res_list.append(infer_resource(m))
        if not res_list:
            raise ValueError("AdminBoard requires models= or resources=")
        # Diamond D4: FK labels + reverse has_many panels
        self.resources = wire_relations({r.name: r for r in res_list})
        self.schema_status = SchemaStatusService(
            models=model_list,
            database_url=database_url,
        )

        if isinstance(self.authz, AllowAll) and _is_prod():
            # Security baseline: warn if no auth in production-like env
            warnings.warn(
                "AdminBoard using AllowAll authz in production-like environment",
                UserWarning,
                stacklevel=2,
            )

        router = create_admin_router(self)
        app.include_router(router, prefix=f"{self.prefix}/api/v1")

        if enable_csp:

            @app.middleware("http")
            async def _phzyx_security_headers(request: Any, call_next: Any) -> Any:
                response = await call_next(request)
                path = request.url.path
                if path.startswith(self.prefix) or path.startswith(self.apiboard_path):
                    for k, v in csp_headers().items():
                        response.headers.setdefault(k, v)
                return response

        static_dir = _spa_static_dir()
        if static_dir is not None and static_dir.is_dir():
            # API Board — separate product URL (same SPA bundle, different boot mode)
            if mount_apiboard:
                from fastapi.responses import RedirectResponse

                apiboard = self.apiboard_path

                @app.get(apiboard, include_in_schema=False)
                def _apiboard_slash() -> Any:
                    return RedirectResponse(url=f"{apiboard}/", status_code=307)

                app.mount(
                    f"{apiboard}/",
                    StaticFiles(directory=str(static_dir), html=True),
                    name="phzyx-apiboard",
                )

            # Optional legacy short link
            if apidocs_redirect:

                @app.get("/apidocs", include_in_schema=False)
                def _apidocs_to_apiboard() -> Any:
                    from fastapi.responses import RedirectResponse

                    return RedirectResponse(url=f"{self.apiboard_path}/", status_code=307)

            app.mount(
                self.prefix,
                StaticFiles(directory=str(static_dir), html=True),
                name="phzyx-admin-spa",
            )


def _spa_static_dir() -> Path | None:
    """Locate AdminBoard SPA assets (fat wheel, vendored static, or monorepo).

    Layouts (``board.py`` at ``…/phzyx/admin/fastapi/board.py``):
    - Fat ``phzyx-forge`` wheel: ``phzyx/admin/web/dist``
    - Vendored: ``phzyx/admin/static``
    - Dev monorepo: ``packages/admin/web/dist``
    """
    here = Path(__file__).resolve()
    admin_pkg = here.parents[1]  # …/phzyx/admin
    candidates = [
        admin_pkg / "web" / "dist",  # fat wheel / packaged layout
        admin_pkg / "static",
        here.parents[2] / "web" / "dist",
        here.parents[3] / "web" / "dist",
        here.parents[4] / "admin" / "web" / "dist",
    ]
    # packages/admin-fastapi/src/phzyx/admin/fastapi/board.py → packages/admin/web/dist
    if len(here.parents) > 5:
        candidates.append(here.parents[5] / "admin" / "web" / "dist")
    for c in candidates:
        if c.is_dir() and (c / "index.html").exists():
            return c
    return None


def _is_prod() -> bool:
    env = (os.environ.get("PHZYX_ENV") or os.environ.get("ENV") or "").lower()
    return env in {"prod", "production"} or os.environ.get("PHZYX_PRODUCTION", "") in {
        "1",
        "true",
    }
