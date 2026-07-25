"""Partial indexes, generated columns, PG enum DDL, identity migration SQL."""

from __future__ import annotations

from enum import StrEnum

import pytest
from phzyx.schema import (
    Dialect,
    Field,
    Model,
    build_manifest,
    render_create_index,
    render_create_table,
    render_enum_ddl,
    render_identity_migration_sql,
    render_manifest_ddl,
)


class Color(StrEnum):
    red = "red"
    blue = "blue"


class Item(Model):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field()
    price: int = Field(default=0)
    qty: int = Field(default=1)
    total: int | None = Field(default=None, generated="price * qty")
    updated_at: str | None = Field(default=None, auto_now=True)
    color: Color = Field(default=Color.red)
    tags: list[str] = Field(default_factory=list)

    class Meta:
        table = "items_adv"
        register = False
        indexes = [
            {
                "name": "ix_items_email_lower",
                "expressions": ("lower(email)",),
            },
            {
                "name": "ix_items_active_email",
                "columns": ("email",),
                "where": "email IS NOT NULL",
            },
        ]


@pytest.mark.unit
def test_generated_partial_index_array_enum() -> None:
    m = build_manifest([Item])
    t = m.table("items_adv")
    total = next(c for c in t.columns if c.name == "total")
    assert total.generated and "price" in total.generated
    tags = next(c for c in t.columns if c.name == "tags")
    assert tags.logical_type.value == "array"

    pg_enums = render_enum_ddl(m, Dialect.POSTGRES)
    assert any("CREATE TYPE" in s and "ENUM" in s for s in pg_enums)

    pg_table = render_create_table(t, Dialect.POSTGRES)
    assert "GENERATED ALWAYS AS" in pg_table

    idxs = [render_create_index(t, ix, Dialect.POSTGRES) for ix in t.indexes]
    assert any("WHERE" in s for s in idxs)
    assert any("lower(email)" in s for s in idxs)

    mysql = render_create_table(t, Dialect.MYSQL)
    assert "ON UPDATE CURRENT_TIMESTAMP" in mysql or "updated_at" in mysql

    mig = render_identity_migration_sql("users", "id", dialect=Dialect.POSTGRES)
    assert any("SEQUENCE" in s for s in mig)

    all_ddl = render_manifest_ddl(m, Dialect.POSTGRES)
    assert all_ddl[0].startswith("CREATE TYPE")
