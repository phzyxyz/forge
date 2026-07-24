"""Database URL parsing for CLI and engine bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from phzyx.engine.errors import ConnectionError
from phzyx.schema.types import Dialect


@dataclass(frozen=True, slots=True)
class DatabaseURL:
    dialect: Dialect
    raw: str
    # sqlite
    path: str | None = None
    # network pieces (postgres / mysql)
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None
    database: str | None = None


def parse_database_url(url: str) -> DatabaseURL:
    """Parse sqlite / postgresql / mysql (and MariaDB-as-mysql) URLs.

    MariaDB schemes (``mariadb://``, ``mariadb+pymysql://``) map to
    :attr:`Dialect.MYSQL` for now — treat as a MySQL-compatible wire; a
    dedicated MariaDB dialect may land later.
    """
    raw = url.strip()
    if not raw:
        raise ConnectionError("empty database URL")

    if raw.startswith("sqlite:"):
        # sqlite:///:memory:  sqlite:///./file.db  sqlite:////abs/path
        rest = raw[len("sqlite:") :]
        if rest.startswith("////"):
            path = rest[3:]  # ////abs -> /abs after one slash kept
            # actually sqlite:////tmp/x -> path /tmp/x
            path = "/" + rest.lstrip("/")
            # simpler: urlparse
        parsed = urlparse(raw)
        path = unquote(parsed.path or "")
        if parsed.netloc == ":memory:" or path in {":memory:", "/:memory:"}:
            return DatabaseURL(dialect=Dialect.SQLITE, raw=raw, path=":memory:")
        if path.startswith("/") and len(path) > 1 and not path.startswith("//"):
            # sqlite:///relative -> /relative on some parsers; sqlite:///./f -> /./f
            # For 3-slash form sqlite:///foo.db path is /foo.db meaning relative foo.db
            if raw.startswith("sqlite:////"):
                file_path = path  # absolute
            else:
                file_path = path[1:] if path.startswith("/") else path
            return DatabaseURL(dialect=Dialect.SQLITE, raw=raw, path=file_path or ":memory:")
        return DatabaseURL(dialect=Dialect.SQLITE, raw=raw, path=path or ":memory:")

    if raw.startswith(("postgresql://", "postgres://", "postgresql+", "postgres+")):
        # strip driver suffix postgresql+psycopg://
        normalized = raw
        if "+psycopg" in normalized.split("://", 1)[0]:
            scheme, rest = normalized.split("://", 1)
            normalized = "postgresql://" + rest
        elif normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized[len("postgres://") :]
        parsed = urlparse(normalized)
        return DatabaseURL(
            dialect=Dialect.POSTGRES,
            raw=raw,
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=unquote(parsed.username) if parsed.username else None,
            password=unquote(parsed.password) if parsed.password else None,
            database=(parsed.path or "/").lstrip("/") or None,
        )

    if raw.startswith(("mysql://", "mysql+", "mariadb://", "mariadb+")):
        # mysql://  mysql+pymysql://  mariadb:// (alias → Dialect.MYSQL)
        normalized = raw
        scheme, _, rest = normalized.partition("://")
        if not rest:
            raise ConnectionError(f"malformed MySQL URL: {url!r}")
        # Drop driver suffix (mysql+pymysql, mariadb+pymysql, …).
        normalized = "mysql://" + rest
        parsed = urlparse(normalized)
        return DatabaseURL(
            dialect=Dialect.MYSQL,
            raw=raw,
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=unquote(parsed.username) if parsed.username else None,
            password=unquote(parsed.password) if parsed.password else None,
            database=(parsed.path or "/").lstrip("/") or None,
        )

    raise ConnectionError(
        f"unsupported database URL scheme (use sqlite:///, postgresql://, or mysql://): {url!r}"
    )
