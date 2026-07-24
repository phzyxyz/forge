"""DSN parse + capabilities (SS2.1 / SS2.5)."""

from __future__ import annotations

import pytest
from phzyx.engine import (
    CAP_COMPOSITE_PK,
    CAP_JSON_TYPE,
    capabilities_for,
    parse_database_url,
    parse_version,
)
from phzyx.engine.capabilities import CAP_JSONB, CAP_RETURNING, CAP_UUID
from phzyx.engine.normalize import normalize_sql_type
from phzyx.schema.types import Dialect, LogicalType


@pytest.mark.unit
def test_parse_sqlite_urls() -> None:
    u = parse_database_url("sqlite:///:memory:")
    assert u.dialect is Dialect.SQLITE
    assert u.path == ":memory:"
    u2 = parse_database_url("sqlite:///tmp_test.db")
    assert u2.path == "tmp_test.db"


@pytest.mark.unit
def test_parse_postgres_url() -> None:
    u = parse_database_url("postgresql://user:pass@localhost:5432/app")
    assert u.dialect is Dialect.POSTGRES
    assert u.user == "user"
    assert u.database == "app"
    assert u.port == 5432


@pytest.mark.unit
def test_parse_mysql_urls() -> None:
    u = parse_database_url("mysql://root:secret@127.0.0.1:3306/app")
    assert u.dialect is Dialect.MYSQL
    assert u.user == "root"
    assert u.password == "secret"
    assert u.host == "127.0.0.1"
    assert u.port == 3306
    assert u.database == "app"

    u2 = parse_database_url("mysql+pymysql://user@localhost/db")
    assert u2.dialect is Dialect.MYSQL
    assert u2.user == "user"
    assert u2.port == 3306
    assert u2.database == "db"


@pytest.mark.unit
def test_parse_mariadb_alias_to_mysql() -> None:
    """MariaDB schemes map to Dialect.MYSQL until a dedicated dialect exists."""
    u = parse_database_url("mariadb://u:p@db.example:3307/prod")
    assert u.dialect is Dialect.MYSQL
    assert u.port == 3307
    assert u.database == "prod"
    u2 = parse_database_url("mariadb+pymysql://u@localhost/x")
    assert u2.dialect is Dialect.MYSQL


@pytest.mark.unit
def test_sqlite_capabilities_include_composite_pk() -> None:
    v = parse_version("3.45.1")
    caps = capabilities_for(Dialect.SQLITE, v)
    assert caps.supports(CAP_COMPOSITE_PK)


@pytest.mark.unit
def test_mysql_capabilities_baseline() -> None:
    v = parse_version("8.4.0")
    caps = capabilities_for(Dialect.MYSQL, v)
    assert caps.supports(CAP_COMPOSITE_PK)
    assert caps.supports(CAP_JSON_TYPE)
    assert caps.supports(CAP_UUID)
    assert not caps.supports(CAP_JSONB)
    assert not caps.supports(CAP_RETURNING)


@pytest.mark.unit
def test_normalize_mysql_types() -> None:
    assert normalize_sql_type("bigint", dialect="mysql") is LogicalType.INT
    assert normalize_sql_type("json", dialect="mysql") is LogicalType.JSON
    assert normalize_sql_type("datetime", dialect="mysql") is LogicalType.DATETIME
    assert normalize_sql_type("tinyint(1)", dialect="mysql") is LogicalType.BOOL
    assert normalize_sql_type("tinyint(4)", dialect="mysql") is LogicalType.INT
    assert normalize_sql_type("longtext", dialect="mysql") is LogicalType.STR
    assert normalize_sql_type("mediumblob", dialect="mysql") is LogicalType.BYTES
