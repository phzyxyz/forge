"""String templates for the golden Forge FastAPI scaffold."""

from __future__ import annotations

GENERATED = "# GENERATED-BY: phzyx-forge-scaffold v1\n"


def pyproject(
    name: str,
    *,
    auth: bool,
    admin: bool,
    use_forge_meta: bool,
    db: str,
) -> str:
    deps: list[str] = []
    if use_forge_meta or admin:
        extras = ["sqlite"]
        if auth:
            extras.append("auth")
        extra_s = ",".join(extras)
        deps.append(f"phzyx-forge[{extra_s}]")
    else:
        deps.extend(
            [
                "phzyx-schema",
                "phzyx-orm[sqlite]",
                "phzyx-engine",
                "phzyx-cli",
            ]
        )
        if auth:
            deps.append("phzyx-auth[fastapi]")
        if admin:
            deps.append("phzyx-admin-fastapi")
    deps.extend(
        [
            "fastapi",
            "uvicorn[standard]>=0.32",
            "httpx",
            "pytest",
            "pytest-asyncio",
        ]
    )
    if db == "postgres" and "phzyx-forge" not in "".join(deps):
        deps.append("phzyx-orm[postgres]")
    dep_block = ",\n".join(f'  "{d}"' for d in deps)
    return f'''\
[project]
name = "{name}"
version = "0.1.0"
description = "Phzyx Forge app scaffolded by phzyx new / forge init"
requires-python = ">=3.11"
dependencies = [
{dep_block},
]

[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
'''


def gitignore() -> str:
    return """\
.env
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.db
.DS_Store
dist/
build/
*.egg-info/
"""


def env_example(*, auth: bool, db: str) -> str:
    if db == "postgres":
        db_line = "PHZYX_DATABASE_URL=postgresql://phzyx:phzyx@127.0.0.1:5432/phzyx"
        async_line = "ASYNC_DATABASE_URL=postgresql+asyncpg://phzyx:phzyx@127.0.0.1:5432/phzyx"
    else:
        db_line = "PHZYX_DATABASE_URL=sqlite:///./dev.db"
        async_line = "ASYNC_DATABASE_URL=sqlite+aiosqlite:///./dev.db"
    lines = [
        "# Copy to .env — never commit secrets",
        db_line,
        async_line,
        "PHZYX_ENV=development",
    ]
    if auth:
        lines.extend(
            [
                "PHZYX_AUTH_SECRET=replace-with-secrets-token-urlsafe-32-chars-min",
                "PHZYX_AUTH_PRODUCTION=0",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def security_md(*, auth: bool, admin: bool) -> str:
    admin_note = (
        "AdminBoard uses staff authz when auth is enabled."
        if auth and admin
        else (
            "**WARNING:** AdminBoard without auth uses AllowAll — dev/localhost only. "
            "Do not expose `/admin` on a public network."
            if admin
            else "AdminBoard not included in this preset."
        )
    )
    return f"""\
# Security notes (generated)

1. **SQL injection** — Phzyx ORM binds parameters and allowlists identifiers. \
Do not build SQL with f-strings from user input (`session.execute` is an escape hatch).
2. **Admin access** — {admin_note}
3. **Secrets** — set a strong `PHZYX_AUTH_SECRET` (≥32 bytes). Never commit `.env`.
4. **Production** — set `PHZYX_ENV=production`, use HTTPS, prefer migrate over push, \
least-privilege DB user.
5. Run `phzyx doctor` before deploy.

See product docs: Security guide on phzyx.xyz/forge/security
"""


def readme(
    name: str,
    *,
    auth: bool,
    admin: bool,
    preset: str,
) -> str:
    auth_export = ""
    if auth:
        auth_export = (
            "export PHZYX_AUTH_SECRET=\"$(python -c 'import secrets; "
            "print(secrets.token_urlsafe(32))')\"\n"
        )
    admin_line = "- AdminBoard: http://127.0.0.1:8000/admin/\n" if admin else ""
    auth_line = "- Auth: http://127.0.0.1:8000/auth/ (see AUTH.md)\n" if auth else ""
    return f"""\
# {name}

Scaffolded by **Phzyx Forge** (`phzyx new` / `phzyx forge init`, preset **{preset}**).

## Setup

```bash
uv sync
cp .env.example .env
{auth_export}uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes
uv run uvicorn app.main:app --reload
```

## URLs

- API health: http://127.0.0.1:8000/api/v1/health
- OpenAPI: http://127.0.0.1:8000/docs
- Items API: http://127.0.0.1:8000/api/v1/items
{admin_line}{auth_line}
## Layout

- `app/api/` — async FastAPI product routes
- `app/forge/` — Phzyx wiring (db, models, registry, admin, auth)
- Large apps: put domain models in `app/<domain>/models.py` and register them in \
`app/forge/registry.py`

## Security

See [SECURITY.md](./SECURITY.md). Run `phzyx doctor` before production.

## Growing beyond Item

1. Add `app/catalog/models.py` (or similar)
2. Append models to `ALL_MODELS` in `app/forge/registry.py`
3. Add async routes under `app/api/routes/`
4. `phzyx db push --models app.forge.registry:ALL_MODELS --yes`
"""


def docker_compose() -> str:
    return """\
services:
  api:
    image: python:3.12-slim
    working_dir: /app
    volumes:
      - .:/app
    command: >
      sh -c "pip install uv && uv sync &&
      uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
    ports:
      - "8000:8000"
    environment:
      PHZYX_DATABASE_URL: sqlite:////app/dev.db
      ASYNC_DATABASE_URL: sqlite+aiosqlite:////app/dev.db
      PHZYX_ENV: development
"""


def app_init() -> str:
    return GENERATED + '"""Application package."""\n'


def core_init() -> str:
    return GENERATED + '"""Core settings and shared config."""\n'


def core_config() -> str:
    return (
        GENERATED
        + '''\
"""Environment settings (stdlib — no extra settings dependency)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    async_database_url: str
    env: str
    auth_secret: str | None

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}


def load_settings() -> Settings:
    sync_url = (
        _env("PHZYX_DATABASE_URL")
        or _env("DATABASE_URL")
        or "sqlite:///./dev.db"
    )
    async_url = _env("ASYNC_DATABASE_URL")
    if not async_url:
        if sync_url.startswith("sqlite:"):
            async_url = sync_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        elif sync_url.startswith("postgresql://"):
            async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgres://"):
            async_url = sync_url.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            async_url = sync_url
    secret = _env("PHZYX_AUTH_SECRET") or None
    return Settings(
        database_url=sync_url,
        async_database_url=async_url,
        env=_env("PHZYX_ENV", "development"),
        auth_secret=secret,
    )


settings = load_settings()
'''
    )


def forge_db() -> str:
    return (
        GENERATED
        + '''\
"""Dual database engines — async for the app, sync for AdminBoard / auth stores."""

from __future__ import annotations

from collections.abc import AsyncIterator

from phzyx.orm import AsyncSession, Session, create_async_engine, create_engine
from phzyx.schema.types import Dialect

from app.core.config import settings


def detect_dialect(url: str) -> Dialect:
    u = url.lower()
    if u.startswith("sqlite"):
        return Dialect.SQLITE
    if u.startswith("postgres"):
        return Dialect.POSTGRES
    if u.startswith("mysql") or u.startswith("mariadb"):
        return Dialect.MYSQL
    if u.startswith("mssql") or u.startswith("sqlserver"):
        return Dialect.MSSQL
    return Dialect.SQLITE


DIALECT = detect_dialect(settings.database_url)
async_engine = create_async_engine(settings.async_database_url)
sync_engine = create_engine(settings.database_url)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — async session for product routes."""
    session = AsyncSession(await async_engine.connect(), dialect=DIALECT)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_admin_session() -> Session:
    """AdminBoard / auth ORM stores — sync Session over the same database."""
    return Session(sync_engine.connect(), dialect=DIALECT)
'''
    )


def forge_models() -> str:
    return (
        GENERATED
        + '''\
"""Sample domain models (day-1).

Large apps: move models into domain packages (e.g. ``app/catalog/models.py``)
and register them in ``app.forge.registry.ALL_MODELS``. Keep this file small.
"""

from __future__ import annotations

from phzyx.schema import Field, Model


class Item(Model):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field()
    notes: str | None = Field(default=None)

    class Meta:
        table = "items"


MODELS = [Item]
'''
    )


def forge_registry(*, auth: bool) -> str:
    auth_block = (
        """\
try:
    from phzyx.auth import AUTH_MODELS as _AUTH_MODELS
except ImportError:  # pragma: no cover
    _AUTH_MODELS = []
"""
        if auth
        else "_AUTH_MODELS = []\n"
    )
    return (
        GENERATED
        + f'''\
"""Compose models for push / migrate / AdminBoard.

Day-1: sample Item. Medium+: import domain models and append to ALL_MODELS.
"""

from __future__ import annotations

from app.forge.models import MODELS

{auth_block}
# from app.catalog.models import Product  # large-app pattern

ALL_MODELS = [
    *MODELS,
    *_AUTH_MODELS,
    # Product,
]
'''
    )


def forge_admin(*, auth: bool) -> str:
    if auth:
        authz_import = "from app.forge.auth import authz_for_admin\n"
        authz_arg = "authz=authz_for_admin()"
    else:
        authz_import = "from phzyx.admin.auth import AllowAll\n"
        authz_arg = "authz=AllowAll()  # DEV ONLY — see SECURITY.md"
    return (
        GENERATED
        + f'''\
"""AdminBoard mount (operator UI + headless API)."""

from __future__ import annotations

from fastapi import FastAPI
from phzyx.admin.fastapi import AdminBoard
{authz_import}
from app.forge.db import get_admin_session
from app.forge.registry import ALL_MODELS


def mount_admin(app: FastAPI, *, prefix: str = "/admin") -> AdminBoard:
    """Mount AdminBoard on the FastAPI app."""
    return AdminBoard(
        app,
        models=list(ALL_MODELS),
        session_factory=get_admin_session,
        theme="stellar-dark",
        prefix=prefix,
        {authz_arg},
    )
'''
    )


def forge_auth() -> str:
    return (
        GENERATED
        + '''\
"""phzyx-auth wiring (cookie sessions + AdminBoard authz)."""

from __future__ import annotations

import os
from collections.abc import Callable

from phzyx.auth import (
    AUTH_MODELS,
    AuthConfig,
    AuthService,
    HybridUserMap,
    OrmAPIKeyStore,
    OrmPasswordResetStore,
    OrmSessionStore,
    OrmUserRepository,
    PhzyxAuthz,
)
from phzyx.auth.adapters.fastapi import mount_auth
from phzyx.orm import Session

from app.core.config import settings

SessionFactory = Callable[[], Session]


def build_auth_service(session_factory: SessionFactory) -> AuthService:
    secret = settings.auth_secret or os.environ.get("PHZYX_AUTH_SECRET", "")
    if not secret:
        if settings.is_production:
            raise RuntimeError("PHZYX_AUTH_SECRET is required in production")
        secret = "dev-only-insecure-secret-min-32b!!"
    production = settings.is_production or os.environ.get(
        "PHZYX_AUTH_PRODUCTION", ""
    ).lower() in {"1", "true", "yes"}
    cfg = AuthConfig(
        secret=secret,
        production=production,
        cookie_secure=production,
        csrf_protect=True,
    )
    repo = OrmUserRepository(session_factory=session_factory)
    return AuthService(
        config=cfg,
        sessions=OrmSessionStore(session_factory=session_factory),
        api_keys=OrmAPIKeyStore(session_factory=session_factory),
        password_reset_store=OrmPasswordResetStore(session_factory=session_factory),
        users=HybridUserMap(repo=repo),  # type: ignore[arg-type]
    )


def install_auth(app, session_factory: SessionFactory, *, prefix: str = "/auth") -> AuthService:
    svc = build_auth_service(session_factory)
    mount_auth(app, svc, prefix=prefix, middleware=True)
    app.state.phzyx_auth = svc
    return svc


def authz_for_admin(*, require_staff: bool = True) -> PhzyxAuthz:
    return PhzyxAuthz(require_staff=require_staff)


__all__ = [
    "AUTH_MODELS",
    "authz_for_admin",
    "build_auth_service",
    "install_auth",
]
'''
    )


def forge_init(*, auth: bool, admin: bool) -> str:
    lines = [
        GENERATED,
        '"""Phzyx Forge integration island — mount_forge(app)."""',
        "",
        "from __future__ import annotations",
        "",
        "from fastapi import FastAPI",
        "",
    ]
    if auth:
        lines.append("from app.forge.auth import install_auth")
        lines.append("from app.forge.db import get_admin_session")
    if admin:
        lines.append("from app.forge.admin import mount_admin")
    lines.extend(
        [
            "",
            "",
            "def mount_forge(app: FastAPI) -> None:",
            '    """Wire auth + AdminBoard onto the FastAPI app."""',
        ]
    )
    if auth:
        lines.append("    install_auth(app, get_admin_session)")
    if admin:
        lines.append("    mount_admin(app)")
    if not auth and not admin:
        lines.append("    return  # minimal: API-only; no operator mounts")
    lines.append("")
    # marker content companion written separately
    return "\n".join(lines)


def forge_marker() -> str:
    return "phzyx-forge-scaffold v1\n"


def api_init() -> str:
    return GENERATED + '"""HTTP API package."""\n'


def api_deps() -> str:
    return (
        GENERATED
        + '''\
"""Shared FastAPI dependencies."""

from app.forge.db import get_session

__all__ = ["get_session"]
'''
    )


def api_schemas_init() -> str:
    return GENERATED + '"""Request/response schemas."""\n'


def api_schemas_items() -> str:
    return (
        GENERATED
        + '''\
"""Item API schemas — allowlisted fields only (mass-assignment safe)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    notes: str | None = None
'''
    )


def api_routes_init() -> str:
    return (
        GENERATED
        + '''\
"""API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health, items

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
'''
    )


def api_routes_health() -> str:
    return (
        GENERATED
        + '''\
"""Health check."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
'''
    )


def api_routes_items() -> str:
    return (
        GENERATED
        + '''\
"""Item CRUD — async product API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from phzyx.orm import AsyncSession, eq

from app.api.deps import get_session
from app.api.schemas.items import ItemCreate, ItemRead
from app.forge.models import Item

router = APIRouter()


@router.get("", response_model=list[ItemRead])
async def list_items(
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[Item]:
    return await session.query(Item, limit=limit)


@router.post("", response_model=ItemRead, status_code=201)
async def create_item(
    body: ItemCreate,
    session: AsyncSession = Depends(get_session),
) -> Item:
    return await session.add(Item(name=body.name, notes=body.notes))


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
) -> Item:
    rows = await session.query(Item, where=[eq("id", item_id)], limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="item not found")
    return rows[0]
'''
    )


def main_py(*, title: str, auth: bool, admin: bool) -> str:
    return (
        GENERATED
        + f'''\
"""FastAPI entrypoint — async product API + Forge mounts."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.forge import mount_forge


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="{title}", version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")
mount_forge(app)
'''
    )


def test_conftest() -> str:
    return (
        GENERATED
        + '''\
"""Pytest configuration."""

from __future__ import annotations

import pytest

pytest_plugins: list[str] = []
'''
    )


def test_health() -> str:
    return (
        GENERATED
        + '''\
"""Smoke: health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
'''
    )


def test_items() -> str:
    return (
        GENERATED
        + '''\
"""Items API shape (may skip DB if schema not pushed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_create_validation() -> None:
    client = TestClient(app)
    r = client.post("/api/v1/items", json={"name": "x", "extra": 1})
    # extra fields forbidden
    assert r.status_code == 422
'''
    )


def admin_md() -> str:
    return """\
# AdminBoard

Mounted at `/admin/` via `app.forge.admin.mount_admin`.

```bash
uv run uvicorn app.main:app --reload
# open http://127.0.0.1:8000/admin/
```

Models come from `app.forge.registry.ALL_MODELS`.
"""


def auth_md() -> str:
    return """\
# Auth

```bash
export PHZYX_AUTH_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes
# optional: phzyx auth create-superuser
```

Routes under `/auth/`. Admin uses staff authz when enabled.
"""
