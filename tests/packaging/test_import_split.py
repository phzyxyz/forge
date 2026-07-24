"""Packaging smoke: namespace leaves import without a root phzyx package module."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest


@pytest.mark.packaging
def test_import_core_leaves() -> None:
    for name in (
        "phzyx.schema",
        "phzyx.engine",
        "phzyx.orm",
        "phzyx.admin",
        "phzyx.admin.fastapi",
        "phzyx.cli",
    ):
        mod = import_module(name)
        assert hasattr(mod, "__version__")


@pytest.mark.packaging
def test_no_namespace_root_init_in_schema_tree() -> None:
    """Schema leaf must not rely on packages/schema/src/phzyx/__init__.py."""
    schema = import_module("phzyx.schema")
    schema_file = schema.__file__
    assert schema_file is not None
    leaf_dir = Path(schema_file).resolve().parent
    namespace_root = leaf_dir.parent  # .../phzyx
    assert namespace_root.name == "phzyx"
    assert not (namespace_root / "__init__.py").exists()


@pytest.mark.packaging
def test_admin_extend_path_allows_fastapi_subpackage() -> None:
    """phzyx.admin uses extend_path so admin-fastapi can ship under the same parent."""
    admin = import_module("phzyx.admin")
    fastapi_mod = import_module("phzyx.admin.fastapi")
    assert fastapi_mod.__name__ == "phzyx.admin.fastapi"
    assert any("admin" in str(p) for p in admin.__path__)
