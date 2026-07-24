"""Primary key validation (SS1.1.4) and composite PK API (SS1.1.5)."""

from __future__ import annotations

import pytest
from phzyx.schema import Field, Model, SchemaError, get_table_info


@pytest.mark.unit
def test_model_without_pk_raises_clear_error() -> None:
    with pytest.raises(SchemaError, match="at least one primary key"):

        class Bad(Model):
            name: str = Field()

            class Meta:
                table = "bad_no_pk"
                register = False


@pytest.mark.unit
def test_single_pk_ok() -> None:
    class Ok(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "ok_single_pk"
            register = False

    assert get_table_info(Ok).primary_key == ("id",)


@pytest.mark.unit
def test_composite_pk_via_multiple_fields() -> None:
    class Membership(Model):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True)

        class Meta:
            table = "memberships_fields"
            register = False

    info = get_table_info(Membership)
    assert info.primary_key == ("org_id", "user_id")
    assert info.columns["org_id"].primary_key is True
    assert info.columns["user_id"].primary_key is True


@pytest.mark.unit
def test_composite_pk_via_meta_list() -> None:
    class Membership(Model):
        org_id: int = Field()
        user_id: int = Field()
        role: str = Field()

        class Meta:
            table = "memberships_meta"
            primary_key = ("org_id", "user_id")
            register = False

    info = get_table_info(Membership)
    assert info.primary_key == ("org_id", "user_id")
    assert info.columns["org_id"].primary_key is True
    assert info.columns["user_id"].primary_key is True
    assert info.columns["role"].primary_key is False


@pytest.mark.unit
def test_meta_primary_key_unknown_field() -> None:
    with pytest.raises(SchemaError, match="unknown field"):

        class Bad(Model):
            id: int = Field()

            class Meta:
                table = "bad_meta_pk"
                primary_key = ("missing",)
                register = False


@pytest.mark.unit
def test_meta_primary_key_empty_raises() -> None:
    with pytest.raises(SchemaError, match="must not be empty"):

        class Bad(Model):
            id: int = Field(primary_key=True)

            class Meta:
                table = "bad_empty_meta_pk"
                primary_key = ()
                register = False


@pytest.mark.unit
def test_abstract_without_pk_allowed() -> None:
    class Mix(Model):
        class Meta:
            abstract = True

        note: str = Field()

    assert Mix.__phzyx_table__ is None
