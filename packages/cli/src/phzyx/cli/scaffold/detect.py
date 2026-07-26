"""Target directory detection for forge init / new."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.scaffold.types import DetectResult, ScaffoldMode

# Entries that do not force "existing project" mode.
IGNORABLE_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        ".DS_Store",
        "node_modules",
        ".coverage",
        "htmlcov",
        ".tox",
        ".nox",
        "dist",
        "build",
        ".phzyx-scaffold-tmp",
    }
)

# Alone (with ignorables) still allow full fresh scaffold.
EMPTY_ISH_FILES = frozenset(
    {
        "README.md",
        "readme.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        ".gitignore",
    }
)

MARKER_NAME = ".phzyx-forge"
GENERATED_MARKER = "GENERATED-BY: phzyx-forge-scaffold"


def is_ignorable_name(name: str) -> bool:
    if name in IGNORABLE_NAMES:
        return True
    if name.endswith(".egg-info"):
        return True
    return name.endswith(".pyc")


def list_non_ignorable(root: Path) -> list[str]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    out: list[str] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if is_ignorable_name(child.name):
            continue
        out.append(child.name)
    return out


def is_effectively_empty(root: Path) -> bool:
    """True if missing, empty, or only ignorable / empty-ish files."""
    if not root.exists():
        return True
    names = list_non_ignorable(root)
    if not names:
        return True
    return all(n in EMPTY_ISH_FILES for n in names)


def _has_mount_forge(forge_init: Path) -> bool:
    if not forge_init.is_file():
        return False
    text = forge_init.read_text(encoding="utf-8", errors="replace")
    return "def mount_forge" in text or "mount_forge" in text


def detect(root: Path, *, module_root: str = "app") -> DetectResult:
    """Classify ``root`` for scaffolding."""
    root = root.resolve()
    warnings: list[str] = []

    if root.exists() and root.is_file():
        raise NotADirectoryError(f"path is a file, not a directory: {root}")

    non = list_non_ignorable(root) if root.exists() else []
    empty = is_effectively_empty(root)

    app = root / module_root
    forge = app / "forge"
    has_app = app.is_dir()
    has_forge = forge.is_dir()
    has_main = (app / "main.py").is_file() or (root / "main.py").is_file()
    has_api = (app / "api").is_dir()
    has_pyproject = (root / "pyproject.toml").is_file()
    marker = forge / MARKER_NAME
    forge_init = forge / "__init__.py"
    complete = has_forge and (marker.is_file() or _has_mount_forge(forge_init))

    if empty:
        mode = ScaffoldMode.FRESH
    elif complete and not any(
        # repair if core files missing
        not (forge / name).is_file()
        for name in ("db.py", "models.py", "registry.py")
    ):
        mode = ScaffoldMode.ALREADY_INIT
    elif has_forge and not complete:
        mode = ScaffoldMode.REPAIR
        warnings.append("partial forge/ island detected — will fill missing files")
    else:
        mode = ScaffoldMode.EXISTING_ISLAND

    return DetectResult(
        root=root,
        mode=mode,
        is_empty=empty,
        has_app=has_app,
        has_forge=has_forge,
        has_main=has_main,
        has_api=has_api,
        has_pyproject=has_pyproject,
        non_ignorable=non,
        warnings=warnings,
    )
