"""ORM structured errors."""

from __future__ import annotations


class OrmError(Exception):
    """Base ORM error."""


class ConflictError(OrmError):
    """Optimistic concurrency conflict (stale version)."""

    def __init__(self, message: str = "concurrent update conflict") -> None:
        super().__init__(message)
        self.message = message
