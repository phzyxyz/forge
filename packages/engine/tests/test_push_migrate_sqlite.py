"""Push + migrate round-trips on SQLite (M2 gate)."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.engine import (
    SQLiteAdapter,
    connect,
    create_migration,
    migrate_apply,
    migrate_status,
    push_schema,
)
from phzyx.schema import Field, Model, build_manifest


@pytest.mark.integration
@pytest.mark.sqlite
def test_push_introspect_empty_diff(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    url = f"sqlite:///{db}"

    class User(Model):
        id: int = Field(primary_key=True)
        email: str = Field(unique=True)

        class Meta:
            table = "users"
            register = False

    conn, adapter = connect(url)
    try:
        r1 = push_schema([User], conn, adapter, yes=True)
        assert r1.applied
        r2 = push_schema([User], conn, adapter, dry_run=True)
        assert r2.plan.empty
        live = adapter.introspect(conn)
        assert any(t.name == "users" for t in live.tables)
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_push_archives_removed_column(tmp_path: Path) -> None:
    db = tmp_path / "arch.db"
    url = f"sqlite:///{db}"

    class V1(Model):
        id: int = Field(primary_key=True)
        nickname: str = Field()

        class Meta:
            table = "users"
            register = False

    class V2(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "users"
            register = False

    conn, adapter = connect(url)
    try:
        push_schema([V1], conn, adapter, yes=True)
        r = push_schema([V2], conn, adapter, yes=True)
        assert r.applied
        assert any(o.kind == "archive_column" for o in r.plan.ops)
        assert not any(o.kind == "drop_column" for o in r.plan.ops)
        # archived column still present under new name
        cols = {row[1] for row in conn.execute('PRAGMA table_info("users")').fetchall()}
        assert "id" in cols
        assert "nickname" not in cols
        assert any(c.startswith("_phzyx_archived_nickname_") for c in cols)
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_rename_column_push(tmp_path: Path) -> None:
    db = tmp_path / "ren.db"
    url = f"sqlite:///{db}"

    class V1(Model):
        id: int = Field(primary_key=True)
        name: str = Field()

        class Meta:
            table = "people"
            register = False

    class V2(Model):
        id: int = Field(primary_key=True)
        full_name: str = Field(renamed_from="name")

        class Meta:
            table = "people"
            register = False

    conn, adapter = connect(url)
    try:
        push_schema([V1], conn, adapter, yes=True)
        r = push_schema([V2], conn, adapter, yes=True)
        assert any(o.kind == "rename_column" for o in r.plan.ops)
        cols = {row[1] for row in conn.execute('PRAGMA table_info("people")').fetchall()}
        assert "full_name" in cols
        assert "name" not in cols
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.sqlite
def test_migrate_create_apply_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "mig.db"
    mig_dir = tmp_path / "migrations"
    url = f"sqlite:///{db}"

    class Widget(Model):
        id: int = Field(primary_key=True)
        name: str = Field()

        class Meta:
            table = "widgets"
            register = False

    conn, adapter = connect(url)
    try:
        from phzyx.engine import build_plan
        from phzyx.schema.manifest import Manifest

        desired = build_manifest([Widget])
        live = Manifest(tables=())
        plan = build_plan(desired, live)
        mig = create_migration(plan, mig_dir, dialect=adapter.dialect, name="init")
        assert mig.path.exists()
        applied = migrate_apply(conn, mig_dir, dialect=adapter.dialect)
        assert mig.version in applied
        st = migrate_status(conn, mig_dir)
        assert mig.version in st.applied
        assert st.pending == []
        # second apply no-op
        applied2 = migrate_apply(conn, mig_dir, dialect=adapter.dialect)
        assert applied2 == []
        row = conn.execute("SELECT name FROM sqlite_master WHERE name='widgets'").fetchone()
        assert row is not None
    finally:
        conn.close()


@pytest.mark.unit
def test_sqlite_adapter_version() -> None:
    import sqlite3

    conn = sqlite3.connect(":memory:")
    try:
        ad = SQLiteAdapter()
        ver = ad.detect_version(conn)
        assert ver.major >= 3
        caps = ad.capabilities(ver)
        assert caps.supports("composite_pk")
    finally:
        conn.close()
