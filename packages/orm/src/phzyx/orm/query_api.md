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
```

## Sync (mirror)

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

Filters: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in_`, `is_null`, `like`, `ilike`.  
Ordering: `asc`, `desc`.  
Keys: scalar or `dict` for composite PK on `get()`.
