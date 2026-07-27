# Canonical query API (M3)

## Async (preferred)

```python
from phzyx.orm import AsyncSession, create_async_engine, eq, gte, desc

engine = create_async_engine("sqlite+aiosqlite:///./app.db")
async with AsyncSession(await engine.connect(), dialect=engine.dialect) as session:
    rows = await session.query(
        User,
        where=[eq("active", True), gte("id", 10)],
        order_by=[desc("id")],
        limit=50,
    )
    page = await session.query_keyset(User, limit=50)  # prefer over deep OFFSET
    n = await session.count(User, where=[eq("active", True)])
    await session.update_by_pk(User, 1, email="new@x.co")  # no prior SELECT
```

### Postgres + FastAPI pool (production)

```python
import asyncpg
from phzyx.orm import AsyncSession
from phzyx.schema.types import Dialect

pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)
# FastAPI Depends: acquire → AsyncSession(conn, dialect=Dialect.POSTGRES) → release
# Uvicorn: multiple workers; size pool so sum of max_size ≈ DB max connections budget
# Read-only handlers: AsyncSession(conn, dialect=…, read_only=True)
```

## Sync (mirror)

Same shape without `await`. Prefer async for app routes; sync is scripts/CLI
and AdminBoard’s `session_factory` today.

```python
from phzyx.orm import Session, create_engine, eq, gte, desc

engine = create_engine("sqlite:///./app.db")
with Session(engine.connect(), dialect=engine.dialect) as session:
    rows = session.query(
        User,
        where=[eq("active", True), gte("id", 10)],
        order_by=[desc("id")],
        limit=50,
    )
```

## Inserts and primary keys (0.1)

`session.add(instance)` inserts columns from `instance.model_dump()` — supply
`id` (or other PK fields) on the model. There is no omit-PK + DB serial path in
0.1; `add` does not populate generated keys from `lastrowid`.

Filters: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in_`, `is_null`, `like`, `ilike`.  
Ordering: `asc`, `desc`.  
Keys: scalar or `dict` for composite PK on `get()`.
