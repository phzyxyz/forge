"""Type mapping and CREATE DDL emit (SS1.3–1.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from phzyx.schema import (
    SQLITE_LIMITS,
    Dialect,
    Field,
    LogicalType,
    Model,
    OnDelete,
    apply_manifest_sqlite,
    build_manifest,
    infer_logical_type,
    physical_type,
    render_create_table,
    render_manifest_ddl,
)


@pytest.mark.unit
def test_infer_logical_types() -> None:
    assert infer_logical_type(str) is LogicalType.STR
    assert infer_logical_type(int) is LogicalType.INT
    assert infer_logical_type(float) is LogicalType.FLOAT
    assert infer_logical_type(bool) is LogicalType.BOOL
    assert infer_logical_type(bytes) is LogicalType.BYTES
    assert infer_logical_type(datetime) is LogicalType.DATETIME
    assert infer_logical_type(UUID) is LogicalType.UUID
    assert infer_logical_type(Decimal) is LogicalType.DECIMAL
    assert infer_logical_type(dict) is LogicalType.JSON


@pytest.mark.unit
def test_physical_mapping_and_db_type_override() -> None:
    assert physical_type(LogicalType.INT, Dialect.POSTGRES) == "BIGINT"
    assert physical_type(LogicalType.INT, Dialect.SQLITE) == "INTEGER"
    assert physical_type(LogicalType.JSON, Dialect.POSTGRES) == "JSONB"
    assert physical_type(LogicalType.STR, Dialect.POSTGRES, db_type="VARCHAR(64)") == "VARCHAR(64)"
    assert "SQLite" in SQLITE_LIMITS
    assert physical_type(LogicalType.INT, Dialect.MYSQL) == "BIGINT"
    assert physical_type(LogicalType.JSON, Dialect.MYSQL) == "JSON"
    assert physical_type(LogicalType.BOOL, Dialect.MYSQL) == "TINYINT(1)"
    assert physical_type(LogicalType.UUID, Dialect.MYSQL) == "CHAR(36)"


@pytest.mark.unit
def test_quote_ident_mysql_backticks() -> None:
    from phzyx.schema.ddl import quote_ident

    assert quote_ident("users", Dialect.MYSQL) == "`users`"
    assert quote_ident("users", Dialect.POSTGRES) == '"users"'
    assert quote_ident("users", Dialect.SQLITE) == '"users"'


@pytest.mark.unit
def test_create_table_single_pk_postgres_golden() -> None:
    class User(Model):
        id: int = Field(primary_key=True)
        email: str = Field(unique=True)
        bio: str | None = Field(default=None)

        class Meta:
            table = "users"
            register = False

    m = build_manifest([User])
    sql = render_create_table(m.table("users"), Dialect.POSTGRES)
    golden = Path(__file__).parent / "goldens" / "create_users_postgres.sql"
    if not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(sql + "\n")
    assert sql + "\n" == golden.read_text()


@pytest.mark.unit
def test_create_table_composite_pk_sqlite_golden() -> None:
    class Membership(Model):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True)
        role: str = Field(index=True)

        class Meta:
            table = "memberships"
            register = False

    m = build_manifest([Membership])
    sql = render_create_table(m.table("memberships"), Dialect.SQLITE)
    assert 'PRIMARY KEY ("org_id", "user_id")' in sql
    golden = Path(__file__).parent / "goldens" / "create_memberships_sqlite.sql"
    if not golden.exists():
        golden.write_text(sql + "\n")
    assert sql + "\n" == golden.read_text()


@pytest.mark.unit
def test_fk_and_index_emit() -> None:
    class Org(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "orgs"
            register = False

    class Member(Model):
        id: int = Field(primary_key=True)
        org_id: int = Field(foreign_key="orgs.id", on_delete=OnDelete.CASCADE)
        code: str = Field(unique=True)

        class Meta:
            table = "members"
            register = False

    m = build_manifest([Org, Member])
    stmts = render_manifest_ddl(m, Dialect.SQLITE)
    joined = "\n".join(stmts)
    assert "FOREIGN KEY" in joined
    assert "REFERENCES" in joined
    assert "CREATE UNIQUE INDEX" in joined


@pytest.mark.unit
@pytest.mark.sqlite
def test_apply_manifest_sqlite_roundtrip() -> None:
    class Widget(Model):
        id: int = Field(primary_key=True)
        name: str = Field()

        class Meta:
            table = "widgets"
            register = False

    m = build_manifest([Widget])
    conn = apply_manifest_sqlite(m)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='widgets'")
    assert cur.fetchone() is not None
    conn.execute("INSERT INTO widgets (id, name) VALUES (1, 'a')")
    row = conn.execute("SELECT name FROM widgets WHERE id=1").fetchone()
    assert row == ("a",)
    conn.close()
