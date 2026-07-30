"""Forge CLI — primary binary ``forge`` (``phzyx`` kept as alias)."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.5"

_EPILOG = """\
first run (any OS — macOS / Linux / Windows):

  uv tool install phzyx-forge
  # already installed an older build? (need 0.1.4+ so start finds app/)
  uv tool install phzyx-forge --reinstall

  forge new myapp --yes          # same CLI: phzyx new myapp --yes
  cd myapp
  uv sync
  uv run forge start             # same: uv run phzyx start
  # → http://127.0.0.1:9898

  # Already in a uv project folder? scaffold here instead of nesting:
  #   uv add phzyx-forge && uv run forge init --yes && uv run forge start

Do NOT run bare `uvicorn` from Homebrew/global Python — always `uv run …`.

scaffold:
  forge new NAME          create ./NAME then scaffold (greenfield)
  forge init              scaffold in current directory (existing app)
  forge start             local dev server (:9898); prompts if schema pending
  forge add auth|admin    one wiring module only (not a full app)

Binaries: forge (preferred) and phzyx (alias) — both call this CLI.
Pulse is separate: uv add phzyx-pulse → uv run pulse worker

docs: https://phzyx.xyz/forge  ·  beginner: https://phzyx.xyz/forge/beginner
"""


def _cli_prog() -> str:
    """Prefer ``forge``; keep ``phzyx`` when invoked under that name."""
    base = Path(sys.argv[0]).name.lower()
    if base in {"phzyx", "phzyx.exe"}:
        return "phzyx"
    return "forge"


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``forge`` / ``phzyx`` console scripts."""
    args = list(argv if argv is not None else sys.argv[1:])
    prog = _cli_prog()
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Forge CLI (ships with phzyx-forge; FastAPI default path)",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"forge {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    db = sub.add_parser("db", help="database schema commands")
    db_sub = db.add_subparsers(dest="db_command")

    status = db_sub.add_parser("status", help="show dialect version and capabilities")
    status.add_argument("--database-url", default=None)

    push = db_sub.add_parser("push", help="apply desired schema (local; archive-first)")
    push.add_argument("--database-url", default=None)
    push.add_argument("--models", default=None, help="module:attr list of models")
    push.add_argument("--dry-run", action="store_true")
    push.add_argument("--yes", action="store_true")
    push.add_argument("--tui", action="store_true", help="interactive plan review")
    push.add_argument("--allow-production", action="store_true")

    lint = db_sub.add_parser("lint", help="lint plan for destructive ops (CI)")
    lint.add_argument("--database-url", default=None)
    lint.add_argument("--models", default=None)

    seed = db_sub.add_parser("seed", help="run a seed callable module:attr")
    seed.add_argument("target", help="module:callable")

    auth = sub.add_parser("auth", help="auth helpers (requires phzyx-auth)")
    auth_sub = auth.add_subparsers(dest="auth_command")
    su = auth_sub.add_parser("create-superuser", help="create staff superuser")
    su.add_argument("--email")
    su.add_argument("--password")

    add = sub.add_parser(
        "add",
        help="add one battery wiring module (not install; use uv add for packages)",
    )
    add_sub = add.add_subparsers(dest="add_command")
    add_auth = add_sub.add_parser("auth", help="scaffold phzyx-auth wiring")
    add_auth.add_argument("--path", default=".", help="project directory (default: cwd)")
    add_auth.add_argument(
        "--module",
        default="app/forge/auth.py",
        help="output module path (default: app/forge/auth.py)",
    )
    add_auth.add_argument("--force", action="store_true")
    add_auth.add_argument("--dry-run", action="store_true")

    add_admin = add_sub.add_parser("admin", help="scaffold AdminBoard wiring")
    add_admin.add_argument("--path", default=".", help="project directory (default: cwd)")
    add_admin.add_argument(
        "--module",
        default="app/forge/admin.py",
        help="output module path (default: app/forge/admin.py)",
    )
    add_admin.add_argument("--force", action="store_true")
    add_admin.add_argument("--dry-run", action="store_true")

    new_p = sub.add_parser(
        "new",
        help="create a new project directory and scaffold Forge into it",
    )
    new_p.add_argument("name", help="new project directory name (created under --path)")
    new_p.add_argument(
        "--preset",
        default="max",
        choices=["minimal", "normal", "max", "full"],
        help="feature preset (default: max)",
    )
    new_p.add_argument(
        "--layout",
        default="forge",
        choices=["forge", "flat", "mvc", "clean", "phzyx-app"],
        help="folder layout (default: forge; legacy names alias to forge)",
    )
    new_p.add_argument("--path", default=".", help="parent directory (default: cwd)")
    new_p.add_argument("--db", default="sqlite", choices=["sqlite", "postgres"])
    new_p.add_argument("--force", action="store_true")
    new_p.add_argument("--yes", "-y", action="store_true")
    new_p.add_argument("--no-input", action="store_true")
    new_p.add_argument("--dry-run", action="store_true")
    new_p.add_argument("--with-auth", action="store_true")
    new_p.add_argument("--no-auth", action="store_true")
    new_p.add_argument("--with-admin", action="store_true")
    new_p.add_argument("--no-admin", action="store_true")

    def _add_init_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--path", default=".", help="project root (default: cwd)")
        p.add_argument("--name", default=None, help="project name (default: directory name)")
        p.add_argument(
            "--preset",
            default="max",
            choices=["minimal", "normal", "max", "full"],
        )
        p.add_argument(
            "--layout",
            default="forge",
            choices=["forge", "flat", "mvc", "clean", "phzyx-app"],
        )
        p.add_argument("--db", default="sqlite", choices=["sqlite", "postgres"])
        p.add_argument("--force", action="store_true")
        p.add_argument("--yes", "-y", action="store_true")
        p.add_argument("--no-input", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--skip-pyproject", action="store_true")
        p.add_argument("--skip-main", action="store_true")
        p.add_argument("--patch-main", action="store_true")
        p.add_argument("--no-auth", action="store_true")
        p.add_argument("--no-admin", action="store_true")
        p.add_argument("--with-docker", action="store_true")

    # Preferred: forge init (top-level). Nested "forge init" kept for phzyx alias.
    init_p = sub.add_parser(
        "init",
        help="scaffold Forge in --path (default cwd); does not create a parent folder",
    )
    _add_init_flags(init_p)

    forge = sub.add_parser(
        "forge",
        help="(legacy) Forge helpers — prefer: forge init",
    )
    forge_sub = forge.add_subparsers(dest="forge_command")
    fin = forge_sub.add_parser(
        "init",
        help="scaffold Forge in --path (same as top-level init)",
    )
    _add_init_flags(fin)

    sub.add_parser("doctor", help="security and environment checks")

    start_p = sub.add_parser(
        "start",
        help="local dev server (:9898); prompts if schema/migrations pending",
    )
    start_p.add_argument("--path", default=".", help="project root (default: cwd)")
    start_p.add_argument("--host", default="127.0.0.1")
    start_p.add_argument(
        "--port",
        type=int,
        default=9898,
        help="HTTP port (default: 9898)",
    )
    start_p.add_argument("--app", default="app.main:app", help="uvicorn app path")
    start_p.add_argument(
        "--models",
        default="app.forge.registry:ALL_MODELS",
        help="models for schema plan / optional push",
    )
    start_p.add_argument("--no-reload", action="store_true")
    start_p.add_argument(
        "--no-schema",
        action="store_true",
        help="skip schema plan check (never auto-applies either way)",
    )
    start_p.add_argument(
        "--no-migrate",
        action="store_true",
        help="skip pending migrations check",
    )
    start_p.add_argument(
        "--migrate-dir",
        default="migrations",
        help="migrations directory (default: migrations)",
    )
    # Deprecated alias for --no-schema
    start_p.add_argument(
        "--no-push",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    mig = sub.add_parser("migrate", help="versioned SQL migrations")
    mig_sub = mig.add_subparsers(dest="migrate_command")

    m_status = mig_sub.add_parser("status", help="list applied/pending migrations")
    m_status.add_argument("--database-url", default=None)
    m_status.add_argument("--dir", default=None)

    m_create = mig_sub.add_parser("create", help="write upgrade.sql from current plan")
    m_create.add_argument("--database-url", default=None)
    m_create.add_argument("--models", default=None)
    m_create.add_argument("--dir", default=None)
    m_create.add_argument("-m", "--message", default="auto")

    m_apply = mig_sub.add_parser("apply", help="apply pending migrations")
    m_apply.add_argument("--database-url", default=None)
    m_apply.add_argument("--dir", default=None)

    ns = parser.parse_args(args)
    try:
        return _dispatch(ns, parser)
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        return 130
    except SystemExit as exc:
        # argparse / intentional exits
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(f"error: {code}", file=sys.stderr)
        return 2
    except ModuleNotFoundError as exc:
        name = getattr(exc, "name", None) or str(exc)
        print(
            f"error: cannot import {name!r} — run from the project root after `uv sync` "
            f"(scaffolds use package=false; app/ is not installed as a package)",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001 — last-resort CLI UX; still non-zero
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(ns: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not ns.command:
        parser.print_help()
        return 0
    if ns.command == "db":
        return _cmd_db(ns)
    if ns.command == "migrate":
        return _cmd_migrate(ns)
    if ns.command == "auth":
        return _cmd_auth(ns)
    if ns.command == "add":
        return _cmd_add(ns)
    if ns.command == "new":
        return _cmd_new(ns)
    if ns.command == "init":
        return _cmd_init(ns)
    if ns.command == "forge":
        return _cmd_forge(ns)
    if ns.command == "doctor":
        return _cmd_doctor()
    if ns.command == "start":
        return _cmd_start(ns)
    parser.print_help()
    return 1


def _auth_admin_flags(ns: argparse.Namespace) -> tuple[bool | None, bool | None]:
    auth: bool | None = None
    admin: bool | None = None
    if getattr(ns, "no_auth", False):
        auth = False
    elif getattr(ns, "with_auth", False):
        auth = True
    if getattr(ns, "no_admin", False):
        admin = False
    elif getattr(ns, "with_admin", False):
        admin = True
    return auth, admin


def _cmd_new(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from phzyx.cli.new import new_project
    from phzyx.cli.scaffold.write import ScaffoldError

    auth, admin = _auth_admin_flags(ns)
    try:
        paths = new_project(
            ns.name,
            preset=ns.preset,
            layout=ns.layout,
            parent=Path(ns.path),
            force=bool(ns.force),
            dry_run=bool(ns.dry_run),
            yes=bool(ns.yes),
            no_input=bool(ns.no_input),
            db=ns.db,
            auth=auth,
            admin=admin,
        )
    except (FileExistsError, ValueError, KeyError, ScaffoldError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    verb = "would write" if ns.dry_run else "wrote"
    for p in paths:
        print(f"{verb} {p}")
    if not ns.dry_run:
        print("next:")
        print(f"  cd {ns.name}")
        print("  uv sync")
        print("  uv run forge start")
        print("  # same CLI: uv run phzyx start")
        print("  # → http://127.0.0.1:9898  /docs  /admin/")
        print("  # always uv run (project venv) — not bare uvicorn")
    return 0


def _cmd_init(ns: argparse.Namespace) -> int:
    """Top-level ``forge init`` (scaffold in place)."""
    from pathlib import Path

    from phzyx.cli.forge_init import forge_init
    from phzyx.cli.scaffold.write import ScaffoldError

    auth = False if ns.no_auth else None
    admin = False if ns.no_admin else None
    docker = True if getattr(ns, "with_docker", False) else None
    try:
        paths, post, warnings = forge_init(
            path=Path(ns.path),
            name=ns.name,
            preset=ns.preset,
            layout=ns.layout,
            force=bool(ns.force),
            dry_run=bool(ns.dry_run),
            yes=bool(ns.yes),
            no_input=bool(ns.no_input),
            db=ns.db,
            auth=auth,
            admin=admin,
            docker=docker,
            skip_pyproject=bool(getattr(ns, "skip_pyproject", False)),
            skip_main=bool(getattr(ns, "skip_main", False)),
            patch_main=bool(getattr(ns, "patch_main", False)),
        )
    except (FileExistsError, ValueError, KeyError, ScaffoldError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    verb = "would write" if ns.dry_run else "wrote"
    for p in paths:
        print(f"{verb} {p}")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not ns.dry_run:
        print("next:")
        for step in post:
            print(f"  {step}")
    return 0


def _cmd_forge(ns: argparse.Namespace) -> int:
    """Legacy ``phzyx forge init`` / ``forge forge init``."""
    if getattr(ns, "forge_command", None) != "init":
        print("error: unknown forge command (try: forge init)", file=sys.stderr)
        return 1
    return _cmd_init(ns)


def _cmd_doctor() -> int:
    from phzyx.cli.doctor import doctor_exit_code, format_results, run_doctor

    results = run_doctor()
    print(format_results(results))
    return doctor_exit_code(results)


def _cmd_start(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from phzyx.cli.start import start_app

    check_schema = not (bool(ns.no_schema) or bool(ns.no_push))
    return start_app(
        root=Path(ns.path),
        host=ns.host,
        port=int(ns.port),
        app=ns.app,
        models=ns.models,
        reload=not bool(ns.no_reload),
        check_schema=check_schema,
        check_migrate=not bool(ns.no_migrate),
        migrate_dir=str(ns.migrate_dir),
    )


def _cmd_add(ns: argparse.Namespace) -> int:
    from pathlib import Path

    if ns.add_command == "auth":
        from phzyx.cli.add_auth import add_auth

        try:
            paths = add_auth(
                Path(ns.path),
                module_name=ns.module,
                force=bool(ns.force),
                dry_run=bool(ns.dry_run),
            )
        except (FileExistsError, FileNotFoundError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        verb = "would write" if ns.dry_run else "wrote"
        for p in paths:
            print(f"{verb} {p}")
        if not ns.dry_run:
            print("next: uv add 'phzyx-auth[fastapi]' && set PHZYX_AUTH_SECRET")
            if not (Path(ns.path) / "app" / "forge" / "db.py").is_file():
                print(
                    "warning: no app/forge/db.py — provide session_factory "
                    "or run: phzyx forge init",
                    file=sys.stderr,
                )
        return 0
    if ns.add_command == "admin":
        from phzyx.cli.add_admin import add_admin

        try:
            paths = add_admin(
                Path(ns.path),
                module_name=ns.module,
                force=bool(ns.force),
                dry_run=bool(ns.dry_run),
            )
        except (FileExistsError, FileNotFoundError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        verb = "would write" if ns.dry_run else "wrote"
        for p in paths:
            print(f"{verb} {p}")
        if not ns.dry_run:
            print("next: uv add phzyx-admin-fastapi && mount_admin / mount_forge")
            print(
                "warning: Admin AllowAll is dev-only — pass authz= in production",
                file=sys.stderr,
            )
            if not (Path(ns.path) / "app" / "forge" / "db.py").is_file():
                print(
                    "warning: no app/forge/db.py — run: phzyx forge init",
                    file=sys.stderr,
                )
        return 0
    print("error: unknown add command (try: phzyx add auth|admin)", file=sys.stderr)
    return 1


def _cmd_auth(ns: argparse.Namespace) -> int:
    try:
        from phzyx.auth.cli import run_create_superuser
    except ImportError:
        print(
            "error: phzyx-auth not installed (uv add 'phzyx-forge[auth]' or phzyx-auth)",
            file=sys.stderr,
        )
        return 2
    if ns.auth_command == "create-superuser":
        # Never dump stack traces for password policy / validation / cancel.
        return run_create_superuser(ns.email, ns.password)
    if not ns.auth_command:
        print(
            "error: missing auth subcommand (try: forge auth create-superuser)",
            file=sys.stderr,
        )
        return 1
    print("error: unknown auth command", file=sys.stderr)
    return 1


def _cmd_db(ns: argparse.Namespace) -> int:
    from phzyx.engine import connect, load_config, push_schema

    if ns.db_command == "seed":
        return _run_seed(ns.target)

    cfg = load_config()
    url = ns.database_url or cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        print("error: set --database-url or PHZYX_DATABASE_URL", file=sys.stderr)
        return 2

    if ns.db_command == "status":
        conn, adapter = connect(url)
        try:
            ver = adapter.detect_version(conn)
            caps = adapter.capabilities(ver)
            print(f"dialect: {adapter.dialect.value}")
            print(f"version: {ver}")
            print("capabilities:")
            for name in sorted(caps.features):
                print(f"  - {name}")
            return 0
        finally:
            conn.close()

    if ns.db_command == "push":
        models = _load_models(ns.models or cfg.models)
        if not models:
            print("error: provide --models module:attr", file=sys.stderr)
            return 2
        conn, adapter = connect(url)
        try:
            if ns.tui:
                from phzyx.engine.tui_push import push_with_tui

                result = push_with_tui(
                    models,
                    conn,
                    adapter,
                    allow_production=bool(ns.allow_production),
                )
            else:
                result = push_schema(
                    models,
                    conn,
                    adapter,
                    dry_run=bool(ns.dry_run),
                    yes=bool(ns.yes),
                    allow_production=bool(ns.allow_production),
                )
            print(result.plan.summary())
            if result.production_warning:
                print(
                    "WARNING: production-like environment detected. "
                    "Push is for local/dev; prefer migrate for shared/prod. "
                    "Use --allow-production to force (not recommended).",
                    file=sys.stderr,
                )
            if result.plan.empty:
                return 0
            if ns.tui:
                if result.applied:
                    print(f"applied {len(result.statements)} statement(s)")
                return 0
            if ns.dry_run:
                print("(dry-run: no changes applied)")
                return 0
            if result.production_warning and not ns.allow_production:
                print("error: push blocked in production-like env", file=sys.stderr)
                return 3
            if not ns.yes:
                print(
                    "error: pass --yes, --tui, or --dry-run",
                    file=sys.stderr,
                )
                return 2
            if result.applied:
                print(f"applied {len(result.statements)} statement(s)")
            return 0
        finally:
            conn.close()

    if ns.db_command == "lint":
        from phzyx.engine import build_plan, connect, lint_plan
        from phzyx.schema import build_manifest

        models = _load_models(ns.models or cfg.models)
        if not models:
            print("error: provide --models module:attr", file=sys.stderr)
            return 2
        conn, adapter = connect(url)
        try:
            plan = build_plan(build_manifest(models), adapter.introspect(conn))
            result = lint_plan(plan)
            print(result.summary())
            return 0 if result.ok else 1
        finally:
            conn.close()

    print("error: unknown db command", file=sys.stderr)
    return 1


def _run_seed(spec: str) -> int:
    if ":" not in spec:
        print("error: seed target must be module:callable", file=sys.stderr)
        return 2
    mod_name, attr = spec.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    fn()
    print(f"seeded via {spec}")
    return 0


def _cmd_migrate(ns: argparse.Namespace) -> int:
    from phzyx.engine import (
        build_plan,
        connect,
        create_migration,
        load_config,
        migrate_apply,
        migrate_status,
    )
    from phzyx.schema import build_manifest

    cfg = load_config()
    url = ns.database_url or cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    mig_dir = ns.dir or cfg.migrations_dir

    if ns.migrate_command == "status":
        if not url:
            print("error: set --database-url or PHZYX_DATABASE_URL", file=sys.stderr)
            return 2
        conn, _adapter = connect(url)
        try:
            st = migrate_status(conn, mig_dir)
            print("applied:")
            for v in st.applied or ["(none)"]:
                print(f"  - {v}")
            print("pending:")
            for v in st.pending or ["(none)"]:
                print(f"  - {v}")
            return 0
        finally:
            conn.close()

    if ns.migrate_command == "create":
        if not url:
            print("error: set --database-url or PHZYX_DATABASE_URL", file=sys.stderr)
            return 2
        models = _load_models(ns.models or cfg.models)
        if not models:
            print("error: provide --models module:attr", file=sys.stderr)
            return 2
        conn, adapter = connect(url)
        try:
            desired = build_manifest(models)
            live = adapter.introspect(conn)
            plan = build_plan(desired, live)
            print(plan.summary())
            mig = create_migration(plan, mig_dir, dialect=adapter.dialect, name=ns.message)
            print(f"wrote {mig.path}")
            return 0
        finally:
            conn.close()

    if ns.migrate_command == "apply":
        if not url:
            print("error: set --database-url or PHZYX_DATABASE_URL", file=sys.stderr)
            return 2
        conn, adapter = connect(url)
        try:
            applied = migrate_apply(conn, mig_dir, dialect=adapter.dialect)
            if not applied:
                print("no pending migrations")
            else:
                for v in applied:
                    print(f"applied {v}")
            return 0
        finally:
            conn.close()

    print("error: unknown migrate command", file=sys.stderr)
    return 1


def ensure_project_on_sys_path(root: Path | None = None) -> str:
    """Make project root importable for ``package = false`` scaffolds.

    Console-script entry points put the script directory on ``sys.path``, not
    the cwd. Scaffolded apps keep ``app/`` as a plain layout (not an installed
    package), so ``import app.*`` fails unless the project root is inserted.
    """
    path = str((root or Path.cwd()).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def _load_models(spec: str | None) -> list[Any]:
    """Load models from ``module:attribute`` where attribute is a list/tuple of models."""
    if not spec:
        return []
    if ":" not in spec:
        print("error: models spec must be module:attr", file=sys.stderr)
        raise SystemExit(2)
    ensure_project_on_sys_path()
    mod_name, attr = spec.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as exc:
        print(
            f"error: cannot import models module {mod_name!r} ({exc}). "
            "Run from the project root after `uv sync`.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    try:
        obj = getattr(mod, attr)
    except AttributeError:
        print(
            f"error: module {mod_name!r} has no attribute {attr!r}",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    if isinstance(obj, (list, tuple)):
        return list(obj)
    return [obj]
