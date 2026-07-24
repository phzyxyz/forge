"""Shared fixtures for AdminBoard live demo tests (phzyx-auth cookie sessions)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# demo main.py does `from seed_rich import …` — put that directory on path for importlib loads
_DEMO_DIR = Path(__file__).resolve().parents[2] / "examples" / "adminboard_live"
if str(_DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(_DEMO_DIR))


def _login(
    client: Any,
    *,
    email: str = "admin",
    password: str = "phzyx",
) -> dict[str, str]:
    """POST /auth/login; return CSRF header (cookies stay on client)."""
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    csrf = r.json().get("csrf_token") or ""
    headers: dict[str, str] = {}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return headers


@pytest.fixture
def auth(client: Any) -> dict[str, str]:
    """Authenticated session headers for the demo TestClient."""
    return _login(client)
