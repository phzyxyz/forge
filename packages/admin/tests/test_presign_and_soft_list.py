"""Presign upload + soft-delete list filtering."""

from __future__ import annotations

from datetime import datetime

import pytest
from phzyx.admin import AdminService, LocalStorage, infer_resource
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Note(Model):
    id: int | None = Field(default=None, primary_key=True)
    body: str = Field()
    deleted_at: datetime | None = Field(default=None)

    class Meta:
        table = "notes_soft"
        register = False


@pytest.mark.integration
@pytest.mark.sqlite
def test_soft_list_and_presign(tmp_path) -> None:
    db = tmp_path / "n.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Note], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        store = LocalStorage(tmp_path / "media")
        svc = AdminService(
            resources={"notes": infer_resource(Note)},
            session=session,
            storage=store,
        )
        a = svc.create("notes", {"body": "hi"})
        assert a["id"]
        svc.delete("notes", str(a["id"]))  # soft
        listed = svc.list("notes")
        assert listed.total == 0
        listed_all = svc.list("notes", filters={"include_deleted": "1"})
        assert listed_all.total == 1

        ps = svc.presign_upload("folder/x.txt")
        assert ps["key"] == "folder/x.txt"
        assert "url" in ps
        session.close()
    finally:
        conn.close()
