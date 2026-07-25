"""Deep ORM battle tests across SQLite + multi-version Postgres/MySQL/MariaDB.

Coverage tiers:
  happy      — AI insert, get, update, delete, count, query
  moderate   — unique, FK, upsert, bulk, soft-delete, timestamps
  difficult  — optimistic lock, FOR UPDATE, many AI inserts, seed id
  edge       — rollback, missing rows, unicode, special chars, re-push
"""

from __future__ import annotations

import pytest
from phzyx.engine import connect, push_schema
from phzyx.orm import (
    ConflictError,
    Session,
    bulk_insert,
    bulk_update,
    soft_delete,
    soft_delete_filter,
    upsert,
)
from phzyx.orm.expr import eq

from .helpers import (
    MatrixAccount,
    MatrixNote,
    close_all,
    integrity_error_types,
    open_session,
)
from .targets import DbTarget

pytestmark = [
    pytest.mark.integration,
    pytest.mark.db_matrix,
    pytest.mark.slow,
]


# ── Happy path ──────────────────────────────────────────────────────────────


def test_happy_identity_crud(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(email="happy@x.co", name="Happy"))
        session.commit()
        assert a.id is not None
        assert a.id >= 1
        assert a.version == 1
        assert a.created_at is not None

        got = session.get(MatrixAccount, a.id)
        assert got is not None
        assert got.email == "happy@x.co"

        updated = session.update(got, name="Happy2", balance=10)
        session.commit()
        assert updated.name == "Happy2"
        assert updated.version == 2
        assert updated.balance == 10

        assert session.count(MatrixAccount) == 1
        rows = session.query(MatrixAccount, limit=10)
        assert len(rows) == 1

        session.delete(updated)
        session.commit()
        assert session.get(MatrixAccount, a.id) is None
        assert session.count(MatrixAccount) == 0
    finally:
        close_all(session, conn)


def test_happy_explicit_seed_id(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(id=9001, email="seed@x.co", name="Seed"))
        session.commit()
        assert a.id == 9001
        got = session.get(MatrixAccount, 9001)
        assert got is not None
        assert got.name == "Seed"
        # AI after explicit id should still work
        b = session.add(MatrixAccount(email="after@x.co", name="After"))
        session.commit()
        assert b.id is not None
        assert b.id != 9001
    finally:
        close_all(session, conn)


# ── Moderate ────────────────────────────────────────────────────────────────


def test_moderate_unique_violation(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        session.add(MatrixAccount(email="u@x.co", name="One"))
        session.commit()
        with pytest.raises(integrity_error_types()):
            session.add(MatrixAccount(email="u@x.co", name="Two"))
            session.commit()
        session.rollback()
        assert session.count(MatrixAccount) == 1
    finally:
        close_all(session, conn)


def test_moderate_fk_orphan_rejected(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        with pytest.raises(integrity_error_types()):
            session.add(MatrixNote(account_id=999_999, body="orphan"))
            session.commit()
        session.rollback()
    finally:
        close_all(session, conn)


def test_moderate_upsert_and_bulk(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        session.add(MatrixAccount(id=50, email="bulk@x.co", name="B0", version=1))
        session.commit()
        upsert(
            session,
            MatrixAccount(id=50, email="bulk@x.co", name="B1", version=1),
            conflict=["id"],
            update_columns=["name"],
        )
        session.commit()
        row = session.get(MatrixAccount, 50)
        assert row is not None
        assert row.name == "B1"

        bulk_insert(
            session,
            MatrixAccount,
            [
                {"id": 60, "email": "b60@x.co", "name": "B60", "version": 1},
                {"id": 61, "email": "b61@x.co", "name": "B61", "version": 1},
            ],
        )
        session.commit()
        bulk_update(session, MatrixAccount, [{"id": 60, "name": "B60x"}])
        session.commit()
        assert session.get(MatrixAccount, 60).name == "B60x"  # type: ignore[union-attr]
    finally:
        close_all(session, conn)


def test_moderate_soft_delete_and_timestamps(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(email="soft@x.co", name="Soft"))
        session.commit()
        created = a.created_at
        assert created is not None
        soft_delete(session, a)
        session.commit()
        live = session.query(MatrixAccount, where=soft_delete_filter())
        assert all(x.id != a.id for x in live)
        # Hard get still finds row unless we filtered — soft_delete only sets deleted_at
        again = session.get(MatrixAccount, a.id)
        assert again is not None
        assert again.deleted_at is not None
    finally:
        close_all(session, conn)


def test_moderate_query_filters_and_order(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        for i, name in enumerate(["zeta", "alpha", "mu"], start=1):
            session.add(MatrixAccount(id=i, email=f"{name}@x.co", name=name, version=1))
        session.commit()
        rows = session.query(
            MatrixAccount,
            where=[eq("name", "alpha")],
        )
        assert len(rows) == 1
        assert rows[0].email == "alpha@x.co"
        assert session.count(MatrixAccount, where=[eq("name", "mu")]) == 1
    finally:
        close_all(session, conn)


# ── Difficult ───────────────────────────────────────────────────────────────


def test_difficult_optimistic_lock(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(email="opt@x.co", name="O"))
        session.commit()
        r1 = session.get(MatrixAccount, a.id)
        r2 = session.get(MatrixAccount, a.id)
        assert r1 and r2
        session.update(r1, name="O1")
        session.commit()
        with pytest.raises(ConflictError):
            session.update(r2, name="O2")
        session.rollback()
        final = session.get(MatrixAccount, a.id)
        assert final is not None
        assert final.name == "O1"
        assert final.version == 2
    finally:
        close_all(session, conn)


def test_difficult_for_update(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(email="lock@x.co", name="L"))
        session.commit()
        locked = session.get_for_update(MatrixAccount, a.id)
        assert locked is not None
        assert locked.email == "lock@x.co"
        session.commit()
    finally:
        close_all(session, conn)


def test_difficult_many_ai_inserts(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        ids: list[int] = []
        for i in range(20):
            row = session.add(MatrixAccount(email=f"m{i}@x.co", name=f"M{i}"))
            session.commit()
            assert row.id is not None
            ids.append(row.id)
        assert len(ids) == len(set(ids))
        assert session.count(MatrixAccount) == 20
    finally:
        close_all(session, conn)


def test_difficult_fk_child_and_parent_delete_order(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        a = session.add(MatrixAccount(email="parent@x.co", name="P"))
        session.commit()
        n = session.add(MatrixNote(account_id=a.id, body="hello 世界"))
        session.commit()
        assert n.id is not None
        # Deleting parent with child should fail without cascade
        with pytest.raises(integrity_error_types()):
            session.delete(a)
            session.commit()
        session.rollback()
        session.delete(n)
        session.commit()
        session.delete(a)
        session.commit()
        assert session.get(MatrixAccount, a.id) is None
    finally:
        close_all(session, conn)


# ── Edge cases ──────────────────────────────────────────────────────────────


def test_edge_rollback_after_error(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        session.add(MatrixAccount(email="r@x.co", name="R"))
        session.commit()
        with pytest.raises(integrity_error_types()):
            session.add(MatrixAccount(email="r@x.co", name="Dup"))
            session.commit()
        session.rollback()
        # After rollback we can still insert a different row
        b = session.add(MatrixAccount(email="r2@x.co", name="R2"))
        session.commit()
        assert b.id is not None
        assert session.count(MatrixAccount) == 2
    finally:
        close_all(session, conn)


def test_edge_get_missing_and_update_without_pk(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        assert session.get(MatrixAccount, 42_424_242) is None
        bare = MatrixAccount(email="nopk@x.co", name="X")
        with pytest.raises(ValueError, match="primary key"):
            session.update(bare, name="Y")
    finally:
        close_all(session, conn)


def test_edge_unicode_and_special_chars(db_target: DbTarget) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        email = "üñîçødé+tag@exämple.com"
        name = 'O\'Brien "quotes" \\ slash 日本語 🎉'
        a = session.add(MatrixAccount(email=email, name=name))
        session.commit()
        got = session.get(MatrixAccount, a.id)
        assert got is not None
        assert got.email == email
        assert got.name == name
    finally:
        close_all(session, conn)


def test_edge_repush_idempotent(db_target: DbTarget) -> None:
    conn, adapter = connect(db_target.url)
    session = None
    try:
        from .helpers import BATTLE_MODELS, wipe_user_tables

        wipe_user_tables(conn, db_target.dialect)
        r1 = push_schema(list(BATTLE_MODELS), conn, adapter, yes=True)
        assert r1.applied or r1.plan.empty
        r2 = push_schema(list(BATTLE_MODELS), conn, adapter, dry_run=True)
        assert r2.plan.empty, f"re-push not empty on {db_target.id}: {r2.plan.ops}"
        live = adapter.introspect(conn)
        names = {t.name for t in live.tables}
        assert "mx_accounts" in names
        assert "mx_notes" in names
    finally:
        close_all(session, conn)


def test_edge_second_connection_sees_commit(db_target: DbTarget) -> None:
    conn1, adapter1, session1 = open_session(db_target)
    conn2 = None
    session2 = None
    try:
        a = session1.add(MatrixAccount(email="vis@x.co", name="Visible"))
        session1.commit()
        conn2, _ = connect(db_target.url)
        session2 = Session(conn2, dialect=db_target.dialect)
        got = session2.get(MatrixAccount, a.id)
        assert got is not None
        assert got.name == "Visible"
    finally:
        close_all(session1, conn1)
        close_all(session2, conn2)
