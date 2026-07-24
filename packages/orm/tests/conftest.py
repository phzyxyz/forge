"""ORM test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from phzyx.schema import get_registry


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    reg = get_registry()
    reg.clear()
    yield
    reg.clear()
