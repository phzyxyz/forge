"""Forge project scaffold — shared by ``phzyx new`` and ``phzyx forge init``."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.scaffold.detect import detect
from phzyx.cli.scaffold.plan import build_plan, validate_name
from phzyx.cli.scaffold.prompts import is_interactive, prompt_existing_non_empty
from phzyx.cli.scaffold.types import (
    DetectResult,
    ForgePlan,
    ScaffoldMode,
    ScaffoldOptions,
)
from phzyx.cli.scaffold.write import ScaffoldError, apply_plan

__all__ = [
    "DetectResult",
    "ForgePlan",
    "ScaffoldError",
    "ScaffoldMode",
    "ScaffoldOptions",
    "apply_plan",
    "build_and_apply",
    "build_plan",
    "detect",
    "validate_name",
]


def build_and_apply(
    root: Path,
    options: ScaffoldOptions,
) -> tuple[ForgePlan, list[Path]]:
    """Detect, plan, confirm, and apply scaffold.

    Raises
    ------
    ValueError
        Invalid name / preset / layout.
    ScaffoldError
        Policy refusal or I/O failure.
    FileExistsError
        Already initialized without force.
    """
    root = root.resolve()
    options.name = validate_name(options.name)

    if root.exists() and root.is_file():
        raise ScaffoldError(f"path is a file, not a directory: {root}")

    det = detect(root, module_root=options.module_root)

    # Policy: already init
    if det.mode is ScaffoldMode.ALREADY_INIT and not options.force:
        raise FileExistsError(
            f"forge already initialized at {root / options.module_root / 'forge'} "
            "(use --force to overwrite scaffold-owned files)"
        )

    # Non-empty existing without yes/force may need prompt
    if (
        det.mode in {ScaffoldMode.EXISTING_ISLAND, ScaffoldMode.REPAIR}
        and not options.yes
        and not options.force
        and not options.dry_run
    ):
        if options.no_input or not is_interactive():
            raise ScaffoldError(
                f"directory is not empty ({root}); pass --yes for island mode, "
                "--force to overwrite, or run interactively"
            )
        choice = prompt_existing_non_empty()
        if choice == "abort":
            raise ScaffoldError("aborted by user")
        if choice == "force":
            options.force = True
        # island: default skip_main
        options.skip_main = True

    if det.mode is ScaffoldMode.EXISTING_ISLAND and options.yes and not options.force:
        options.skip_main = True
        if det.has_pyproject:
            options.skip_pyproject = True

    plan = build_plan(det, options)
    paths = apply_plan(plan)
    return plan, paths
