"""Smoke tests for phzyx-admin-fastapi package layout."""

from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.unit
def test_admin_fastapi_version_string() -> None:
    # importlib avoids static resolution issues with split phzyx.admin wheels
    admin_fastapi = import_module("phzyx.admin.fastapi")
    version = getattr(admin_fastapi, "__version__", None)
    assert isinstance(version, str)
    assert version
