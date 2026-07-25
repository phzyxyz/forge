"""Unit coverage for MSSQL dialect pieces without a live server."""

from __future__ import annotations

from phzyx.engine.capabilities import CAP_COMPOSITE_PK, capabilities_for, parse_version
from phzyx.engine.dsn import parse_database_url
from phzyx.orm import Field, Model
from phzyx.schema.ddl import mysql_timestamp_expr, quote_ident, render_manifest_ddl
from phzyx.schema.manifest import build_manifest
from phzyx.schema.types import Dialect


class _T(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    name: str = Field()

    class Meta:
        table = "t_mssql_unit"
        register = False


def test_parse_mssql_url() -> None:
    db = parse_database_url("mssql://sa:p%40ss@127.0.0.1:1422/phzyx")
    assert db.dialect is Dialect.MSSQL
    assert db.host == "127.0.0.1"
    assert db.port == 1422
    assert db.database == "phzyx"
    assert db.user == "sa"


def test_parse_sqlserver_alias() -> None:
    db = parse_database_url("sqlserver://u:p@localhost/db")
    assert db.dialect is Dialect.MSSQL
    assert db.port == 1433


def test_mssql_capabilities() -> None:
    ver = parse_version("Microsoft SQL Server 2022 (RTM)")
    caps = capabilities_for(Dialect.MSSQL, ver)
    assert caps.supports(CAP_COMPOSITE_PK)


def test_mssql_ddl_identity_and_brackets() -> None:
    m = build_manifest([_T])
    stmts = render_manifest_ddl(m, Dialect.MSSQL)
    create = stmts[0]
    assert "[t_mssql_unit]" in create
    assert "IDENTITY(1,1)" in create
    assert "NVARCHAR(255)" in create  # unique email not MAX
    assert quote_ident("foo", Dialect.MSSQL) == "[foo]"


def test_mysql_timestamp_expr_precision() -> None:
    assert (
        mysql_timestamp_expr("CURRENT_TIMESTAMP", "DATETIME(6)", Dialect.MYSQL)
        == "CURRENT_TIMESTAMP(6)"
    )
    assert (
        mysql_timestamp_expr("CURRENT_TIMESTAMP", "DATETIME(6)", Dialect.MSSQL)
        == "CURRENT_TIMESTAMP"
    )


def test_unique_checks_empty_data() -> None:
    from phzyx.admin.unique_checks import unique_field_errors

    errs = unique_field_errors(
        _T,
        {},
        query=lambda _w: [],
    )
    assert errs == {}


def test_normalize_mssql_types() -> None:
    from phzyx.engine.normalize import normalize_sql_type
    from phzyx.schema.types import LogicalType

    assert normalize_sql_type("uniqueidentifier", dialect="mssql") is LogicalType.UUID
    assert normalize_sql_type("bit", dialect="mssql") is LogicalType.BOOL
    assert normalize_sql_type("datetime2", dialect="mssql") is LogicalType.DATETIME
