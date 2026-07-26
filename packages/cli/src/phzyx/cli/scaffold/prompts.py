"""Interactive prompts for forge init (TTY only)."""

from __future__ import annotations

import sys
from typing import Literal

ExistingChoice = Literal["island", "abort", "force"]


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_existing_non_empty() -> ExistingChoice:
    """Ask how to treat a non-empty project directory."""
    print("This directory is not empty.")
    print("  [1] Add forge island only (recommended)")
    print("  [2] Abort")
    print("  [3] Force overwrite scaffold-owned files")
    raw = input("Choice [1/2/3]: ").strip() or "1"
    if raw in {"1", "island", "i"}:
        return "island"
    if raw in {"2", "abort", "a", "q"}:
        return "abort"
    if raw in {"3", "force", "f"}:
        return "force"
    print("Invalid choice — aborting.")
    return "abort"


def prompt_yes_no(question: str, *, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    raw = input(question + suffix).strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "1", "true"}
