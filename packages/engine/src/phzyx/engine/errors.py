"""Schema engine errors."""

from __future__ import annotations


class EngineError(Exception):
    """Base error for phzyx-engine."""


class PolicyError(EngineError):
    """Operation refused by SchemaPolicy."""


class ConnectionError(EngineError):
    """DSN / driver / connection failure."""


class MigrationError(EngineError):
    """Migration history or apply failure."""
