"""Diff, policy, renamed_from, archive (SS2.2–2.3 safety)."""

from __future__ import annotations

import pytest
from phzyx.engine import DEFAULT_POLICY, PolicyError, build_plan, diff_manifests
from phzyx.schema import ColumnDef, Field, LogicalType, Manifest, Model, TableDef, build_manifest


def _empty_live() -> Manifest:
    return Manifest(tables=())


@pytest.mark.unit
def test_diff_empty_when_equal() -> None:
    class User(Model):
        id: int = Field(primary_key=True)
        email: str = Field()

        class Meta:
            table = "users"
            register = False

    desired = build_manifest([User])
    # Simulate live as same structure without indexes noise: build from desired tables
    live = Manifest(tables=desired.tables)
    plan = build_plan(desired, live)
    assert plan.empty


@pytest.mark.unit
def test_add_column_op() -> None:
    class UserV1(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "users"
            register = False

    live = build_manifest([UserV1])

    class UserV2(Model):
        id: int = Field(primary_key=True)
        email: str = Field()

        class Meta:
            table = "users"
            register = False

    desired = build_manifest([UserV2])
    ops = diff_manifests(desired, live)
    assert any(o.kind == "add_column" and o.column and o.column.name == "email" for o in ops)


@pytest.mark.unit
def test_remove_column_archives_not_drop() -> None:
    class UserV1(Model):
        id: int = Field(primary_key=True)
        nickname: str = Field()

        class Meta:
            table = "users"
            register = False

    live = build_manifest([UserV1])

    class UserV2(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "users"
            register = False

    desired = build_manifest([UserV2])
    ops = diff_manifests(desired, live, policy=DEFAULT_POLICY)
    assert any(o.kind == "archive_column" for o in ops)
    assert not any(o.kind == "drop_column" for o in ops)


@pytest.mark.unit
def test_never_drop_column_under_default_policy() -> None:
    live = Manifest(
        tables=(
            TableDef(
                name="t",
                columns=(
                    ColumnDef(
                        name="id",
                        logical_type=LogicalType.INT,
                        primary_key=True,
                        nullable=False,
                    ),
                    ColumnDef(name="gone", logical_type=LogicalType.STR),
                ),
                primary_key=("id",),
            ),
        )
    )
    desired = Manifest(
        tables=(
            TableDef(
                name="t",
                columns=(
                    ColumnDef(
                        name="id",
                        logical_type=LogicalType.INT,
                        primary_key=True,
                        nullable=False,
                    ),
                ),
                primary_key=("id",),
            ),
        )
    )
    ops = diff_manifests(desired, live)
    kinds = {o.kind for o in ops}
    assert "archive_column" in kinds
    assert "drop_column" not in kinds


@pytest.mark.unit
def test_drop_table_refused() -> None:
    live = Manifest(
        tables=(
            TableDef(
                name="old",
                columns=(ColumnDef(name="id", logical_type=LogicalType.INT, primary_key=True),),
                primary_key=("id",),
            ),
        )
    )
    desired = Manifest(tables=())
    with pytest.raises(PolicyError, match="DROP TABLE refused"):
        diff_manifests(desired, live, policy=DEFAULT_POLICY)


@pytest.mark.unit
def test_renamed_from_produces_rename() -> None:
    class V1(Model):
        id: int = Field(primary_key=True)
        name: str = Field()

        class Meta:
            table = "people"
            register = False

    live = build_manifest([V1])

    class V2(Model):
        id: int = Field(primary_key=True)
        full_name: str = Field(renamed_from="name")

        class Meta:
            table = "people"
            register = False

    desired = build_manifest([V2])
    ops = diff_manifests(desired, live)
    renames = [o for o in ops if o.kind == "rename_column"]
    assert len(renames) == 1
    assert renames[0].column_name == "name"
    assert renames[0].new_column_name == "full_name"
    assert not any(o.kind == "archive_column" and o.column_name == "name" for o in ops)


@pytest.mark.unit
def test_plan_summary() -> None:
    class User(Model):
        id: int = Field(primary_key=True)

        class Meta:
            table = "users"
            register = False

    plan = build_plan(build_manifest([User]), _empty_live())
    text = plan.summary()
    assert "Create table" in text
    assert not plan.empty
