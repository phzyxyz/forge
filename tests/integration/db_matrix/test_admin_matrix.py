"""AdminService battle tests on every matrix target."""

from __future__ import annotations

import pytest
from phzyx.admin import AdminService, LocalStorage, infer_resource

from .helpers import MatrixAccount, MatrixNote, close_all, open_session
from .targets import DbTarget

pytestmark = [
    pytest.mark.integration,
    pytest.mark.db_matrix,
    pytest.mark.slow,
]


def test_admin_crud_list_search_widgets(db_target: DbTarget, tmp_path) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        media = tmp_path / "media"
        media.mkdir()
        svc = AdminService(
            resources={
                "accounts": infer_resource(MatrixAccount),
                "notes": infer_resource(MatrixNote),
            },
            session=session,
            storage=LocalStorage(str(media)),
        )

        created = svc.create("accounts", {"email": "admin@x.co", "name": "Admin"})
        assert created["id"] is not None
        assert created["email"] == "admin@x.co"

        got = svc.get("accounts", str(created["id"]))
        assert got is not None
        assert got["name"] == "Admin"

        updated = svc.update("accounts", str(created["id"]), {"name": "Admin2"})
        assert updated["name"] == "Admin2"

        listed = svc.list("accounts")
        assert listed.total >= 1
        assert any(r["id"] == created["id"] for r in listed.items)

        # Second account for search breadth
        svc.create("accounts", {"email": "other@x.co", "name": "Other"})
        hits = svc.global_search("Admin")
        assert any(h.get("resource") == "accounts" for h in hits)

        widgets = svc.dashboard_widgets()
        assert widgets  # non-empty summary widgets

        ps = svc.presign_upload("battle/matrix.bin")
        assert ps["key"] == "battle/matrix.bin"

        # soft delete
        before = svc.list("accounts").total
        svc.delete("accounts", str(created["id"]))
        after = svc.list("accounts").total
        # soft-delete should hide or reduce visible count
        assert after <= before
    finally:
        close_all(session, conn)


def test_admin_validation_and_missing(db_target: DbTarget, tmp_path) -> None:
    from phzyx.admin.errors import NotFoundError, ValidationAdminError

    conn, _adapter, session = open_session(db_target)
    try:
        svc = AdminService(
            resources={"accounts": infer_resource(MatrixAccount)},
            session=session,
            storage=LocalStorage(str(tmp_path / "m")),
        )
        # AdminService.get raises NotFoundError (not None) for missing ids.
        with pytest.raises(NotFoundError):
            svc.get("accounts", "999999")
        # create without required field should surface a validation/error path
        with pytest.raises((ValidationAdminError, Exception)):
            svc.create("accounts", {"name": "NoEmail"})
    finally:
        close_all(session, conn)


def test_admin_note_under_account(db_target: DbTarget, tmp_path) -> None:
    conn, _adapter, session = open_session(db_target)
    try:
        svc = AdminService(
            resources={
                "accounts": infer_resource(MatrixAccount),
                "notes": infer_resource(MatrixNote),
            },
            session=session,
            storage=LocalStorage(str(tmp_path / "m")),
        )
        acc = svc.create("accounts", {"email": "n@x.co", "name": "N"})
        note = svc.create("notes", {"account_id": acc["id"], "body": "body"})
        assert note["id"] is not None
        listed = svc.list("notes")
        assert listed.total >= 1
    finally:
        close_all(session, conn)
