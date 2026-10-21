"""Downgrade SQL is real DDL, and session constructors live on phzyx.engine."""

from __future__ import annotations

import phzyx.engine as engine
import phzyx.orm as orm
import pytest
from phzyx.engine import SchemaOp, SchemaPlan, render_downgrade_sql
from phzyx.schema.manifest import ColumnDef, IndexDef
from phzyx.schema.types import Dialect, LogicalType


@pytest.mark.unit
def test_downgrade_reverses_creates_and_does_not_pretend_to_undo_drops() -> None:
    plan = SchemaPlan(
        ops=[
            SchemaOp(kind="create_table", table="users"),
            SchemaOp(
                kind="add_column",
                table="users",
                column=ColumnDef(name="email", logical_type=LogicalType.STR),
            ),
            SchemaOp(
                kind="add_index",
                table="users",
                index=IndexDef(name="ix_users_email", columns=("email",)),
            ),
            SchemaOp(
                kind="rename_column",
                table="users",
                column_name="email",
                new_column_name="mail",
            ),
            SchemaOp(kind="drop_table", table="legacy"),
        ]
    )
    sql = render_downgrade_sql(plan, dialect=Dialect.SQLITE)

    assert "not automatic" not in sql
    assert "TODO" not in sql
    assert "-- not reversible: Drop table legacy" in sql
    # Opposite order of the reversible operations. The drop stays a comment.
    assert sql.index('RENAME COLUMN "mail" TO "email"') < sql.index("DROP INDEX")
    assert sql.index("DROP INDEX") < sql.index("DROP COLUMN")
    assert sql.index("DROP COLUMN") < sql.index('DROP TABLE "users"')


@pytest.mark.unit
def test_mssql_downgrade_drops_an_index_on_its_table() -> None:
    plan = SchemaPlan(
        ops=[
            SchemaOp(
                kind="add_index",
                table="users",
                index=IndexDef(name="ix_users_email", columns=("email",)),
            )
        ]
    )
    sql = render_downgrade_sql(plan, dialect=Dialect.MSSQL)
    assert "DROP INDEX [ix_users_email] ON [users]" in sql


@pytest.mark.unit
def test_engine_reexports_the_session_constructors() -> None:
    assert engine.create_engine is orm.create_engine
    assert engine.create_sync_engine is orm.create_engine
    assert engine.create_async_engine is orm.create_async_engine
    assert engine.create_session is orm.create_session
    assert engine.create_async_session is orm.create_async_session
    assert engine.Engine is orm.Engine
    assert engine.AsyncEngine is orm.AsyncEngine
    assert engine.Session is orm.Session
    assert engine.AsyncSession is orm.AsyncSession
