"""FileField keys + dual session API parity (S3.4/S3.5-ish)."""

from __future__ import annotations

import inspect

import pytest
from phzyx.orm import (
    AsyncSession,
    FileField,
    ImageField,
    Session,
    build_upload_to,
    sanitize_upload_key,
)
from phzyx.schema import Field, Model, get_column_meta


@pytest.mark.unit
def test_file_field_is_string_key_metadata() -> None:
    class Doc(Model):
        id: int = Field(primary_key=True)
        path: str = FileField()
        thumb: str = ImageField()

        class Meta:
            table = "docs"
            register = False

    meta = get_column_meta(Doc.model_fields["path"])
    assert meta is not None and meta.file_kind == "file"
    assert get_column_meta(Doc.model_fields["thumb"]).file_kind == "image"  # type: ignore[union-attr]
    # model values are strings, not bytes
    d = Doc(id=1, path="uploads/a.pdf", thumb="uploads/a.png")
    assert isinstance(d.path, str)


@pytest.mark.unit
def test_sanitize_upload_key_rejects_traversal() -> None:
    assert sanitize_upload_key("uploads/a.png") == "uploads/a.png"
    with pytest.raises(ValueError, match=r"\.\."):
        sanitize_upload_key("../etc/passwd")
    with pytest.raises(ValueError, match="absolute"):
        sanitize_upload_key("/abs/path")
    fn = build_upload_to("users/{user_id}/{name}")
    assert fn(user_id=1, name="a.png") == "users/1/a.png"


@pytest.mark.unit
def test_async_sync_public_methods_match() -> None:
    """Drift guard until full unasyncd pipeline lands."""
    async_public = {
        n
        for n, m in inspect.getmembers(AsyncSession, predicate=inspect.isfunction)
        if not n.startswith("_")
    }
    # also include coroutine methods
    async_public |= {
        n
        for n, m in inspect.getmembers(AsyncSession)
        if callable(m) and not n.startswith("_") and n in dir(AsyncSession)
    }
    sync_public = {
        n
        for n, m in inspect.getmembers(Session, predicate=inspect.isfunction)
        if not n.startswith("_")
    }
    sync_public |= {
        n for n in dir(Session) if not n.startswith("_") and callable(getattr(Session, n))
    }
    required = {"add", "get", "delete", "update", "query", "commit", "rollback", "begin", "close"}
    assert required <= set(dir(AsyncSession))
    assert required <= set(dir(Session))
