"""Unit tests for Phzyx Model base and __phzyx_table__ (SS1.1.2)."""

from __future__ import annotations

import pytest
from phzyx.schema import Field, Model, camel_to_snake, get_table_info
from pydantic import ValidationError


@pytest.mark.unit
def test_camel_to_snake() -> None:
    assert camel_to_snake("User") == "user"
    assert camel_to_snake("UserProfile") == "user_profile"
    assert camel_to_snake("HTTPServer") == "http_server"


@pytest.mark.unit
def test_default_table_name_from_class() -> None:
    class UserProfile(Model):
        id: int = Field(primary_key=True)

    assert UserProfile.__phzyx_table__ is not None
    assert UserProfile.__phzyx_table__.name == "user_profile"
    assert UserProfile.__phzyx_table__.schema_name is None


@pytest.mark.unit
def test_meta_table_and_schema() -> None:
    class Account(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "accounts"
            schema = "app"

    info = get_table_info(Account)
    assert info.name == "accounts"
    assert info.schema_name == "app"
    assert info.qualified_name == "app.accounts"


@pytest.mark.unit
def test_subclass_kwargs_override_meta() -> None:
    class Item(Model, table="catalog_items", schema="shop"):
        id: int = Field(primary_key=True)

        class Meta:
            table = "ignored"
            schema = "ignored"

    info = get_table_info(Item)
    assert info.name == "catalog_items"
    assert info.schema_name == "shop"


@pytest.mark.unit
def test_columns_and_primary_key_collection() -> None:
    class Membership(Model):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True)
        role: str = Field(index=True)

    info = get_table_info(Membership)
    assert info.primary_key == ("org_id", "user_id")
    assert set(info.columns) == {"org_id", "user_id", "role"}
    assert info.columns["role"].index is True
    assert info.columns["org_id"].primary_key is True


@pytest.mark.unit
def test_plain_annotation_gets_default_column_meta() -> None:
    class Note(Model):
        id: int = Field(primary_key=True)
        body: str

    info = get_table_info(Note)
    assert "body" in info.columns
    assert info.columns["body"].primary_key is False


@pytest.mark.unit
def test_abstract_model_has_no_table() -> None:
    class Timestamped(Model):
        class Meta:
            abstract = True

        id: int = Field(primary_key=True)

    assert Timestamped.__phzyx_table__ is None
    with pytest.raises(TypeError, match="no __phzyx_table__"):
        get_table_info(Timestamped)


@pytest.mark.unit
def test_concrete_subclass_of_abstract_builds_table() -> None:
    class Timestamped(Model):
        class Meta:
            abstract = True

        id: int = Field(primary_key=True)

    class Event(Timestamped):
        name: str = Field()

        class Meta:
            table = "events"

    info = get_table_info(Event)
    assert info.name == "events"
    assert "id" in info.columns and "name" in info.columns
    assert info.primary_key == ("id",)


@pytest.mark.unit
def test_model_validation_still_works() -> None:
    class User(Model):
        id: int = Field(primary_key=True)
        email: str = Field(unique=True)

    user = User(id=1, email="a@b.co")
    assert user.email == "a@b.co"
    assert get_table_info(user).name == "user"
    with pytest.raises(ValidationError):
        User(id="x", email="a@b.co")  # type: ignore[arg-type]


@pytest.mark.unit
def test_orm_reexport() -> None:
    from phzyx.orm import Field as OrmField
    from phzyx.orm import Model as OrmModel

    class Thing(OrmModel, table="things"):
        id: int = OrmField(primary_key=True)

    assert Thing.__phzyx_table__ is not None
    assert Thing.__phzyx_table__.name == "things"


@pytest.mark.unit
def test_model_qualname_recorded() -> None:
    class Widget(Model):
        id: int = Field(primary_key=True)

    assert "Widget" in get_table_info(Widget).model_qualname
