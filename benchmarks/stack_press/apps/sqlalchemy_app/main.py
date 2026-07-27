# ruff: noqa: B008
"""SQLAlchemy 2 async + FastAPI — realistic stack press."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DSN = os.environ.get(
    "BENCH_DSN",
    "postgresql+asyncpg://phzyx:phzyx@127.0.0.1:5518/bench_sa",
)

engine = create_async_engine(DSN, pool_size=20, max_overflow=20, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general", index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)


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


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="sa-bench", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "stack": "sqlalchemy+fastapi"}


@app.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    count = await session.scalar(select(func.count()).select_from(ItemRow))
    mx = await session.scalar(select(func.max(ItemRow.id)))
    return {"count": int(count or 0), "max_id": int(mx or 0)}


@app.post("/items", response_model=ItemRead, status_code=201)
async def create_item(body: ItemCreate, session: AsyncSession = Depends(get_session)) -> ItemRow:
    row = ItemRow(name=body.name, notes=body.notes, category=body.category, score=body.score)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


@app.get("/items/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)) -> ItemRow:
    row = await session.get(ItemRow, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@app.get("/items", response_model=list[ItemRead])
async def list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ItemRow]:
    stmt = select(ItemRow)
    if category:
        stmt = stmt.where(ItemRow.category == category)
    if min_score is not None:
        stmt = stmt.where(ItemRow.score >= min_score)
    if q:
        stmt = stmt.where(ItemRow.name.like(f"{q}%"))
    stmt = stmt.offset(offset).limit(limit)
    result = await session.scalars(stmt)
    return list(result.all())


@app.put("/items/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int, body: ItemUpdate, session: AsyncSession = Depends(get_session)
) -> ItemRow:
    row = await session.get(ItemRow, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return row


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)) -> None:
    row = await session.get(ItemRow, item_id)
    if row is None:
        raise HTTPException(404, "not found")
    await session.delete(row)
