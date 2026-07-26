"""Shared types for the Forge project scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal


class ScaffoldMode(StrEnum):
    """How the target directory should be treated."""

    FRESH = "fresh"
    EXISTING_ISLAND = "existing-island"
    ALREADY_INIT = "already-init"
    REPAIR = "repair"


class FileMode(StrEnum):
    CREATE = "create"
    OVERWRITE = "overwrite"
    SKIP_IF_EXISTS = "skip_if_exists"


@dataclass(slots=True)
class FileOp:
    """One planned filesystem write."""

    rel_path: str
    content: str
    mode: FileMode = FileMode.CREATE
    owned: bool = True  # scaffold-owned (force may overwrite)


@dataclass(slots=True)
class DetectResult:
    root: Path
    mode: ScaffoldMode
    is_empty: bool
    has_app: bool
    has_forge: bool
    has_main: bool
    has_api: bool
    has_pyproject: bool
    non_ignorable: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScaffoldOptions:
    name: str
    preset: str = "max"
    layout: str = "forge"
    db: Literal["sqlite", "postgres"] = "sqlite"
    auth: bool | None = None  # None → from preset
    admin: bool | None = None
    docker: bool | None = None
    force: bool = False
    yes: bool = False
    no_input: bool = False
    dry_run: bool = False
    skip_pyproject: bool = False
    skip_main: bool = False
    patch_main: bool = False
    module_root: str = "app"


@dataclass(slots=True)
class ForgePlan:
    root: Path
    mode: ScaffoldMode
    options: ScaffoldOptions
    ops: list[FileOp] = field(default_factory=list)
    post_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    layout_warning: str | None = None
