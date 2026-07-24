"""``phzyx add admin`` — scaffold AdminBoard wiring into an existing project."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.new import ADMIN_MODULE, ADMIN_README


def add_admin(
    target: Path,
    *,
    module_name: str = "admin_board.py",
    force: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Write AdminBoard scaffold under ``target``. Returns written paths."""
    target = target.resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"not a directory: {target}")

    admin_py = target / module_name
    readme = target / "ADMIN.md"
    written: list[Path] = []

    for path, content in ((admin_py, ADMIN_MODULE), (readme, ADMIN_README)):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite {path} (use --force)")
        if dry_run:
            written.append(path)
            continue
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
