"""Example widget descriptor (entry point target)."""

from __future__ import annotations


class HelloBadgeWidget:
    """Minimal widget SPI example — not a React component, a server descriptor."""

    name = "hello_badge"
    label = "Hello badge"
    widget = "text"

    def serialize(self, value: object) -> str:
        return f"👋 {value}"
