"""Unit tests for Phzyx Field DB metadata namespace (SS1.1.1)."""

from __future__ import annotations

import pytest
from phzyx.schema import (
    PHZYX_JSON_SCHEMA_KEY,
    ColumnMeta,
    Field,
    OnDelete,
    get_column_meta,
)
from pydantic import BaseModel
from pydantic import Field as PydanticField


@pytest.mark.unit
def test_field_primary_key_unique_index_on_model() -> None:
    class User(BaseModel):
        id: int = Field(primary_key=True)
        email: str = Field(unique=True, index=True)
        name: str = Field()

    id_meta = get_column_meta(User.model_fields["id"])
    email_meta = get_column_meta(User.model_fields["email"])
    name_meta = get_column_meta(User.model_fields["name"])

    assert id_meta is not None
    assert id_meta.primary_key is True
    assert email_meta is not None
    assert email_meta.unique is True
    assert email_meta.index is True
    assert name_meta is not None
    assert name_meta.primary_key is False


@pytest.mark.unit
def test_renamed_from_metadata() -> None:
    class Person(BaseModel):
        full_name: str = Field(renamed_from="name")

    meta = get_column_meta(Person.model_fields["full_name"])
    assert meta is not None
    assert meta.renamed_from == "name"


@pytest.mark.unit
def test_foreign_key_and_on_delete() -> None:
    class Order(BaseModel):
        id: int = Field(primary_key=True)
        user_id: int = Field(foreign_key="users.id", on_delete=OnDelete.CASCADE)

    meta = get_column_meta(Order.model_fields["user_id"])
    assert meta is not None
    assert meta.foreign_key == "users.id"
    assert meta.on_delete == OnDelete.CASCADE


@pytest.mark.unit
def test_on_delete_without_foreign_key_raises() -> None:
    with pytest.raises(ValueError, match="on_delete requires foreign_key"):
        Field(on_delete=OnDelete.CASCADE)


@pytest.mark.unit
def test_db_type_and_server_default() -> None:
    class Row(BaseModel):
        payload: dict = Field(db_type="jsonb", server_default="'{}'::jsonb")

    meta = get_column_meta(Row.model_fields["payload"])
    assert meta is not None
    assert meta.db_type == "jsonb"
    assert meta.server_default == "'{}'::jsonb"


@pytest.mark.unit
def test_admin_and_file_hints() -> None:
    class Asset(BaseModel):
        id: int = Field(primary_key=True)
        secret: str = Field(admin_exclude=True, admin_hidden=True)
        path: str = Field(file_kind="image", admin_readonly=True)

    secret = get_column_meta(Asset.model_fields["secret"])
    path = get_column_meta(Asset.model_fields["path"])
    assert secret is not None
    assert secret.admin_exclude is True
    assert secret.admin_hidden is True
    assert path is not None
    assert path.file_kind == "image"
    assert path.admin_readonly is True


@pytest.mark.unit
def test_invalid_file_kind_raises() -> None:
    with pytest.raises(ValueError, match="file_kind"):
        Field(file_kind="blob")  # type: ignore[arg-type]


@pytest.mark.unit
def test_empty_renamed_from_raises() -> None:
    with pytest.raises(ValueError, match="renamed_from"):
        Field(renamed_from="  ")


@pytest.mark.unit
def test_get_column_meta_none_for_plain_pydantic_field() -> None:
    class Plain(BaseModel):
        x: int = PydanticField(default=1)

    assert get_column_meta(Plain.model_fields["x"]) is None


@pytest.mark.unit
def test_column_meta_roundtrip_dict() -> None:
    original = ColumnMeta(
        primary_key=True,
        foreign_key="t.id",
        on_delete=OnDelete.SET_NULL,
        renamed_from="old",
        archive_on_remove=True,
        file_kind="file",
    )
    restored = ColumnMeta.from_dict(original.to_dict())
    assert restored == original


@pytest.mark.unit
def test_json_schema_extra_merges_phzyx_key() -> None:
    class Item(BaseModel):
        code: str = Field(unique=True, json_schema_extra={"title_hint": "SKU"})

    info = Item.model_fields["code"]
    assert isinstance(info.json_schema_extra, dict)
    assert info.json_schema_extra["title_hint"] == "SKU"
    assert PHZYX_JSON_SCHEMA_KEY in info.json_schema_extra
    meta = get_column_meta(info)
    assert meta is not None
    assert meta.unique is True


@pytest.mark.unit
def test_callable_json_schema_extra_rejected() -> None:
    with pytest.raises(TypeError, match="callable"):
        Field(json_schema_extra=lambda schema: schema)


@pytest.mark.unit
def test_field_default_value_still_works() -> None:
    class Config(BaseModel):
        enabled: bool = Field(default=True, index=True)

    assert Config().enabled is True
    meta = get_column_meta(Config.model_fields["enabled"])
    assert meta is not None
    assert meta.index is True


@pytest.mark.unit
def test_composite_pk_flags_on_multiple_fields() -> None:
    """SS1.1.1 only attaches flags; Model validation of ≥1 PK is SS1.1.4."""

    class Membership(BaseModel):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True)

    assert get_column_meta(Membership.model_fields["org_id"]).primary_key is True  # type: ignore[union-attr]
    assert get_column_meta(Membership.model_fields["user_id"]).primary_key is True  # type: ignore[union-attr]
