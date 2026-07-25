# phzyx-orm

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
uv add phzyx-orm
# or: pip install phzyx-orm
uv add 'phzyx-orm[sqlite]'     # aiosqlite
uv add 'phzyx-orm[postgres]'   # asyncpg + psycopg
uv add 'phzyx-orm[mysql]'      # pymysql
```

## Async (preferred)

```python
from phzyx.orm import AsyncSession, create_async_engine, eq
from phzyx.schema.types import Dialect

engine = create_async_engine("sqlite+aiosqlite:///./app.db")

async with AsyncSession(await engine.connect(), dialect=Dialect.SQLITE) as session:
    await session.add(User(email="a@b.co"))
    rows = await session.query(User, where=[eq("email", "a@b.co")])
```

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
