"""Packaging smoke: meta install-all surfaces recommended leaves in one env."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

import pytest


@pytest.mark.packaging
def test_meta_package_distribution_present() -> None:
    """Workspace installs the ecosystem meta distribution named ``phzyx``."""
    try:
        ver = version("phzyx")
    except PackageNotFoundError as exc:  # pragma: no cover - env misconfigured
        raise AssertionError("meta package 'phzyx' is not installed") from exc
    assert ver


@pytest.mark.packaging
def test_forge_meta_package_distribution_present() -> None:
    """Workspace installs the Forge product meta ``phzyx-forge``."""
    try:
        ver = version("phzyx-forge")
    except PackageNotFoundError as exc:  # pragma: no cover - env misconfigured
        raise AssertionError("meta package 'phzyx-forge' is not installed") from exc
    assert ver


@pytest.mark.packaging
def test_meta_env_imports_recommended_set() -> None:
    """After install-all, Forge product leaves import successfully."""
    for name in (
        "phzyx.schema",
        "phzyx.engine",
        "phzyx.orm",
        "phzyx.admin",
        "phzyx.admin.fastapi",
        "phzyx.cli",
    ):
        import_module(name)


@pytest.mark.packaging
def test_cli_console_script_callable() -> None:
    from phzyx.cli import main

    assert callable(main)
    assert main([]) == 0
