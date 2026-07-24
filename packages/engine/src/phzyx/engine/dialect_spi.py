"""Dialect SPI protocol: version detection, capabilities, introspection."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from phzyx.engine.capabilities import CapabilitySet, Version
from phzyx.schema.manifest import Manifest
from phzyx.schema.types import Dialect


@runtime_checkable
class DialectAdapter(Protocol):
    """Sync dialect adapter used by CLI and push/migrate (Sans-I/O core stays pure)."""

    dialect: Dialect

    def detect_version(self, connection: Any) -> Version:
        """Return server version for capability gating."""
        ...

    def capabilities(self, version: Version) -> CapabilitySet:
        """Capability flags for this version."""
        ...

    def introspect(self, connection: Any) -> Manifest:
        """Read live schema into Manifest IR (tables Phzyx cares about)."""
        ...
