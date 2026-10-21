# phzyx-orm

**Not a separate PyPI project** — ships inside **`phzyx-forge`**. Use `uv add phzyx-forge`.


**Async-first** ORM sessions over Phzyx models. Prefer `AsyncSession` for app routes.
Sync `Session` mirrors the same API for scripts/CLI **and** AdminBoard’s `session_factory` today.

### Primary keys & timestamps

Single integer PK defaults to DB identity (SQLite rowid / Postgres IDENTITY /
MySQL AUTO_INCREMENT). Prefer:

```python
id: int | None = Field(default=None, primary_key=True)
created_at: datetime | None = Field(default=None, auto_now_add=True)
```

`session.add(User(email=…))` omits null AI PK and hydrates `id`. Also:
`bulk_update`, `upsert`, `soft_delete`.

## Install

```bash
uv add phzyx-forge
# import: from phzyx.orm …
```

## Async (preferred)

```python
from phzyx.orm import AsyncSession, create_async_engine, eq
from phzyx.schema.types import Dialect

engine = create_async_engine("sqlite+aiosqlite:///./app.db")

async with AsyncSession(await engine.connect(), dialect=Dialect.SQLITE) as session:
    await session.add(User(email="a@b.co"))
    rows = await session.query(User, where=[eq("email", "a@b.co")])
    page = await session.query_keyset(User, limit=50)  # deep pages without OFFSET
    await session.update_by_pk(User, 1, email="b@c.co")  # single-trip update
```

### Postgres pools (FastAPI)

`create_async_engine("postgresql+asyncpg://…")` owns an asyncpg pool.
`connect()` borrows a connection; `dispose()` closes the pool. A session from
`create_async_session` begins a transaction before the first statement, so
`commit` and `rollback` reach PostgreSQL (they are not SQLite-only).

Shut the engine down with the app (`await engine.dispose()`). Multi-worker
Uvicorn: budget `workers × pool_max` under Postgres `max_connections`.
`AsyncPostgresPool` is the explicit pool when you need min/max size.
`AsyncSession(..., read_only=True)` rejects writes, including writes hidden
in CTEs, once the transaction is open.

## Sync (mirror)

```python
from phzyx.orm import Session, create_engine, eq
from phzyx.schema.types import Dialect

engine = create_engine("sqlite:///./app.db")
with Session(engine.connect(), dialect=Dialect.SQLITE) as session:
    session.add(User(email="a@b.co"))
    session.commit()
    print(session.query(User, where=[eq("email", "a@b.co")]))
```

## File fields

Keys only in the database (never file bytes by default):

```python
from phzyx.orm import FileField, ImageField, sanitize_upload_key

class Asset(Model):
    id: int = Field(primary_key=True)
    file: str = FileField()
```

## Relations (thin)

FK as scalar fields; optional `fetch_related` / `fetch_related_async`. **Non-goals:** SQLAlchemy-style relationship graphs, lazy loading, cascade unit-of-work.

## Query API

See `src/phzyx/orm/query_api.md`.


## PostgreSQL application lifecycle (local development update)

```python
from phzyx.orm import AsyncPostgresPool

pool = AsyncPostgresPool(dsn, min_size=1, max_size=10, statement_cache_size=0)
await pool.open()  # FastAPI lifespan startup
async with pool.session() as session:
    await session.execute_native("SELECT set_config('app.tenant_id', $1, true)", "42")
    rows = await session.fetch_native("SELECT $1::jsonb AS payload", {"ok": True})
    async with session.savepoint():
        pass  # nested work rolls back independently on exception
await pool.close()  # lifespan shutdown
```

Pooled sessions begin a real transaction and commit or roll back on exit.
Borrowed connections are released to the pool, never closed by the session.
JSON/JSONB codecs use Python values by default; UUID, decimal, timestamps and
arrays retain asyncpg codecs. Use `json_codecs=False` to retain driver JSON
strings, and `init=` for additional per-connection configuration.

Direct `AsyncSession(conn, dialect=...)` retains connection ownership by default.
Its PostgreSQL context now begins a real transaction. For caller-owned
connections, use `owns_connection=False`: by default the session neither closes
the connection nor commits/rolls back its transaction. Explicit
`manage_transaction=True` owns a transaction (or a savepoint within an existing
one). `begin()` starts explicit work; use `savepoint()` for nesting. After an
explicit commit/rollback, call `begin()` before another atomic unit of work.

`fetch_native` returns dictionaries and `execute_native` returns the asyncpg
command status. They use native `$n` parameters without textual replacement;
never interpolate untrusted values or identifiers. `read_only=True` managed
sessions use a PostgreSQL read-only transaction, including for CTEs. Existing
portable CRUD builders remain a separate API and still use their legacy
placeholder conversion; their broader query migration is not completed here.

This development update is not published. PostgreSQL checks require an explicit
`PHZYX_TEST_DATABASE_URL` pointing to a disposable database.
