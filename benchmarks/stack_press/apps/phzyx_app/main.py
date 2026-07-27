# ruff: noqa: B008
"""Phzyx Forge + FastAPI — realistic stack press (large table + filters)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Query
from phzyx.engine import connect, push_schema
from phzyx.orm import AsyncSession, eq, gte, like
from phzyx.schema import Field as PhField
from phzyx.schema import Model
from phzyx.schema.types import Dialect
from pydantic import BaseModel, ConfigDict, Field

DSN = os.environ.get(
    "BENCH_DSN",
    "postgresql://phzyx:phzyx@127.0.0.1:5518/bench_phzyx",
).replace("postgresql+asyncpg://", "postgresql://", 1)

DIALECT = Dialect.POSTGRES
pool: asyncpg.Pool | None = None


class Item(Model):
    id: int | None = PhField(default=None, primary_key=True)
    name: str = PhField(index=True)
    notes: str | None = PhField(default=None)
    category: str = PhField(default="general", index=True)
    score: int = PhField(default=0, index=True)

    class Meta:
        table = "items"


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    category: str = "general"
    score: int = 0


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    notes: str | None = None
    category: str | None = None
    score: int | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    notes: str | None = None
    category: str
    score: int


def _read(row: Item) -> ItemRead:
    """Build response DTO once (avoid FastAPI re-validating nested Phzyx models)."""
    return ItemRead(
        id=int(row.id),  # type: ignore[arg-type]
        name=row.name,
        notes=row.notes,
        category=row.category,
        score=row.score,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    assert pool is not None
    conn = await pool.acquire()
    session = AsyncSession(conn, dialect=DIALECT)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await pool.release(conn)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global pool
    conn, adapter = connect(DSN)
    try:
        push_schema([Item], conn, adapter, dry_run=False, yes=True, allow_production=True)
    finally:
        conn.close()
    pool = await asyncpg.create_pool(DSN, min_size=10, max_size=40, command_timeout=60)
    yield
    if pool is not None:
        await pool.close()
        pool = None


app = FastAPI(title="phzyx-bench", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "stack": "phzyx+fastapi"}


@app.get("/stats")
async def stats() -> dict[str, int]:
    assert pool is not None
    n = await pool.fetchval("SELECT COUNT(*) FROM items")
    mx = await pool.fetchval("SELECT COALESCE(MAX(id),0) FROM items")
    return {"count": int(n or 0), "max_id": int(mx or 0)}


@app.post("/items", response_model=ItemRead, status_code=201)
async def create_item(
    body: ItemCreate,
    session: AsyncSession = Depends(get_session),
) -> ItemRead:
    row = await session.add(
        Item(name=body.name, notes=body.notes, category=body.category, score=body.score)
    )
    return _read(row)


@app.get("/items/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)) -> ItemRead:
    row = await session.get(Item, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    return _read(row)


@app.get("/items", response_model=list[ItemRead])
async def list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ItemRead]:
    where = []
    if category:
        where.append(eq("category", category))
    if min_score is not None:
        where.append(gte("score", min_score))
    if q:
        where.append(like("name", f"{q}%"))
    rows = await session.query(Item, where=where, limit=limit, offset=offset)
    return [_read(r) for r in rows]


@app.put("/items/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int,
    body: ItemUpdate,
    session: AsyncSession = Depends(get_session),
) -> ItemRead:
    data = body.model_dump(exclude_unset=True)
    if not data:
        row = await session.get(Item, item_id)
        if row is None:
            raise HTTPException(404, "not found")
        return _read(row)
    # Single round-trip: UPDATE … RETURNING (no prior SELECT)
    updated = await session.update_by_pk(Item, item_id, **data)
    if updated is None:
        raise HTTPException(404, "not found")
    return _read(updated)


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)) -> None:
    row = await session.get(Item, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    await session.delete(row)
