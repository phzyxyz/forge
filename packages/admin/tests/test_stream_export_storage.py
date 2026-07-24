"""Streaming export + multi-cloud storage (S5.2 / S5.8)."""

from __future__ import annotations

import pytest
from phzyx.admin import (
    EXCEL_MAX_ROWS,
    MediaLibrary,
    MemoryStorage,
    S3CompatibleStorage,
    export_xlsx,
    infer_resource,
    stream_csv,
    stream_jsonl,
)
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session
from phzyx.schema.types import Dialect


class Item(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    secret: str = Field(admin_exclude=True, default="hide")

    class Meta:
        table = "items"
        register = False


@pytest.mark.unit
def test_stream_csv_jsonl_excludes_secrets() -> None:
    res = infer_resource(Item)
    rows = [{"id": 1, "name": "a", "secret": "nope"}, {"id": 2, "name": "b", "secret": "x"}]
    csv_text = "".join(stream_csv(res, rows))
    assert "name" in csv_text and "a" in csv_text
    assert "secret" not in csv_text and "nope" not in csv_text
    jsonl = "".join(stream_jsonl(res, rows))
    assert "nope" not in jsonl
    assert EXCEL_MAX_ROWS == 100_000


@pytest.mark.unit
def test_excel_export_capped() -> None:
    res = infer_resource(Item)
    rows = [{"id": i, "name": f"n{i}", "secret": "s"} for i in range(5)]
    data = export_xlsx(res, rows)
    assert data[:2] == b"PK"  # zip/xlsx


@pytest.mark.unit
def test_s3_compatible_memory_client_and_media_library() -> None:
    class FakeS3:
        def __init__(self) -> None:
            self.obj: dict[str, bytes] = {}

        def put_object(self, **kw):
            self.obj[kw["Key"]] = kw["Body"]

        def get_object(self, **kw):
            return {"Body": type("B", (), {"read": lambda self: self.obj[kw["Key"]]})()}

        def delete_object(self, **kw):
            self.obj.pop(kw["Key"], None)

        def head_object(self, **kw):
            if kw["Key"] not in self.obj:
                raise KeyError(kw["Key"])
            return {}

        def generate_presigned_url(self, **kw):
            return f"https://example.test/{kw['Params']['Key']}?sig=1"

    fake = FakeS3()

    # bind read correctly
    def get_object(**kw):
        key = kw["Key"]
        body = fake.obj[key]

        class B:
            def read(self_inner):
                return body

        return {"Body": B()}

    fake.get_object = get_object  # type: ignore[method-assign]

    store = S3CompatibleStorage(bucket="b", client=fake, public_base_url="https://cdn.test/")
    assert store.save("a/b.txt", b"hello") == "a/b.txt"
    assert store.open("a/b.txt") == b"hello"
    assert store.exists("a/b.txt")
    assert store.url("a/b.txt") == "https://cdn.test/a/b.txt"
    assert "sig=1" in store.presign("a/b.txt")

    lib = MediaLibrary(storage=MemoryStorage())
    item = lib.add("logo.svg", b"<svg/>", folder="brand")
    assert item.key.endswith("logo.svg")
    assert lib.attach_key(item.key) == item.key
    assert any(i.key == item.key for i in lib.list_folder("brand"))


@pytest.mark.integration
@pytest.mark.sqlite
def test_admin_list_keyset_cursor(tmp_path) -> None:
    from phzyx.admin import AdminService, infer_resource

    db = tmp_path / "a.db"
    conn, adapter = connect(f"sqlite:///{db}")
    try:
        push_schema([Item], conn, adapter, yes=True)
        session = Session(conn, dialect=Dialect.SQLITE)
        for i in range(1, 8):
            session.add(Item(id=i, name=f"n{i}"))
        session.commit()
        svc = AdminService(resources={"items": infer_resource(Item)}, session=session)
        p1 = svc.list("items", page_size=3, pagination="keyset")
        assert p1.has_more and p1.next_cursor
        p2 = svc.list("items", page_size=3, cursor=p1.next_cursor, pagination="keyset")
        assert p2.items[0]["id"] > p1.items[-1]["id"]
        # stream export
        _media, body = svc.export_stream("items", fmt="csv")
        text = body.decode() if isinstance(body, (bytes, bytearray)) else "".join(body)
        assert "n1" in text
        session.close()
    finally:
        conn.close()
