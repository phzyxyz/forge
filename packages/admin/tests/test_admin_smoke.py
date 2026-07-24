"""Smoke tests for phzyx-admin package layout."""

from __future__ import annotations

import phzyx.admin as admin
import pytest


@pytest.mark.unit
def test_admin_version_string() -> None:
    assert isinstance(admin.__version__, str)
    assert admin.__version__
