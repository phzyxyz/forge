"""Sync engine / connection factories."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from phzyx.schema.types import Dialect


@dataclass
class Engine:
    dialect: Dialect
    url: str
    _factory: Any

    def connect(self) -> Any:
        return self._factory()

    def dispose(self) -> None:
        return None


def create_engine(url: str) -> Engine:
    """Create a sync engine for sqlite / postgresql / mysql (``%s`` placeholders).

    MySQL uses PyMySQL (``uv add pymysql``). MariaDB schemes alias to MySQL.
    """
    raw = url.strip()
    if raw.startswith("sqlite:"):
        path = _sqlite_path(raw)
        return Engine(dialect=Dialect.SQLITE, url=raw, _factory=_sqlite_factory(path))
    if raw.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        return Engine(dialect=Dialect.POSTGRES, url=raw, _factory=_psycopg_factory(raw))
    if raw.startswith(("mysql://", "mysql+pymysql://", "mariadb://", "mariadb+pymysql://")):
        # Placeholders in SQL builders are already ``%s`` for non-SQLite dialects.
        return Engine(dialect=Dialect.MYSQL, url=raw, _factory=_pymysql_factory(raw))
    raise ValueError("unsupported sync URL; use sqlite:///…, postgresql://…, or mysql://…")


def _sqlite_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    if parsed.netloc == ":memory:" or path in {":memory:", "/:memory:"}:
        return ":memory:"
    if url.startswith("sqlite:////"):
        return path
    return path[1:] if path.startswith("/") else path or ":memory:"


def _sqlite_factory(path: str):
    def _connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    return _connect


def _psycopg_factory(url: str):
    def _connect():
        try:
            import psycopg  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("install psycopg: uv add 'phzyx-orm[postgres]'") from exc
        # normalize
        dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
        dsn = dsn.replace("postgres://", "postgresql://", 1)
        return psycopg.connect(dsn)

    return _connect


def _pymysql_factory(url: str):
    def _connect():
        try:
            import pymysql  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "install pymysql for MySQL: uv add pymysql  (or uv add 'phzyx-orm[mysql]')"
            ) from exc
        from urllib.parse import unquote, urlparse

        # Strip driver suffix (mysql+pymysql:// → parse as mysql://)
        scheme, _, rest = url.partition("://")
        normalized = "mysql://" + rest
        parsed = urlparse(normalized)
        return pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=unquote(parsed.username) if parsed.username else None,
            password=unquote(parsed.password) if parsed.password else "",
            database=(parsed.path or "/").lstrip("/") or None,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.Cursor,
        )

    return _connect
