"""``phzyx forge init`` — scaffold into an existing or empty directory."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.scaffold import ScaffoldOptions, build_and_apply, validate_name


def forge_init(
    path: Path | str = ".",
    *,
    name: str | None = None,
    preset: str = "max",
    layout: str = "forge",
    db: str = "sqlite",
    auth: bool | None = None,
    admin: bool | None = None,
    docker: bool | None = None,
    force: bool = False,
    yes: bool = False,
    no_input: bool = False,
    dry_run: bool = False,
    skip_pyproject: bool = False,
    skip_main: bool = False,
    patch_main: bool = False,
) -> tuple[list[Path], list[str], list[str]]:
    """Initialize forge in ``path``.

    Returns ``(written_paths, post_steps, warnings)``.
    """
    root = Path(path).resolve()
    proj_name = name or root.name or "app"
    if proj_name in {".", "..", ""} or not proj_name[:1].isalpha():
        proj_name = "app"
    try:
        validate_name(proj_name)
    except ValueError:
        proj_name = "app"

    opts = ScaffoldOptions(
        name=proj_name,
        preset=preset,
        layout=layout,
        db=db,  # type: ignore[arg-type]
        auth=auth,
        admin=admin,
        docker=docker,
        force=force,
        yes=yes,
        no_input=no_input,
        dry_run=dry_run,
        skip_pyproject=skip_pyproject,
        skip_main=skip_main,
        patch_main=patch_main,
    )
    plan, paths = build_and_apply(root, opts)
    return paths, plan.post_steps, plan.warnings
