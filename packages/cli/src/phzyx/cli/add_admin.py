"""``phzyx add admin`` — scaffold AdminBoard wiring into an existing project."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.new import ADMIN_MODULE, ADMIN_README


def add_admin(
    target: Path,
    *,
    module_name: str = "app/forge/admin.py",
    force: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Write AdminBoard scaffold under ``target``. Returns written paths."""
    target = target.resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"not a directory: {target}")

    admin_py = target / module_name
    # README next to module or project root
    readme = target / "ADMIN.md"
    written: list[Path] = []

    # Prefer full forge admin template when writing into app/forge/
    content = ADMIN_MODULE
    if module_name.replace("\\", "/").endswith("forge/admin.py"):
        from phzyx.cli.scaffold.templates import forge_admin

        content = forge_admin(auth=False)

    for path, body in ((admin_py, content), (readme, ADMIN_README)):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite {path} (use --force)")
        if dry_run:
            written.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written
