"""Smoke tests for phzyx-engine package layout."""

from __future__ import annotations

import phzyx.engine as engine
import pytest


@pytest.mark.unit
def test_engine_version_string() -> None:
    assert isinstance(engine.__version__, str)
    assert engine.__version__
