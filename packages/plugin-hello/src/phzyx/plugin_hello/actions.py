"""Example AdminAction factory for entry points."""

from __future__ import annotations

from typing import Any


def hello_ping_action() -> dict[str, Any]:
    """Return an action descriptor compatible with AdminBoard action catalogs."""
    return {
        "name": "hello_ping",
        "label": "Ping (plugin)",
        "scope": "global",
        "confirm": False,
        "plugin": "phzyx-plugin-hello",
    }
