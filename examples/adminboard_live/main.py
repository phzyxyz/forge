"""Live AdminBoard demo — FastAPI + phzyx-auth cookie sessions + PhzyxAuthz.

Rich seed: many rows on every demo + auth table (see seed_rich.py).
Reseed when SEED_SCHEMA_VERSION changes or PHZYX_DEMO_RESEED=1.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from phzyx.admin.fastapi import AdminBoard
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
from phzyx.auth import models as auth_models
from phzyx.auth.adapters.fastapi import mount_auth
from phzyx.auth.password import PasswordHasher
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, FileField, Model, Session
from phzyx.schema.types import Dialect
from seed_rich import (
    SEED_SCHEMA_VERSION,
    build_assets,
    build_auth_seed,
    build_comments,
    build_invoices,
    build_memberships,
    build_orgs,
    build_post_tags,
    build_posts,
    build_project_members,
    build_projects,
    build_tags,
    build_users,
    extra_media_files,
)
from starlette.requests import Request

# Keys written by seed — tests may assert core keys exist under media root.
SEED_ASSET_KEYS: tuple[str, ...] = (
    "brand/logo.svg",
    "marketing/hero.svg",
    "brand/wordmark.svg",
    "docs/readme.txt",
    "docs/changelog.md",
    "marketing/banner.svg",
    "avatars/ops.svg",
    "avatars/dev.svg",
    "uploads/sample-notes.txt",
)

DEFAULT_DB = Path(__file__).with_name("demo.db")
DEFAULT_MEDIA = Path(__file__).with_name("media")

# Dense defaults — override with env for lighter CI if needed
N_USERS = int(os.environ.get("PHZYX_DEMO_N_USERS", "90"))
N_POSTS = int(os.environ.get("PHZYX_DEMO_N_POSTS", "160"))
N_COMMENTS = int(os.environ.get("PHZYX_DEMO_N_COMMENTS", "220"))
N_ORGS = int(os.environ.get("PHZYX_DEMO_N_ORGS", "12"))
N_PROJECTS = int(os.environ.get("PHZYX_DEMO_N_PROJECTS", "40"))
N_INVOICES = int(os.environ.get("PHZYX_DEMO_N_INVOICES", "60"))
N_ASSETS = int(os.environ.get("PHZYX_DEMO_N_ASSETS", "48"))


def _admin_creds() -> tuple[str, str]:
    """Demo SPA login (read env at call time so tests can monkeypatch)."""
    return (
        os.environ.get("PHZYX_ADMIN_USER", "admin"),
        os.environ.get("PHZYX_ADMIN_PASSWORD", "phzyx"),
    )


def _demo_secret() -> str:
    return os.environ.get("PHZYX_AUTH_SECRET", "phzyx-demo-auth-secret-key-32b!!")


# —— Domain models (rich columns for filters / widgets) ——


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    name: str = Field()
    active: bool = Field(default=True)
    joined: date | None = Field(default=None)
    notes: str | None = Field(default="")
    team: str = Field(default="")
    title: str = Field(default="")
    country: str = Field(default="")
    score: int = Field(default=0)
    last_seen: datetime | None = Field(default=None)

    class Meta:
        table = "users"
        register = False


class Organization(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    slug: str = Field()
    plan: str = Field(default="free")
    seats: int = Field(default=5)
    active: bool = Field(default=True)
    region: str = Field(default="US")
    mrr_cents: int = Field(default=0)
    created_on: date | None = Field(default=None)

    class Meta:
        table = "organizations"
        register = False


class Membership(Model):
    org_id: int = Field(primary_key=True, foreign_key="organizations.id")
    user_id: int = Field(primary_key=True, foreign_key="users.id")
    role: str = Field(default="member")
    since: date | None = Field(default=None)
    primary: bool = Field(default=False)

    class Meta:
        table = "memberships"
        register = False


class Asset(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    path: str = FileField()
    kind: str = Field(default="upload")
    size_bytes: int = Field(default=0)
    uploaded_by: int | None = Field(default=None, foreign_key="users.id")
    public: bool = Field(default=True)
    caption: str = Field(default="")

    class Meta:
        table = "assets"
        register = False


class Post(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    author_id: int = Field(foreign_key="users.id")
    body: str = Field(default="")
    status: str = Field(default="draft")
    published: bool = Field(default=False)
    published_at: date | None = Field(default=None)
    views: int = Field(default=0)
    featured: bool = Field(default=False)
    summary: str = Field(default="")

    class Meta:
        table = "posts"
        register = False


class Tag(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    slug: str = Field(default="")
    color: str = Field(default="#22d3ee")
    description: str = Field(default="")
    featured: bool = Field(default=False)

    class Meta:
        table = "tags"
        register = False


class PostTag(Model):
    post_id: int = Field(primary_key=True, foreign_key="posts.id")
    tag_id: int = Field(primary_key=True, foreign_key="tags.id")

    class Meta:
        table = "post_tags"
        register = False


class Comment(Model):
    id: int = Field(primary_key=True)
    post_id: int = Field(foreign_key="posts.id")
    author_id: int = Field(foreign_key="users.id")
    body: str = Field(default="")
    approved: bool = Field(default=True)
    created_at: datetime | None = Field(default=None)
    likes: int = Field(default=0)

    class Meta:
        table = "comments"
        register = False


class Project(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    owner_id: int = Field(foreign_key="users.id")
    status: str = Field(default="planned")
    budget_usd: int = Field(default=0)
    due_date: date | None = Field(default=None)
    priority: int = Field(default=3)
    description: str = Field(default="")

    class Meta:
        table = "projects"
        register = False


class ProjectMember(Model):
    project_id: int = Field(primary_key=True, foreign_key="projects.id")
    user_id: int = Field(primary_key=True, foreign_key="users.id")
    role: str = Field(default="member")
    allocation_pct: int = Field(default=50)

    class Meta:
        table = "project_members"
        register = False


class Invoice(Model):
    id: int = Field(primary_key=True)
    org_id: int = Field(foreign_key="organizations.id")
    number: str = Field()
    amount_cents: int = Field(default=0)
    currency: str = Field(default="USD")
    status: str = Field(default="open")
    issued_on: date | None = Field(default=None)
    due_on: date | None = Field(default=None)
    memo: str = Field(default="")

    class Meta:
        table = "invoices"
        register = False


DEMO_MODELS = [
    User,
    Organization,
    Membership,
    Asset,
    Post,
    Tag,
    PostTag,
    Comment,
    Project,
    ProjectMember,
    Invoice,
]


def _env_paths() -> tuple[Path, Path]:
    db = Path(os.environ.get("PHZYX_DEMO_DB", str(DEFAULT_DB)))
    media = Path(os.environ.get("PHZYX_DEMO_MEDIA", str(DEFAULT_MEDIA)))
    return db, media


def _seed_marker(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + f".seed_v{SEED_SCHEMA_VERSION}")


def _svg(w: int, h: int, fill: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
        f'<rect width="{w}" height="{h}" rx="24" fill="{fill}"/>'
        f'<text x="{w // 2}" y="{h // 2 + 8}" text-anchor="middle" font-size="28" '
        f'fill="#041018" font-family="system-ui,sans-serif">{label}</text></svg>'
    )


def write_seed_media(media_root: Path, *, overwrite: bool = False) -> list[Path]:
    """Write real bytes for SEED_ASSET_KEYS + gallery bulk."""
    media_root.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {
        "brand/logo.svg": _svg(240, 240, "#22d3ee", "P"),
        "brand/wordmark.svg": _svg(480, 120, "#67e8f9", "Phzyx"),
        "marketing/hero.svg": _svg(640, 320, "#8b5cf6", "Phzyx"),
        "marketing/banner.svg": _svg(800, 200, "#fb923c", "AdminBoard"),
        "avatars/ops.svg": _svg(128, 128, "#4ade80", "Ops"),
        "avatars/dev.svg": _svg(128, 128, "#60a5fa", "Dev"),
        "docs/readme.txt": (
            "Phzyx AdminBoard live demo\n"
            "========================\n\n"
            "Rich seed dataset for tables, relations, media, and auth.\n"
        ),
        "docs/changelog.md": (
            "# Changelog\n\n"
            "## 0.1.0\n"
            "- Diamond AdminBoard + rich seed\n"
            "- phzyx-auth cookie sessions\n"
            "- Media library + dropzone\n"
        ),
        "uploads/sample-notes.txt": (
            "Meeting notes — platform sync\n"
            "- Rich seed for AdminBoard\n"
            "- M2M / filters / export stress\n"
        ),
    }
    files.update(extra_media_files())
    out: list[Path] = []
    for key, body in files.items():
        path = media_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not path.exists():
            path.write_text(body, encoding="utf-8")
        out.append(path)
    return out


def _should_reseed(db_path: Path, force: bool) -> bool:
    if force or not db_path.exists():
        return True
    return not _seed_marker(db_path).exists()


def seed(
    *,
    db_path: Path | None = None,
    media_root: Path | None = None,
    force: bool | None = None,
) -> None:
    """Seed demo DB + media. Reseeds when version marker missing or force/env set."""
    db_path = db_path or _env_paths()[0]
    media_root = media_root or _env_paths()[1]
    force = (
        force
        if force is not None
        else os.environ.get("PHZYX_DEMO_RESEED", "").lower() in {"1", "true", "yes"}
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    reseed = _should_reseed(db_path, force)
    if reseed and db_path.exists():
        db_path.unlink()
        for p in db_path.parent.glob(db_path.name + ".seed_v*"):
            p.unlink(missing_ok=True)

    write_seed_media(media_root, overwrite=reseed)
    url = f"sqlite:///{db_path}"
    conn, adapter = connect(url)
    try:
        push_schema(
            [*DEMO_MODELS, *AUTH_MODELS],
            conn,
            adapter,
            yes=True,
        )
        session = Session(conn, dialect=Dialect.SQLITE)
        if reseed or session.get(User, 1) is None:
            _load_all(session)
            session.commit()
            _seed_marker(db_path).write_text(str(SEED_SCHEMA_VERSION), encoding="utf-8")
        session.close()
    finally:
        conn.close()


def _add_rows(session: Session, model: type[Model], rows: list[dict]) -> None:  # type: ignore[type-arg]
    for row in rows:
        session.add(model(**row))


def _load_all(session: Session) -> None:
    users = build_users(N_USERS)
    orgs = build_orgs(N_ORGS)
    tags = build_tags()
    posts = build_posts(N_POSTS, user_n=N_USERS)
    assets = build_assets(N_ASSETS)
    comments = build_comments(N_COMMENTS, post_n=N_POSTS, user_n=N_USERS)
    projects = build_projects(N_PROJECTS, user_n=N_USERS)
    invoices = build_invoices(N_INVOICES, org_n=N_ORGS)

    _add_rows(session, User, users)
    _add_rows(session, Organization, orgs)
    _add_rows(session, Membership, build_memberships(N_USERS, N_ORGS))
    _add_rows(session, Asset, assets)
    _add_rows(session, Post, posts)
    _add_rows(session, Tag, tags)
    _add_rows(session, PostTag, build_post_tags(N_POSTS, len(tags)))
    _add_rows(session, Comment, comments)
    _add_rows(session, Project, projects)
    _add_rows(session, ProjectMember, build_project_members(N_PROJECTS, N_USERS))
    _add_rows(session, Invoice, invoices)

    auth = build_auth_seed()
    _add_rows(session, auth_models.Group, auth["groups"])
    _add_rows(session, auth_models.Permission, auth["permissions"])
    # SPA login uses PHZYX_ADMIN_USER (default "admin") as identity email key
    now = datetime(2026, 7, 1, 12, 0, 0)
    demo_hash = PasswordHasher(min_length=5).hash("phzyx")
    for i, email, uname, staff, superu in (
        (1, "admin", "admin", True, True),
        (2, "editor@phzyx.xyz", "editor", True, False),
        (3, "viewer@phzyx.xyz", "viewer", False, False),
        (4, "billing@phzyx.xyz", "billing", True, False),
        (5, "support@phzyx.xyz", "support", True, False),
        (6, "ops@phzyx.xyz", "ops", True, False),
        (7, "dev@phzyx.xyz", "dev", True, False),
        (8, "bot+ci@phzyx.xyz", "ci", True, False),
    ):
        session.add(
            auth_models.User(
                id=i,
                email=email,
                username=uname,
                password_hash=demo_hash,
                is_active=True,
                is_staff=staff,
                is_superuser=superu,
                email_verified=True,
                # Demo SPA has no MFA step UI — keep password-only login
                mfa_enabled=False,
                failed_login_count=0 if i != 3 else 2,
                locked_until=None,
                last_login_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()

    _add_rows(session, auth_models.UserGroup, auth["user_groups"])
    _add_rows(session, auth_models.GroupPermission, auth["group_permissions"])
    _add_rows(session, auth_models.UserPermission, auth["user_permissions"])
    _add_rows(session, auth_models.AuthSession, auth["sessions"])
    _add_rows(session, auth_models.RefreshToken, auth["refresh_tokens"])
    _add_rows(session, auth_models.APIKey, auth["api_keys"])
    _add_rows(session, auth_models.PasswordResetToken, auth["password_resets"])
    _add_rows(session, auth_models.AuditEvent, auth["audit"])
    _add_rows(session, auth_models.OAuthAccount, auth["oauth"])
    # Seed MFA factors as unverified samples only — users stay mfa_enabled=False


def build_auth_service(session_factory) -> AuthService:  # type: ignore[no-untyped-def]
    """ORM-backed auth (sessions, users, API keys, password resets)."""
    user, password = _admin_creds()
    cfg = AuthConfig(
        secret=_demo_secret(),
        production=False,
        cookie_secure=False,
        csrf_protect=True,
        password=PasswordHasher(min_length=5),  # allow demo password "phzyx"
    )
    repo = OrmUserRepository(session_factory=session_factory)
    svc = AuthService(
        config=cfg,
        sessions=OrmSessionStore(session_factory=session_factory),
        api_keys=OrmAPIKeyStore(session_factory=session_factory),
        password_reset_store=OrmPasswordResetStore(session_factory=session_factory),
        users=HybridUserMap(repo=repo),  # type: ignore[arg-type]
    )
    email = user.strip().lower()
    if email not in svc.users:
        svc.register(email, password, is_staff=True, is_superuser=True)
    return svc


def create_app(
    *,
    db_path: Path | None = None,
    media_root: Path | None = None,
    theme: str | None = None,
    auth_service: AuthService | None = None,
) -> FastAPI:
    """Build app (used by uvicorn and tests)."""
    db_path = db_path or _env_paths()[0]
    media_root = media_root or _env_paths()[1]
    theme = theme or os.environ.get("PHZYX_ADMIN_THEME", "stellar-dark")
    seed(db_path=db_path, media_root=media_root)

    def session_factory() -> Session:
        conn, _ = connect(f"sqlite:///{db_path}")
        return Session(conn, dialect=Dialect.SQLITE)

    application = FastAPI(title="Phzyx AdminBoard live demo", version="0.1.0")
    auth_svc = auth_service or build_auth_service(session_factory)
    mount_auth(application, auth_svc, middleware=False)

    AdminBoard(
        application,
        models=[*DEMO_MODELS, *AUTH_MODELS],
        session_factory=session_factory,
        theme=theme,
        storage_root=media_root,
        authz=PhzyxAuthz(require_staff=True),
        database_url=f"sqlite:///{db_path}",
    )

    @application.middleware("http")
    async def phzyx_auth_gate(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Resolve principal; require auth for /admin/api; CSRF for cookie mutations."""
        from phzyx.auth.csrf import csrf_valid, extract_csrf, should_check_csrf

        cookie = request.cookies.get(auth_svc.config.session_cookie_name)
        authz_h = request.headers.get("authorization")
        api_key = request.headers.get("x-api-key")
        try:
            principal = auth_svc.resolve_principal(
                session_token=cookie,
                authorization=authz_h,
                api_key=api_key,
            )
        except Exception:
            principal = None
        request.state.principal = principal
        request.state.auth_service = auth_svc

        path = request.url.path
        if path.startswith("/admin/api"):
            if principal is None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "unauthorized",
                            "message": "Login required",
                            "details": {},
                        }
                    },
                    status_code=401,
                )
            if should_check_csrf(
                request.method,
                has_session_cookie=bool(cookie) and not authz_h and not api_key,
                csrf_protect=auth_svc.config.csrf_protect,
            ):
                c_tok, h_tok = extract_csrf(
                    request,
                    cookie_name=auth_svc.config.csrf_cookie_name,
                    header_name=auth_svc.config.csrf_header_name,
                )
                if not csrf_valid(c_tok, h_tok):
                    return JSONResponse(
                        {
                            "error": {
                                "code": "forbidden",
                                "message": "CSRF validation failed",
                                "details": {},
                            }
                        },
                        status_code=403,
                    )

        return await call_next(request)

    @application.get("/health")
    def health() -> dict[str, str | int]:
        user, _ = _admin_creds()
        return {
            "status": "ok",
            "admin": "/admin/",
            "user": user,
            "seed_version": SEED_SCHEMA_VERSION,
        }

    @application.get("/")
    def root() -> dict[str, str]:
        user, _ = _admin_creds()
        return {
            "message": "Phzyx AdminBoard live demo",
            "admin": "/admin/",
            "api": "/admin/api/v1/resources",
            "auth": "/auth/login",
            "docs": "/docs",
            "login": f"SPA Sign in — user={user} (phzyx-auth session cookie)",
            "health": "/health",
        }

    application.state.phzyx_demo_db = db_path  # type: ignore[attr-defined]
    application.state.phzyx_demo_media = media_root  # type: ignore[attr-defined]
    application.state.phzyx_auth = auth_svc  # type: ignore[attr-defined]
    return application


app = create_app()
