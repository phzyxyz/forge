"""``phzyx new`` — create a project directory and run forge scaffold."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.scaffold import (
    ScaffoldError,
    ScaffoldOptions,
    build_and_apply,
    validate_name,
)
from phzyx.cli.scaffold.detect import is_effectively_empty
from phzyx.cli.scaffold.templates import admin_md

ADMIN_README = admin_md()

# Standalone mount helper for ``phzyx add admin`` (legacy module path).
ADMIN_MODULE = '''\
# GENERATED-BY: phzyx-forge-scaffold v1
"""AdminBoard wiring — prefer app/forge/admin.py from phzyx forge init."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from phzyx.admin.fastapi import AdminBoard
from phzyx.orm import Session

SessionFactory = Callable[[], Session]


def mount_admin(
    app: Any,
    *,
    models: Sequence[type],
    session_factory: SessionFactory,
    theme: str = "stellar-dark",
    storage_root: Path | None = None,
    authz: Any = None,
    prefix: str = "/admin",
) -> AdminBoard:
    """Mount AdminBoard on a FastAPI app."""
    return AdminBoard(
        app,
        models=list(models),
        session_factory=session_factory,
        theme=theme,
        storage_root=storage_root,
        authz=authz,
        prefix=prefix,
    )
'''


def new_project(
    name: str,
    *,
    preset: str = "max",
    layout: str = "forge",
    parent: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    no_input: bool = False,
    db: str = "sqlite",
    auth: bool | None = None,
    admin: bool | None = None,
    docker: bool | None = None,
) -> list[Path]:
    """Create ``parent/name`` and scaffold a Forge app."""
    name = validate_name(name)
    parent = (parent or Path.cwd()).resolve()
    root = parent / name

    if root.exists() and not is_effectively_empty(root) and not force and not yes:
        raise FileExistsError(
            f"refusing to write into non-empty {root} "
            "(use --force, or phzyx forge init inside the directory)"
        )

    opts = ScaffoldOptions(
        name=name,
        preset=preset,
        layout=layout,
        db=db,  # type: ignore[arg-type]
        auth=auth,
        admin=admin,
        docker=docker,
        force=force or yes,
        yes=yes or force,
        no_input=no_input,
        dry_run=dry_run,
        skip_pyproject=False,
        skip_main=False,
        patch_main=False,
    )
    # For new projects always fresh semantics
    if not root.exists() and not dry_run:
        root.mkdir(parents=True, exist_ok=True)

    try:
        _plan, paths = build_and_apply(root, opts)
    except ScaffoldError:
        raise
    # First-run default: materialize .env so `forge start` needs no manual cp
    if not dry_run and (yes or force or no_input):
        from phzyx.cli.start import write_env_if_missing

        env_path = write_env_if_missing(root)
        if env_path is not None:
            paths = [*paths, env_path]
    return paths
