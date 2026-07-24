"""SaaS-style AdminBoard demo — users / memberships / assets (M4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from phzyx.admin.fastapi import AdminBoard  # type: ignore[import-not-found]
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, FileField, Model, Session
from phzyx.schema.types import Dialect

DB = Path(__file__).with_name("demo.db")
URL = f"sqlite:///{DB}"


class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()
    name: str = Field()

    class Meta:
        table = "users"
        register = False


class Membership(Model):
    org_id: int = Field(primary_key=True)
    user_id: int = Field(primary_key=True)
    role: str = Field(default="member")

    class Meta:
        table = "memberships"
        register = False


class Asset(Model):
    id: int = Field(primary_key=True)
    title: str = Field()
    path: str = FileField()

    class Meta:
        table = "assets"
        register = False


def session_factory() -> Session:
    conn, _ = connect(URL)
    return Session(conn, dialect=Dialect.SQLITE)


def seed() -> None:
    conn, adapter = connect(URL)
    try:
        push_schema([User, Membership, Asset], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        if session.get(User, 1) is None:
            session.add(User(id=1, email="ops@phzyx.xyz", name="Ops"))
            session.add(Membership(org_id=1, user_id=1, role="admin"))
            session.add(Asset(id=1, title="Logo", path="brand/logo.svg"))
            session.commit()
        session.close()
    finally:
        conn.close()


seed()
app = FastAPI(title="Phzyx AdminBoard demo")
AdminBoard(
    app,
    models=[User, Membership, Asset],
    session_factory=session_factory,
    theme="stellar-dark",
    storage_root=Path(__file__).with_name("media"),
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "admin": "/admin/",
        "api": "/admin/api/v1/resources",
        "docs": "/docs",
    }
