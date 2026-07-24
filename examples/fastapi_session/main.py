"""FastAPI dependency example for Phzyx AsyncSession (M3)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI
from phzyx.orm import AsyncSession, create_async_engine
from phzyx.schema.types import Dialect

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL)
app = FastAPI(title="Phzyx session example")


async def get_session() -> AsyncIterator[AsyncSession]:
    conn = await engine.connect()
    session = AsyncSession(conn, dialect=Dialect.SQLITE)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:  # noqa: B008
    _ = session
    return {"status": "ok"}
