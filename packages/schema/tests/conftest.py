"""Schema package test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from phzyx.schema import get_registry


@pytest.fixture(autouse=True)
def _clean_model_registry() -> Iterator[None]:
    """Isolate registry state across tests (models auto-register on definition)."""
    registry = get_registry()
    registry.clear()
    yield
    registry.clear()
