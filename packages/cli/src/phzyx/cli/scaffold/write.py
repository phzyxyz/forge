"""Apply a ForgePlan to the filesystem."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.scaffold.types import FileMode, ForgePlan


class ScaffoldError(Exception):
    """User-facing scaffold failure."""


def apply_plan(plan: ForgePlan) -> list[Path]:
    """Write planned files. Returns paths written (or that would be in dry-run)."""
    root = plan.root
    written: list[Path] = []
    dry = plan.options.dry_run
    force = plan.options.force

    if not dry:
        root.mkdir(parents=True, exist_ok=True)

    for op in plan.ops:
        path = root / op.rel_path
        exists = path.exists()

        if exists and op.mode is FileMode.SKIP_IF_EXISTS and not force:
            continue
        if exists and op.mode is FileMode.CREATE and not force:
            # treat as skip for safety in existing mode
            continue
        if exists and op.mode is FileMode.OVERWRITE and not force and not op.owned:
            continue

        written.append(path)
        if dry:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(op.content, encoding="utf-8")
        except OSError as exc:
            raise ScaffoldError(f"failed to write {path}: {exc}") from exc

    return written
