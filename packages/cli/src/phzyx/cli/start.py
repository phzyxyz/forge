"""``forge start`` — local dev server with safe schema prompts (no silent push)."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import TextIO


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9898
DEFAULT_APP = "app.main:app"
DEFAULT_MODELS = "app.forge.registry:ALL_MODELS"
DEFAULT_MIGRATE_DIR = "migrations"


def ensure_dotenv(root: Path) -> bool:
    """Copy .env.example → .env if missing. Returns True if created."""
    env = root / ".env"
    example = root / ".env.example"
    if env.is_file() or not example.is_file():
        return False
    text = example.read_text(encoding="utf-8")
    if "PHZYX_AUTH_SECRET=" in text and "token_urlsafe" not in text:
        secret = secrets.token_urlsafe(32)
        lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("PHZYX_AUTH_SECRET=") and len(line.split("=", 1)[-1].strip()) < 16:
                lines.append(f"PHZYX_AUTH_SECRET={secret}")
            else:
                lines.append(line)
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    env.write_text(text, encoding="utf-8")
    return True


def load_dotenv(root: Path) -> None:
    """Minimal .env loader (no extra deps): KEY=VALUE into os.environ if unset."""
    path = root / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _prompt_yes_no(
    question: str,
    *,
    default: bool = False,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> bool:
    """y/N (or Y/n). Empty uses default. Empty non-TTY always no (safe)."""
    inp = input_stream or sys.stdin
    out = output_stream or sys.stdout
    tty = bool(getattr(inp, "isatty", lambda: False)())
    hint = "Y/n" if default else "y/N"
    if tty:
        out.write(f"{question} [{hint}] ")
    else:
        out.write(f"{question} [{hint}] (non-interactive) ")
    out.flush()
    answer = inp.readline().strip().lower()
    if not answer:
        # Never auto-yes when non-interactive and no answer piped
        if not tty:
            out.write("→ no\n")
            out.flush()
            return False
        return default
    return answer in {"y", "yes"}


def preview_schema_plan(*, models: str) -> tuple[object | None, int]:
    """Dry-run schema plan. Returns (plan, exit_code). plan is SchemaPlan or None on error."""
    from phzyx.engine import connect, load_config, push_schema

    from phzyx.cli import _load_models

    cfg = load_config()
    url = cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        print(
            "error: set PHZYX_DATABASE_URL (or create .env from scaffold)",
            file=sys.stderr,
        )
        return None, 2
    model_list = _load_models(models or cfg.models)
    if not model_list:
        print(f"error: could not load models {models!r}", file=sys.stderr)
        return None, 2
    conn, adapter = connect(url)
    try:
        result = push_schema(
            model_list,
            conn,
            adapter,
            dry_run=True,
            yes=False,
            allow_production=False,
        )
        return result.plan, 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: schema plan failed: {exc}", file=sys.stderr)
        return None, 2
    finally:
        conn.close()


def apply_schema_push(*, models: str) -> int:
    """Apply schema push after user already confirmed (yes=True)."""
    from phzyx.engine import connect, load_config, push_schema

    from phzyx.cli import _load_models

    cfg = load_config()
    url = cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        return 2
    model_list = _load_models(models or cfg.models)
    if not model_list:
        return 2
    conn, adapter = connect(url)
    try:
        result = push_schema(
            model_list,
            conn,
            adapter,
            dry_run=False,
            yes=True,
            allow_production=False,
        )
        print(result.plan.summary())
        if result.production_warning and not result.applied:
            print(
                "error: production-like env — refuse push; use migrate",
                file=sys.stderr,
            )
            return 2
        if result.applied:
            print(f"applied {len(result.statements)} statement(s)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: db push failed: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


def check_pending_migrations(
    *,
    migrate_dir: str = DEFAULT_MIGRATE_DIR,
) -> tuple[list[str], int]:
    """Return (pending_versions, exit_code). Empty list if none or no dir."""
    from phzyx.engine import connect, load_config, migrate_status

    root = Path.cwd()
    path = root / migrate_dir
    if not path.is_dir():
        return [], 0
    cfg = load_config()
    url = cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        return [], 0
    conn, adapter = connect(url)
    try:
        st = migrate_status(conn, path, dialect=adapter.dialect)
        return list(st.pending), 0
    except Exception as exc:  # noqa: BLE001
        print(f"warning: could not read migrations: {exc}", file=sys.stderr)
        return [], 0
    finally:
        conn.close()


def apply_pending_migrations(*, migrate_dir: str = DEFAULT_MIGRATE_DIR) -> int:
    from phzyx.engine import connect, load_config, migrate_apply

    path = Path.cwd() / migrate_dir
    cfg = load_config()
    url = cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        print("error: no database URL for migrate apply", file=sys.stderr)
        return 2
    conn, adapter = connect(url)
    try:
        applied = migrate_apply(conn, path, dialect=adapter.dialect)
        if not applied:
            print("no pending migrations")
        else:
            for v in applied:
                print(f"applied {v}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: migrate apply failed: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


def maybe_handle_schema(
    *,
    models: str,
    check_schema: bool,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    """Dry-run plan; prompt before any push. Never silent-apply.

    Returns 0 to continue start, non-zero to abort.
    """
    if not check_schema:
        return 0
    env = (os.environ.get("PHZYX_ENV") or "development").lower()
    if env in {"prod", "production"}:
        print("skipping schema check (PHZYX_ENV looks like production); use migrate")
        return 0

    plan, code = preview_schema_plan(models=models)
    if code != 0:
        return code
    if plan is None:
        return 2

    from phzyx.engine.tui_push import render_plan_view

    empty = getattr(plan, "empty", True)
    if empty:
        print("schema: up to date (no push needed)")
        return 0

    print(render_plan_view(plan))  # type: ignore[arg-type]
    print(
        "Schema changes are pending. forge start will not apply them "
        "unless you confirm.",
        file=sys.stderr,
    )
    if _prompt_yes_no(
        "Apply schema push now?",
        default=False,
        input_stream=input_stream,
        output_stream=output_stream,
    ):
        return apply_schema_push(models=models)

    if _prompt_yes_no(
        "Start server without applying schema?",
        default=True,
        input_stream=input_stream,
        output_stream=output_stream,
    ):
        print("warning: starting with pending schema changes", file=sys.stderr)
        return 0
    print("aborted (fix schema first: forge db push)", file=sys.stderr)
    return 1


def maybe_handle_migrations(
    *,
    check_migrate: bool,
    migrate_dir: str = DEFAULT_MIGRATE_DIR,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    """If versioned migrations pending, prompt — never auto-apply."""
    if not check_migrate:
        return 0
    pending, code = check_pending_migrations(migrate_dir=migrate_dir)
    if code != 0:
        return code
    if not pending:
        return 0

    print(f"migrations pending ({len(pending)}):")
    for v in pending[:20]:
        print(f"  - {v}")
    if len(pending) > 20:
        print(f"  … and {len(pending) - 20} more")
    print(
        "forge start will not apply migrations unless you confirm.",
        file=sys.stderr,
    )
    if _prompt_yes_no(
        "Apply pending migrations now?",
        default=False,
        input_stream=input_stream,
        output_stream=output_stream,
    ):
        return apply_pending_migrations(migrate_dir=migrate_dir)

    if _prompt_yes_no(
        "Start server without applying migrations?",
        default=True,
        input_stream=input_stream,
        output_stream=output_stream,
    ):
        print("warning: starting with pending migrations", file=sys.stderr)
        return 0
    print("aborted (run: forge migrate apply)", file=sys.stderr)
    return 1


def start_app(
    *,
    root: Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    app: str = DEFAULT_APP,
    models: str = DEFAULT_MODELS,
    reload: bool = True,
    check_schema: bool = True,
    check_migrate: bool = True,
    migrate_dir: str = DEFAULT_MIGRATE_DIR,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    """Ensure env, optional *prompted* schema/migrate, then uvicorn.

    Never auto-applies schema or migrations without confirmation.
    """
    root = (root or Path.cwd()).resolve()
    os.chdir(root)

    created = ensure_dotenv(root)
    if created:
        print(f"created {root / '.env'} from .env.example")
    load_dotenv(root)

    code = maybe_handle_schema(
        models=models,
        check_schema=check_schema,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    if code != 0:
        return code

    code = maybe_handle_migrations(
        check_migrate=check_migrate,
        migrate_dir=migrate_dir,
        input_stream=input_stream,
        output_stream=output_stream,
    )
    if code != 0:
        return code

    base = f"http://{host}:{port}"
    print(f"→ {base}  /docs  /admin/")
    print(
        f"   uvicorn {app} --host {host} --port {port}"
        + (" --reload" if reload else "")
    )

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        app,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(
            "error: uvicorn not found — run inside project after `uv sync`",
            file=sys.stderr,
        )
        return 2


def write_env_if_missing(root: Path) -> Path | None:
    """Used by ``forge new``: materialize .env next to .env.example."""
    if ensure_dotenv(root):
        return root / ".env"
    return None
