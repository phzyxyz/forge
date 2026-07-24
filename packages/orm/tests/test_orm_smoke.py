"""Smoke tests for phzyx-orm package layout."""

from __future__ import annotations

import phzyx.orm as orm
import pytest


@pytest.mark.unit
def test_orm_version_string() -> None:
    assert isinstance(orm.__version__, str)
    assert orm.__version__
