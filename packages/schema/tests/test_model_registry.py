"""Unit tests for the model registry (SS1.1.3)."""

from __future__ import annotations

import pytest
from phzyx.schema import (
    Field,
    Model,
    ModelRegistry,
    RegistryError,
    get_registry,
    get_table_info,
    register_model,
    unregister_model,
)


@pytest.mark.unit
def test_auto_register_on_model_definition() -> None:
    class User(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "reg_users"

    registry = get_registry()
    assert registry.contains(User)
    assert registry.get_by_table("reg_users") is User
    assert registry.get(get_table_info(User).model_qualname) is User
    assert User in registry.models()


@pytest.mark.unit
def test_meta_register_false_skips_auto_register() -> None:
    class Ephemeral(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "ephemeral_rows"
            register = False

    assert not get_registry().contains(Ephemeral)
    register_model(Ephemeral)
    assert get_registry().contains(Ephemeral)
    unregister_model(Ephemeral)
    assert not get_registry().contains(Ephemeral)


@pytest.mark.unit
def test_duplicate_table_raises() -> None:
    class A(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "same_table"
            register = False

    class B(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "same_table"
            register = False

    register_model(A)
    with pytest.raises(RegistryError, match="already registered"):
        register_model(B)


@pytest.mark.unit
def test_schema_qualified_table_lookup() -> None:
    class TenantUser(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "users"
            schema = "tenant"

    reg = get_registry()
    assert reg.get_by_table("users", schema="tenant") is TenantUser
    with pytest.raises(RegistryError):
        reg.get_by_table("users")


@pytest.mark.unit
def test_abstract_not_registered() -> None:
    class Base(Model):
        class Meta:
            abstract = True

        id: int = Field(primary_key=True)

    assert len(get_registry()) == 0


@pytest.mark.unit
def test_isolated_registry_instance() -> None:
    local = ModelRegistry()

    class Widget(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "widgets"
            register = False

    local.register(Widget)
    assert local.contains(Widget)
    assert not get_registry().contains(Widget)
    assert "widgets" in local.tables()
    local.clear()
    assert len(local) == 0


@pytest.mark.unit
def test_replace_allows_reregister_same_table() -> None:
    class V1(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "versioned"
            register = False

    class V2(Model):
        id: int = Field(primary_key=True)
        name: str = Field()

        class Meta:
            table = "versioned"
            register = False

    reg = get_registry()
    reg.register(V1)
    reg.register(V2, replace=True)
    assert reg.get_by_table("versioned") is V2
