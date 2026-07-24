"""Smoke tests for the hello FastAPI example."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HELLO_DIR = Path(__file__).resolve().parents[1]
if str(HELLO_DIR) not in sys.path:
    sys.path.insert(0, str(HELLO_DIR))

from main import app  # noqa: E402


@pytest.mark.unit
def test_app_title() -> None:
    assert app.title == "Phzyx hello"


@pytest.mark.unit
def test_routes_registered() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/" in paths
    assert "/health" in paths
