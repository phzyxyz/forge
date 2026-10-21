"""ORM-backed session / API key / password-reset / user stores (phzyx-orm Session)."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from phzyx.auth.api_keys import IssuedAPIKey
from phzyx.auth.crypto import hash_token
from phzyx.auth.models import (
    APIKey,
    AuthSession,
    PasswordResetToken,
    RateLimitBucket,
    RefreshToken,
    User,
)
from phzyx.auth.password import generate_token
from phzyx.auth.principal import Principal
from phzyx.auth.sessions import SessionRecord
from phzyx.orm.expr import eq
from phzyx.orm.session_sync import Session
from phzyx.schema.model import get_table_info
from phzyx.schema.types import Dialect

SessionFactory = Callable[[], Session]


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sql_placeholder(session: Session) -> str:
    """Bind marker for one value in a hand-written statement.

    SQLite's driver uses ``?``. PostgreSQL through psycopg uses ``%s``.
    """
    if session.dialect is Dialect.SQLITE:
        return "?"
    return "%s"


def _is_duplicate_key(exc: BaseException) -> bool:
    """True when the driver rejected the insert because the key already exists.

    sqlite3 calls that ``IntegrityError``. psycopg calls it ``UniqueViolation``.
    The class name is enough; this module does not import either driver.
    """
    return type(exc).__name__ in {"IntegrityError", "UniqueViolation"}


def _positive_int(value: Any) -> int | None:
    """An id the caller actually chose. ``None``, ``0``, and junk become "no id"."""
    try:
        number = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return None
    if number > 0:
        return number
    return None


def _first_column(row: Any, column_name: str) -> Any:
    """Read one value from a driver row.

    ``execute_returning`` hands back a dict keyed by column name.
    sqlite3 hands back a tuple or ``sqlite3.Row``, and the value we asked
    for is the first column of the SELECT or RETURNING list.
    """
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(column_name)
    return row[0]


def _user_for_insert(user: User, user_id: int | None) -> User:
    """Copy the user onto a new row with the id that should be inserted.

    ``None`` leaves the primary key out of the INSERT so the database
    assigns it. The caller's object is not modified. ``session.add``
    returns a different object that carries the assigned id.
    """
    return User(
        id=user_id,
        email=user.email,
        username=user.username,
        password_hash=user.password_hash,
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        email_verified=getattr(user, "email_verified", False),
        mfa_enabled=getattr(user, "mfa_enabled", False),
        failed_login_count=getattr(user, "failed_login_count", 0),
        locked_until=getattr(user, "locked_until", None),
        last_login_at=getattr(user, "last_login_at", None),
        created_at=user.created_at or _now_naive(),
        updated_at=_now_naive(),
    )


def _find_user_id_ignore_case(session: Session, username: str) -> int | None:
    """User id for this username, comparing with ``LOWER`` on both sides.

    Usernames may contain ``_``. That character is a wildcard in ``LIKE``
    and ``ILIKE``, so a pattern match would accept the wrong row. This is
    one equality check, not a scan of the table.
    """
    placeholder = _sql_placeholder(session)
    sql = f"SELECT id FROM phzyx_auth_users WHERE LOWER(username) = LOWER({placeholder}) LIMIT 1"
    if session.dialect is Dialect.SQLITE:
        # execute_returning opens a cursor(). The sqlite connection used
        # here has execute() on the connection itself, not that cursor API.
        cursor = session._conn.execute(sql, (username,))
        row = cursor.fetchone()
    else:
        row = session.execute_returning(sql, [username])
    user_id = _first_column(row, "id")
    if user_id is None:
        return None
    return int(user_id)


@dataclass
class OrmSessionStore:
    """Persist opaque sessions in ``AuthSession`` table."""

    session_factory: SessionFactory

    def create(
        self,
        user_id: str,
        *,
        ttl_seconds: int,
        idle_seconds: int | None = None,
        user_agent: str | None = None,
        ip_hash: str | None = None,
        secret: str = "",
    ) -> str:
        raw = generate_token(32)
        now = _now_naive()
        idle = now + timedelta(seconds=idle_seconds) if idle_seconds is not None else None
        session = self.session_factory()
        try:
            row = AuthSession(
                token_hash=hash_token(raw, secret=secret),
                user_id=int(user_id),
                expires_at=now + timedelta(seconds=ttl_seconds),
                idle_expires_at=idle,
                revoked_at=None,
                user_agent=user_agent,
                ip_hash=ip_hash,
                created_at=now,
            )
            session.add(row)
            session.commit()
        finally:
            session.close()
        return raw

    def get(self, raw_token: str, *, secret: str = "") -> SessionRecord | None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.revoked_at is not None:
                return None
            now = _now_naive()
            exp = row.expires_at
            if getattr(exp, "tzinfo", None) is not None:
                exp = exp.replace(tzinfo=None)
            if exp < now:
                return None
            idle = row.idle_expires_at
            if idle is not None:
                if getattr(idle, "tzinfo", None) is not None:
                    idle = idle.replace(tzinfo=None)
                if idle < now:
                    return None
            return SessionRecord(
                token_hash=row.token_hash,
                user_id=str(row.user_id),
                expires_at=row.expires_at,
                idle_expires_at=row.idle_expires_at,
                revoked=False,
                user_agent=row.user_agent,
                ip_hash=row.ip_hash,
            )
        finally:
            session.close()

    def touch(self, raw_token: str, *, idle_seconds: int, secret: str = "") -> None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return
            row = rows[0]
            idle = _now_naive() + timedelta(seconds=idle_seconds)
            session.update(row, idle_expires_at=idle)
            session.commit()
        finally:
            session.close()

    def revoke(self, raw_token: str, *, secret: str = "") -> None:
        h = hash_token(raw_token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(AuthSession, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return
            session.update(rows[0], revoked_at=_now_naive())
            session.commit()
        finally:
            session.close()

    def revoke_user(self, user_id: str) -> int:
        """Revoke every live session for this user in one UPDATE.

        Loading the rows and updating them one by one stops at a page size.
        A user with more sessions than that page would stay logged in.
        """
        session = self.session_factory()
        try:
            placeholder = _sql_placeholder(session)
            table_name = get_table_info(AuthSession).name
            revoked_at = _now_naive()
            updated = session.execute(
                f"UPDATE {table_name} SET revoked_at = {placeholder} "
                f"WHERE user_id = {placeholder} AND revoked_at IS NULL",
                [revoked_at, int(user_id)],
            )
            session.commit()
            # Some drivers report rowcount as -1 when they do not know it.
            if updated < 0:
                return 0
            return updated
        finally:
            session.close()


@dataclass
class OrmAPIKeyStore:
    """Persist API keys in ``APIKey`` table."""

    session_factory: SessionFactory

    def create(
        self,
        *,
        name: str,
        user_id: str | None,
        scopes: list[str],
        secret: str,
        expires_at: datetime | None = None,
    ) -> IssuedAPIKey:
        raw_secret = generate_token(24)
        prefix = f"phx_{raw_secret[:8]}"
        raw_key = f"{prefix}.{raw_secret}"
        session = self.session_factory()
        try:
            row = APIKey(
                name=name,
                prefix=prefix,
                key_hash=hash_token(raw_key, secret=secret),
                user_id=int(user_id) if user_id is not None else None,
                scopes=" ".join(scopes),
                expires_at=expires_at,
                revoked_at=None,
                last_used_at=None,
                created_at=_now_naive(),
            )
            saved = session.add(row)
            session.commit()
            return IssuedAPIKey(
                id=str(saved.id), name=name, prefix=prefix, raw_key=raw_key, scopes=list(scopes)
            )
        finally:
            session.close()

    def verify(self, raw_key: str, *, secret: str) -> Principal | None:
        h = hash_token(raw_key, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("key_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.revoked_at is not None:
                return None
            exp = row.expires_at
            if exp is not None:
                now = _now_naive()
                e = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
                if e < now:
                    return None
            scopes = frozenset(s for s in (row.scopes or "").split() if s)
            session.update(row, last_used_at=_now_naive())
            session.commit()
            return Principal(
                id=str(row.user_id or f"key:{row.id}"),
                scopes=scopes,
                permissions=scopes,
                auth_method="api_key",
            )
        finally:
            session.close()

    def revoke(self, key_id: str, *, user_id: str | None = None) -> bool:
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("id", int(key_id))], limit=1)
            if not rows:
                return False
            row = rows[0]
            if user_id is not None and str(row.user_id) != str(user_id):
                return False
            session.update(row, revoked_at=_now_naive())
            session.commit()
            return True
        finally:
            session.close()

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        session = self.session_factory()
        try:
            rows = session.query(APIKey, where=[eq("user_id", int(user_id))], limit=1000)
            out = []
            for row in rows:
                if row.revoked_at is not None:
                    continue
                out.append(
                    {
                        "id": str(row.id),
                        "name": row.name,
                        "prefix": row.prefix,
                        "scopes": [s for s in (row.scopes or "").split() if s],
                    }
                )
            return out
        finally:
            session.close()


@dataclass
class OrmPasswordResetStore:
    """Persist password reset tokens (used by AuthService when injected)."""

    session_factory: SessionFactory

    def create(self, *, user_id: str, secret: str, ttl_hours: int = 1) -> str:
        raw = generate_token(32)
        session = self.session_factory()
        try:
            row = PasswordResetToken(
                token_hash=hash_token(raw, secret=secret),
                user_id=int(user_id),
                expires_at=_now_naive() + timedelta(hours=ttl_hours),
                used_at=None,
                attempts=0,
                created_at=_now_naive(),
            )
            session.add(row)
            session.commit()
            return raw
        finally:
            session.close()

    def consume(self, token: str, *, secret: str, max_attempts: int = 5) -> str | None:
        """Return user_id if valid; mark used. None if invalid."""
        h = hash_token(token, secret=secret)
        session = self.session_factory()
        try:
            rows = session.query(PasswordResetToken, where=[eq("token_hash", h)], limit=1)
            if not rows:
                return None
            row = rows[0]
            if row.used_at is not None:
                return None
            attempts = int(row.attempts or 0) + 1
            if attempts > max_attempts:
                session.update(row, attempts=attempts, used_at=_now_naive())
                session.commit()
                return None
            exp = row.expires_at
            e = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
            if e < _now_naive():
                session.update(row, attempts=attempts)
                session.commit()
                return None
            session.update(row, attempts=attempts, used_at=_now_naive())
            session.commit()
            return str(row.user_id)
        finally:
            session.close()


@dataclass
class OrmUserRepository:
    """Load/save ``phzyx.auth.models.User`` rows."""

    session_factory: SessionFactory

    def all_by_email(self) -> dict[str, User]:
        session = self.session_factory()
        try:
            out: dict[str, User] = {}
            offset = 0
            page = 1000
            while True:
                rows = session.query(User, limit=page, offset=offset)
                if not rows:
                    break
                for user in rows:
                    out[str(user.email).lower()] = user
                if len(rows) < page:
                    break
                offset += page
            return out
        finally:
            session.close()

    def get_by_email(self, email: str) -> User | None:
        session = self.session_factory()
        try:
            rows = session.query(User, where=[eq("email", email.strip().lower())], limit=1)
            return rows[0] if rows else None
        finally:
            session.close()

    def get_by_username(self, username: str) -> User | None:
        """Case-insensitive username lookup (Django-style alternate login id)."""
        uname = (username or "").strip()
        if not uname:
            return None
        session = self.session_factory()
        try:
            # Exact match first. Case differences go through LOWER(), not a scan.
            rows = session.query(User, where=[eq("username", uname)], limit=1)
            if rows:
                return rows[0]
            found_id = _find_user_id_ignore_case(session, uname)
            if found_id is None:
                return None
            return session.get(User, found_id)
        finally:
            session.close()

    def get_by_id(self, user_id: str) -> User | None:
        session = self.session_factory()
        try:
            return session.get(User, int(user_id))
        finally:
            session.close()

    def save_new(self, user: User) -> User:
        """Insert ``user`` and return the row the database stored.

        A missing id, or an id that is already taken, is left unset so the
        identity column assigns one inside the INSERT. An id the caller
        picked is kept when that row does not exist yet. Two callers can
        both observe the same id as free; the loser retries once without it.
        """
        session = self.session_factory()
        try:
            requested_id = _positive_int(getattr(user, "id", None))
            id_is_free = requested_id is not None and session.get(User, requested_id) is None
            insert_id = requested_id if id_is_free else None
            try:
                saved = session.add(_user_for_insert(user, insert_id))
                session.commit()
            except Exception as exc:
                session.rollback()
                if insert_id is None or not _is_duplicate_key(exc):
                    raise
                saved = session.add(_user_for_insert(user, None))
                session.commit()
            return saved
        finally:
            session.close()

    def update(self, user: User, **values: Any) -> User:
        session = self.session_factory()
        try:
            live = session.get(User, int(user.id))
            if live is None:
                raise KeyError(user.id)
            updated = session.update(live, **values, updated_at=_now_naive())
            session.commit()
            return updated
        finally:
            session.close()


@dataclass
class HybridUserMap:
    """Dict-like email→user that reads through to ORM and keeps a write-through cache."""

    repo: OrmUserRepository
    _cache: dict[str, Any] = field(default_factory=dict)
    loaded: bool = False

    def _ensure(self) -> None:
        if not self.loaded:
            self._cache = dict(self.repo.all_by_email())
            self.loaded = True

    def get(self, email: str, default: Any = None) -> Any:
        """Prefer live ORM row so admin/seed toggles (e.g. mfa_enabled) are not stale."""
        email_n = str(email).strip().lower()
        live = self.repo.get_by_email(email_n)
        if live is not None:
            self._cache[email_n] = live
            self.loaded = True
            return live
        self._ensure()
        return self._cache.get(email_n, default)

    def get_by_username(self, username: str, default: Any = None) -> Any:
        live = self.repo.get_by_username(username)
        if live is not None:
            email_n = str(live.email).strip().lower()
            self._cache[email_n] = live
            self.loaded = True
            return live
        self._ensure()
        lower = (username or "").strip().lower()
        for u in self._cache.values():
            if str(getattr(u, "username", "") or "").lower() == lower:
                return u
        return default

    def __contains__(self, email: object) -> bool:
        self._ensure()
        return str(email).strip().lower() in self._cache

    def __setitem__(self, email: str, user: Any) -> None:
        self._ensure()
        email_n = str(email).strip().lower()
        # persist if new
        if email_n not in self._cache:
            # Always go through save_new (allocates free PK; never silent update).
            user = self.repo.save_new(user)
            email_n = str(getattr(user, "email", email_n)).strip().lower()
        else:
            # update mutable fields
            with contextlib.suppress(Exception):
                self.repo.update(
                    user,
                    password_hash=user.password_hash,
                    failed_login_count=getattr(user, "failed_login_count", 0),
                    locked_until=getattr(user, "locked_until", None),
                    last_login_at=getattr(user, "last_login_at", None),
                    is_active=getattr(user, "is_active", True),
                    email_verified=getattr(user, "email_verified", False),
                    mfa_enabled=getattr(user, "mfa_enabled", False),
                )
        self._cache[email_n] = user

    def values(self) -> Any:
        self._ensure()
        return self._cache.values()

    def __len__(self) -> int:
        self._ensure()
        return len(self._cache)


def _refresh_view(row: RefreshToken) -> dict[str, Any]:
    return {
        "family_id": row.family_id,
        "user_id": str(row.user_id),
        "expires_at": _as_utc(row.expires_at),
        "scopes": row.scopes or "",
        "revoked": row.revoked_at is not None,
        "receipt_access": row.receipt_access,
        "receipt_refresh": row.receipt_refresh,
        "receipt_until": _as_utc(row.receipt_expires_at),
        "receipt_expires_in": row.receipt_expires_in,
    }


@dataclass
class OrmRefreshStore:
    """Refresh tokens and lost-response receipts in ``RefreshToken``."""

    session_factory: SessionFactory

    def _row(self, session: Session, refresh_token: str, *, secret: str) -> RefreshToken | None:
        digest = hash_token(refresh_token, secret=secret)
        rows = session.query(RefreshToken, where=[eq("jti_hash", digest)], limit=1)
        return rows[0] if rows else None

    def save(
        self,
        *,
        jti: str,
        family_id: str,
        user_id: str,
        expires_at: datetime,
        scopes: str,
        secret: str,
    ) -> None:
        session = self.session_factory()
        try:
            session.add(
                RefreshToken(
                    jti_hash=hash_token(jti, secret=secret),
                    family_id=family_id,
                    user_id=int(user_id),
                    expires_at=_naive(expires_at),
                    revoked_at=None,
                    scopes=scopes,
                    created_at=_now_naive(),
                )
            )
            session.commit()
        finally:
            session.close()

    def get(self, refresh_token: str, *, secret: str) -> dict[str, Any] | None:
        session = self.session_factory()
        try:
            row = self._row(session, refresh_token, secret=secret)
            if row is None:
                return None
            return _refresh_view(row)
        finally:
            session.close()

    def mark_consumed(self, refresh_token: str, *, secret: str) -> bool:
        session = self.session_factory()
        try:
            row = self._row(session, refresh_token, secret=secret)
            if row is None or row.revoked_at is not None:
                return False
            session.update(row, revoked_at=_now_naive())
            session.commit()
            return True
        finally:
            session.close()

    def save_receipt(
        self,
        refresh_token: str,
        *,
        secret: str,
        access_token: str,
        refresh_token_next: str,
        expires_in: int,
        until: datetime,
    ) -> None:
        session = self.session_factory()
        try:
            row = self._row(session, refresh_token, secret=secret)
            if row is None:
                return
            session.update(
                row,
                receipt_access=access_token,
                receipt_refresh=refresh_token_next,
                receipt_expires_in=expires_in,
                receipt_expires_at=_naive(until),
            )
            session.commit()
        finally:
            session.close()

    def revoke_family(self, family_id: str) -> None:
        """Revoke every token in this family, and drop any saved receipt.

        One UPDATE, not a paged query. A family with more rows than a page
        size would otherwise keep tokens that still work.

        ``COALESCE`` keeps a revoked-at time that was already stored.
        """
        session = self.session_factory()
        try:
            placeholder = _sql_placeholder(session)
            table_name = get_table_info(RefreshToken).name
            revoked_at = _now_naive()
            session.execute(
                f"UPDATE {table_name} SET "
                f"revoked_at = COALESCE(revoked_at, {placeholder}), "
                "receipt_access = NULL, receipt_refresh = NULL, "
                "receipt_expires_at = NULL, receipt_expires_in = NULL "
                f"WHERE family_id = {placeholder}",
                [revoked_at, family_id],
            )
            session.commit()
        finally:
            session.close()


def _increment_bucket(session: Session, bucket_name: str) -> int:
    """Add one to this bucket and return the count after the add.

    ``INSERT ... ON CONFLICT`` is a single statement. Two requests cannot
    both read 0 and both write 1. ``RETURNING`` is the count the database
    stored. SQLite uses the connection's ``execute``; PostgreSQL uses
    ``execute_returning``, which speaks psycopg's cursor.
    """
    placeholder = _sql_placeholder(session)
    table_name = get_table_info(RateLimitBucket).name
    sql = (
        f"INSERT INTO {table_name} (bucket, hits) VALUES ({placeholder}, 1) "
        f"ON CONFLICT (bucket) DO UPDATE SET hits = {table_name}.hits + 1 "
        "RETURNING hits"
    )
    if session.dialect is Dialect.SQLITE:
        cursor = session._conn.execute(sql, (bucket_name,))
        row = cursor.fetchone()
    else:
        row = session.execute_returning(sql, [bucket_name])
    hits = _first_column(row, "hits")
    if hits is None:
        return 1
    return int(hits)


def _increment_bucket_by_read_and_write(session: Session, bucket_name: str) -> int:
    """Count one hit where ``INSERT ... ON CONFLICT`` is not available.

    This can lose a hit if two requests interleave. SQLite and PostgreSQL
    do not use it.
    """
    rows = session.query(RateLimitBucket, where=[eq("bucket", bucket_name)], limit=1)
    if not rows:
        session.add(RateLimitBucket(bucket=bucket_name, hits=1))
        return 1
    hit_count = int(rows[0].hits) + 1
    session.update(rows[0], hits=hit_count)
    return hit_count


@dataclass
class OrmRateLimiter:
    """Fixed-window counter stored in ``phzyx_auth_rate_limits``.

    SQLite and PostgreSQL increment with one ``INSERT ... ON CONFLICT``
    statement. Other dialects fall back to a read-modify-write in the
    session transaction.
    """

    session_factory: SessionFactory

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Count one hit. Return True while the window is still under ``limit``.

        The bucket name is the key plus the window that contains "now", so
        the counter resets when that window ends. SQLite and PostgreSQL do
        the increment in one statement. A read then a write would lose hits
        when two requests arrive together.
        """
        window_seconds = max(1, window_seconds)
        window_index = int(time.time()) // window_seconds
        bucket_name = f"{key}:{window_seconds}:{window_index}"
        session = self.session_factory()
        try:
            if session.dialect in {Dialect.SQLITE, Dialect.POSTGRES}:
                hit_count = _increment_bucket(session, bucket_name)
            else:
                hit_count = _increment_bucket_by_read_and_write(session, bucket_name)
            session.commit()
            return hit_count <= limit
        finally:
            session.close()
