"""Manifest IR build and serialization (SS1.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.schema import (
    MANIFEST_VERSION,
    Field,
    Model,
    OnDelete,
    build_manifest,
    manifest_from_json,
    manifest_to_json,
)


@pytest.mark.unit
def test_build_manifest_single_and_composite_pk() -> None:
    class User(Model):
        id: int = Field(primary_key=True)
        email: str = Field(unique=True, index=True)

        class Meta:
            table = "users"
            register = False

    class Membership(Model):
        org_id: int = Field(primary_key=True)
        user_id: int = Field(primary_key=True, foreign_key="users.id", on_delete=OnDelete.CASCADE)

        class Meta:
            table = "memberships"
            register = False

    m = build_manifest([User, Membership])
    assert m.manifest_version == MANIFEST_VERSION
    assert m.table("users").primary_key == ("id",)
    assert m.table("memberships").primary_key == ("org_id", "user_id")
    assert any(c.unique for c in m.table("users").columns if c.name == "email")
    assert m.table("memberships").constraints[0].ref_table == "users"


@pytest.mark.unit
def test_manifest_json_roundtrip_and_golden() -> None:
    class Item(Model):
        id: int = Field(primary_key=True)
        name: str = Field()
        renamed: str = Field(renamed_from="title")

        class Meta:
            table = "items"
            register = False

    m = build_manifest([Item])
    text = manifest_to_json(m)
    restored = manifest_from_json(text)
    assert restored == m

    golden = Path(__file__).parent / "goldens" / "manifest_item.json"
    if not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text)
    assert text == golden.read_text()


@pytest.mark.unit
def test_manifest_version_constant() -> None:
    assert MANIFEST_VERSION == 1
