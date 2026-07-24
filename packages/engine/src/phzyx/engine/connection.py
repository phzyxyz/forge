"""Open sync connections from DatabaseURL."""

from __future__ import annotations

import contextlib
import sqlite3
from datetime import date, datetime
from typing import Any

from phzyx.engine.dsn import DatabaseURL, parse_database_url
from phzyx.engine.errors import ConnectionError
from phzyx.engine.introspect_mysql import MySQLAdapter, require_pymysql
from phzyx.engine.introspect_postgres import PostgresAdapter, require_psycopg
from phzyx.engine.introspect_sqlite import SQLiteAdapter
from phzyx.schema.types import Dialect

_sqlite_adapters_ready = False


def _ensure_sqlite_adapters() -> None:
    """Register ISO date/datetime adapters (Python 3.12+ deprecates defaults)."""
    global _sqlite_adapters_ready
    if _sqlite_adapters_ready:
        return
    sqlite3.register_adapter(date, lambda d: d.isoformat())
    sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))
    sqlite3.register_converter("DATE", lambda b: date.fromisoformat(b.decode()))
    sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode()))
    sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()))
    _sqlite_adapters_ready = True


def connect(
    url: str | DatabaseURL,
) -> tuple[Any, SQLiteAdapter | PostgresAdapter | MySQLAdapter]:
    """Return (connection, dialect_adapter)."""
    db = parse_database_url(url) if isinstance(url, str) else url
    if db.dialect is Dialect.SQLITE:
        _ensure_sqlite_adapters()
        path = db.path or ":memory:"
        # timeout + check_same_thread=False: AdminBoard opens a connection per
        # request; without these, concurrent SQLite ops raise "database is locked".
        conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        if path != ":memory:":
            with contextlib.suppress(sqlite3.Error):
                conn.execute("PRAGMA journal_mode = WAL")
        return conn, SQLiteAdapter()
    if db.dialect is Dialect.POSTGRES:
        psycopg = require_psycopg()
        conninfo = _postgres_conninfo(db)
        try:
            conn = psycopg.connect(conninfo)
        except Exception as exc:  # pragma: no cover
            raise ConnectionError(f"failed to connect to PostgreSQL: {exc}") from exc
        return conn, PostgresAdapter()
    if db.dialect is Dialect.MYSQL:
        pymysql = require_pymysql()
        try:
            conn = pymysql.connect(
                host=db.host or "localhost",
                port=db.port or 3306,
                user=db.user,
                password=db.password or "",
                database=db.database,
                charset="utf8mb4",
                autocommit=False,
            )
        except Exception as exc:  # pragma: no cover
            raise ConnectionError(f"failed to connect to MySQL: {exc}") from exc
        return conn, MySQLAdapter()
    raise ConnectionError(f"unsupported dialect: {db.dialect}")


def _postgres_conninfo(db: DatabaseURL) -> str:
    parts = []
    if db.host:
        parts.append(f"host={db.host}")
    if db.port:
        parts.append(f"port={db.port}")
    if db.user:
        parts.append(f"user={db.user}")
    if db.password:
        parts.append(f"password={db.password}")
    if db.database:
        parts.append(f"dbname={db.database}")
    return " ".join(parts)
