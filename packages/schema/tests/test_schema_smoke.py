"""Smoke tests for phzyx-schema package layout."""

from __future__ import annotations

import phzyx.schema as schema
import pytest


@pytest.mark.unit
def test_schema_version_string() -> None:
    assert isinstance(schema.__version__, str)
    assert schema.__version__
