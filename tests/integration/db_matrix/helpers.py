"""Shared setup/teardown for multi-dialect matrix tests."""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect

from .targets import DbTarget


class MatrixAccount(Model):
    """Rich account model for battle scenarios (identity PK + opt lock + soft)."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    name: str = Field()
    balance: int = Field(default=0)
    version: int = Field(default=1, optimistic=True)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None, auto_now_add=True)
    updated_at: datetime | None = Field(default=None, auto_now=True)

    class Meta:
        table = "mx_accounts"
        register = False


class MatrixNote(Model):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="mx_accounts.id")
    body: str = Field()

    class Meta:
        table = "mx_notes"
        register = False


class MatrixTag(Model):
    """Simple model used for migration / rename scenarios."""

    id: int | None = Field(default=None, primary_key=True)
    label: str = Field()

    class Meta:
        table = "mx_tags"
        register = False


BATTLE_MODELS: Sequence[type[Model]] = (MatrixAccount, MatrixNote)


def open_session(target: DbTarget) -> tuple[Any, Any, Session]:
    """Connect, wipe user tables, push battle models, return session."""
    conn, adapter = connect(target.url)
    wipe_user_tables(conn, target.dialect)
    push_schema(list(BATTLE_MODELS), conn, adapter, yes=True)
    session = Session(conn, dialect=target.dialect)
    return conn, adapter, session


def open_raw(target: DbTarget) -> tuple[Any, Any]:
    conn, adapter = connect(target.url)
    return conn, adapter


def wipe_user_tables(conn: Any, dialect: Dialect) -> None:
    """Drop every user table in the current database/schema.

    Shared matrix DBs accumulate leftover tables across tests and manual
    probes; push_schema's default policy refuses DROP TABLE, so the harness
    must clear first.
    """
    names = list_user_tables(conn, dialect)
    _drop_tables(conn, dialect, names)


def list_user_tables(conn: Any, dialect: Dialect) -> list[str]:
    if dialect is Dialect.SQLITE:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [r[0] for r in cur.fetchall()]
    if dialect is Dialect.POSTGRES:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            return [r[0] for r in cur.fetchall()]
    if dialect is Dialect.MSSQL:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
                ORDER BY TABLE_NAME
                """
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
    # MySQL / MariaDB — current database only
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        return [r[0] for r in cur.fetchall()]


def _drop_tables(conn: Any, dialect: Dialect, tables: Sequence[str]) -> None:
    """Best-effort drop so each test starts clean."""
    if not tables:
        return
    if dialect is Dialect.SQLITE:
        for t in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{t}"')
        conn.commit()
        return
    if dialect is Dialect.POSTGRES:
        with conn.cursor() as cur:
            for t in tables:
                cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
        conn.commit()
        return
    if dialect is Dialect.MSSQL:
        cur = conn.cursor()
        try:
            # Drop FKs first so parent tables can be removed (no CASCADE DROP).
            cur.execute(
                """
                SELECT 'ALTER TABLE [' + OBJECT_SCHEMA_NAME(parent_object_id) + '].['
                       + OBJECT_NAME(parent_object_id) + '] DROP CONSTRAINT [' + name + ']'
                FROM sys.foreign_keys
                """
            )
            for (stmt,) in cur.fetchall():
                cur.execute(stmt)
            for t in tables:
                cur.execute(f"DROP TABLE IF EXISTS [{t}]")
        finally:
            cur.close()
        conn.commit()
        return
    # MySQL / MariaDB
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in tables:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()


def integrity_error_types() -> tuple[type[BaseException], ...]:
    """Driver integrity / unique / FK exception types we accept as failures."""
    types: list[type[BaseException]] = []
    try:
        import sqlite3

        types.append(sqlite3.IntegrityError)
    except ImportError:
        pass
    try:
        import psycopg
        from psycopg import errors as pg_errors

        types.extend(
            [
                pg_errors.IntegrityError,
                pg_errors.UniqueViolation,
                pg_errors.ForeignKeyViolation,
                pg_errors.NotNullViolation,
                psycopg.Error,
            ]
        )
    except ImportError:
        pass
    try:
        import pymysql

        types.extend(
            [
                pymysql.err.IntegrityError,
                pymysql.err.OperationalError,
                pymysql.err.DataError,
            ]
        )
    except ImportError:
        pass
    try:
        import pymssql

        types.extend([pymssql.IntegrityError, pymssql.OperationalError, pymssql.DatabaseError])
    except ImportError:
        pass
    if not types:
        types.append(Exception)
    return tuple(types)


def close_all(session: Session | None, conn: Any | None) -> None:
    """Close session (which owns the connection) or the raw connection.

    Session.close() already closes the underlying DB-API connection, so we
    must not call conn.close() again (PyMySQL raises ``Already closed``).
    """
    if session is not None:
        with contextlib.suppress(Exception):
            session.close()
        return
    if conn is not None:
        with contextlib.suppress(Exception):
            conn.close()
