"""Push + migrate battle tests across the DB matrix."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from phzyx.engine import (
    build_plan,
    connect,
    create_migration,
    migrate_apply,
    migrate_status,
    push_schema,
)
from phzyx.orm import Field, Model, Session
from phzyx.schema.manifest import Manifest

from .helpers import close_all, wipe_user_tables
from .targets import DbTarget

pytestmark = [
    pytest.mark.integration,
    pytest.mark.db_matrix,
    pytest.mark.slow,
]


def test_push_add_column_and_archive(db_target: DbTarget) -> None:
    conn, adapter = connect(db_target.url)
    try:
        wipe_user_tables(conn, db_target.dialect)

        class V1(Model):
            id: int | None = Field(default=None, primary_key=True)
            nickname: str = Field()

            class Meta:
                table = "mx_tags"
                register = False

        class V2(Model):
            id: int | None = Field(default=None, primary_key=True)
            # drop nickname via archive policy (not hard DROP)

            class Meta:
                table = "mx_tags"
                register = False

        r1 = push_schema([V1], conn, adapter, yes=True)
        assert r1.applied
        session = Session(conn, dialect=db_target.dialect)
        row = session.add(V1(nickname="neo"))
        session.commit()
        assert row.id is not None

        r2 = push_schema([V2], conn, adapter, yes=True)
        assert r2.applied
        assert any(o.kind == "archive_column" for o in r2.plan.ops)
        assert not any(o.kind == "drop_column" for o in r2.plan.ops)

        # re-push empty
        r3 = push_schema([V2], conn, adapter, dry_run=True)
        assert r3.plan.empty, f"re-push not empty: {r3.plan.ops}"
        close_all(session, conn)
        conn = None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def test_push_rename_column(db_target: DbTarget) -> None:
    conn, adapter = connect(db_target.url)
    try:
        wipe_user_tables(conn, db_target.dialect)

        class V1(Model):
            id: int | None = Field(default=None, primary_key=True)
            name: str = Field()

            class Meta:
                table = "mx_people"
                register = False

        class V2(Model):
            id: int | None = Field(default=None, primary_key=True)
            full_name: str = Field(renamed_from="name")

            class Meta:
                table = "mx_people"
                register = False

        push_schema([V1], conn, adapter, yes=True)
        session = Session(conn, dialect=db_target.dialect)
        session.add(V1(name="Ada"))
        session.commit()
        r = push_schema([V2], conn, adapter, yes=True)
        assert any(o.kind == "rename_column" for o in r.plan.ops)
        live = adapter.introspect(conn)
        table = next(t for t in live.tables if t.name == "mx_people")
        col_names = {c.name for c in table.columns}
        assert "full_name" in col_names
        assert "name" not in col_names
        close_all(session, conn)
        conn = None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def test_migrate_create_apply_idempotent(db_target: DbTarget, tmp_path: Path) -> None:
    conn, adapter = connect(db_target.url)
    mig_dir = tmp_path / "migrations"
    try:
        wipe_user_tables(conn, db_target.dialect)

        class Widget(Model):
            id: int | None = Field(default=None, primary_key=True)
            name: str = Field()

            class Meta:
                table = "mx_widgets"
                register = False

        from phzyx.schema.manifest import build_manifest

        desired = build_manifest([Widget])
        live = Manifest(tables=())
        plan = build_plan(desired, live)
        mig = create_migration(plan, mig_dir, dialect=adapter.dialect, name="init")
        assert mig.path.exists()
        applied = migrate_apply(conn, mig_dir, dialect=adapter.dialect)
        assert mig.version in applied
        st = migrate_status(conn, mig_dir, dialect=adapter.dialect)
        assert mig.version in st.applied
        assert st.pending == []
        applied2 = migrate_apply(conn, mig_dir, dialect=adapter.dialect)
        assert applied2 == []

        session = Session(conn, dialect=db_target.dialect)
        w = session.add(Widget(name="w1"))
        session.commit()
        assert w.id is not None
        close_all(session, conn)
        conn = None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def test_push_add_nullable_column(db_target: DbTarget) -> None:
    conn, adapter = connect(db_target.url)
    try:
        wipe_user_tables(conn, db_target.dialect)

        class V1(Model):
            id: int | None = Field(default=None, primary_key=True)
            label: str = Field()

            class Meta:
                table = "mx_tags"
                register = False

        class V2(Model):
            id: int | None = Field(default=None, primary_key=True)
            label: str = Field()
            color: str | None = Field(default=None)

            class Meta:
                table = "mx_tags"
                register = False

        push_schema([V1], conn, adapter, yes=True)
        session = Session(conn, dialect=db_target.dialect)
        session.add(V1(label="red"))
        session.commit()
        r = push_schema([V2], conn, adapter, yes=True)
        assert r.applied
        # old row still readable under expanded model
        rows = session.query(V2)
        assert len(rows) == 1
        assert rows[0].label == "red"
        # new column may be None
        session.add(V2(label="blue", color="#00f"))
        session.commit()
        assert session.count(V2) == 2
        close_all(session, conn)
        conn = None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def test_introspect_roundtrip_accounts(db_target: DbTarget) -> None:
    conn, adapter = connect(db_target.url)
    try:
        from .helpers import BATTLE_MODELS

        wipe_user_tables(conn, db_target.dialect)
        push_schema(list(BATTLE_MODELS), conn, adapter, yes=True)
        live = adapter.introspect(conn)
        by_name = {t.name: t for t in live.tables}
        assert "mx_accounts" in by_name
        cols = {c.name for c in by_name["mx_accounts"].columns}
        for expected in ("id", "email", "name", "version", "deleted_at"):
            assert expected in cols, f"{expected} missing on {db_target.id}: {cols}"
    finally:
        conn.close()
