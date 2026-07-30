"""``phzyx start`` — local defaults: .env, db push, uvicorn on port 9898."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9898
DEFAULT_APP = "app.main:app"
DEFAULT_MODELS = "app.forge.registry:ALL_MODELS"


def ensure_dotenv(root: Path) -> bool:
    """Copy .env.example → .env if missing. Returns True if created."""
    env = root / ".env"
    example = root / ".env.example"
    if env.is_file() or not example.is_file():
        return False
    text = example.read_text(encoding="utf-8")
    if "PHZYX_AUTH_SECRET=" in text and "token_urlsafe" not in text:
        # Inject a local-only secret if placeholder is empty/short
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


def run_db_push(*, models: str, yes: bool = True) -> int:
    """Run schema push without re-entering argparse."""
    from phzyx.engine import connect, load_config, push_schema

    from phzyx.cli import _load_models

    cfg = load_config()
    url = cfg.database_url or os.environ.get("PHZYX_DATABASE_URL")
    if not url:
        print(
            "error: set PHZYX_DATABASE_URL (or use scaffold .env)",
            file=sys.stderr,
        )
        return 2
    model_list = _load_models(models or cfg.models)
    if not model_list:
        print(f"error: could not load models {models!r}", file=sys.stderr)
        return 2
    conn, adapter = connect(url)
    try:
        result = push_schema(
            model_list,
            conn,
            adapter,
            dry_run=False,
            yes=yes,
            allow_production=False,
        )
        print(result.plan.summary())
        if result.applied:
            print(f"applied {len(result.statements)} statement(s)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: db push failed: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


def start_app(
    *,
    root: Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    app: str = DEFAULT_APP,
    models: str = DEFAULT_MODELS,
    reload: bool = True,
    push: bool = True,
) -> int:
    """Ensure env, optional push, then exec uvicorn. Returns process exit code."""
    root = (root or Path.cwd()).resolve()
    os.chdir(root)

    created = ensure_dotenv(root)
    if created:
        print(f"created {root / '.env'} from .env.example")
    load_dotenv(root)

    env = (os.environ.get("PHZYX_ENV") or "development").lower()
    is_prod = env in {"prod", "production"}
    if push and not is_prod:
        print(f"db push ({models}) …")
        code = run_db_push(models=models, yes=True)
        if code not in (0,):
            # still allow start if push blocked; print and continue only for empty models?
            if code != 0:
                print(
                    "warning: db push failed — fix models/DB then re-run, "
                    "or: phzyx start --no-push",
                    file=sys.stderr,
                )
                # For brand-new sqlite this should work; fail hard so user notices
                return code
    elif push and is_prod:
        print("skipping push (PHZYX_ENV looks like production); use migrate")

    base = f"http://{host}:{port}"
    print(f"→ {base}  /docs  /admin/")
    print(f"   uvicorn {app} --host {host} --port {port}" + (" --reload" if reload else ""))

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
    """Used by ``phzyx new``: materialize .env next to .env.example."""
    if ensure_dotenv(root):
        return root / ".env"
    return None
