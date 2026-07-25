"""Dialect capability registry (version-aware feature flags)."""

from __future__ import annotations

import re
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from phzyx.schema.types import Dialect


@dataclass(frozen=True, slots=True)
class Version:
    """Parsed server version (major.minor.patch)."""

    major: int
    minor: int = 0
    patch: int = 0
    raw: str = ""

    def at_least(self, major: int, minor: int = 0, patch: int = 0) -> bool:
        return (self.major, self.minor, self.patch) >= (major, minor, patch)

    def __str__(self) -> str:
        return self.raw or f"{self.major}.{self.minor}.{self.patch}"


# Seed capability names (plan/09 + M2).
CAP_COMPOSITE_PK = "composite_pk"
CAP_JSON_TYPE = "json_type"
CAP_JSONB = "jsonb"
CAP_UUID = "uuid"
CAP_RETURNING = "returning"
CAP_TRANSACTIONAL_DDL = "transactional_ddl"
CAP_SCHEMAS = "schemas"


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    dialect: Dialect
    version: Version
    features: frozenset[str]

    def supports(self, feature: str) -> bool:
        return feature in self.features

    def require(self, feature: str) -> None:
        if not self.supports(feature):
            raise ValueError(f"{self.dialect.value} {self.version} does not support {feature!r}")


def capabilities_for(dialect: Dialect | str, version: Version) -> CapabilitySet:
    """Return the capability set for a dialect version."""
    d = Dialect(dialect) if not isinstance(dialect, Dialect) else dialect
    if d is Dialect.SQLITE:
        features = frozenset(
            {
                CAP_COMPOSITE_PK,
                CAP_JSON_TYPE,  # stored as TEXT
                CAP_UUID,  # TEXT
                CAP_RETURNING,  # 3.35+
                CAP_TRANSACTIONAL_DDL,
            }
        )
        # RETURNING only if version high enough when we know it.
        if version.raw and not version.at_least(3, 35):
            features = features - {CAP_RETURNING}
        return CapabilitySet(dialect=d, version=version, features=features)

    if d is Dialect.POSTGRES:
        features = {
            CAP_COMPOSITE_PK,
            CAP_JSON_TYPE,
            CAP_JSONB,
            CAP_UUID,
            CAP_RETURNING,
            CAP_TRANSACTIONAL_DDL,
            CAP_SCHEMAS,
        }
        return CapabilitySet(dialect=d, version=version, features=frozenset(features))

    if d is Dialect.MYSQL:
        # MySQL 8+ baseline (MariaDB DSN aliases share this set for now).
        # No native UUID / JSONB / full RETURNING / transactional DDL.
        features = {
            CAP_COMPOSITE_PK,
            CAP_JSON_TYPE,  # JSON type 5.7+/8.0+
            CAP_UUID,  # CHAR(36) storage
            CAP_SCHEMAS,  # database-as-schema
        }
        return CapabilitySet(dialect=d, version=version, features=frozenset(features))

    if d is Dialect.MSSQL:
        # SQL Server 2017+ baseline used by the local matrix.
        features = {
            CAP_COMPOSITE_PK,
            CAP_JSON_TYPE,  # NVARCHAR(MAX) JSON text
            CAP_UUID,  # UNIQUEIDENTIFIER
            CAP_SCHEMAS,  # dbo etc.
            CAP_TRANSACTIONAL_DDL,  # most DDL in transactions
        }
        return CapabilitySet(dialect=d, version=version, features=frozenset(features))

    return CapabilitySet(dialect=d, version=version, features=frozenset())


def parse_version(raw: str, *, dialect: Dialect | str | None = None) -> Version:
    """Best-effort parse of version strings from SQLite/Postgres."""
    text = raw.strip()
    # Postgres: "PostgreSQL 16.2 on ..."
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return Version(0, 0, 0, raw=text)
    return Version(
        major=int(m.group(1)),
        minor=int(m.group(2)),
        patch=int(m.group(3) or 0),
        raw=text,
    )


def all_capability_names() -> AbstractSet[str]:
    return frozenset(
        {
            CAP_COMPOSITE_PK,
            CAP_JSON_TYPE,
            CAP_JSONB,
            CAP_UUID,
            CAP_RETURNING,
            CAP_TRANSACTIONAL_DDL,
            CAP_SCHEMAS,
        }
    )
