"""Plan lint + TUI push confirm (S6.5 / S6.6)."""

from __future__ import annotations

import io

import pytest
from phzyx.engine import (
    SchemaOp,
    SchemaPlan,
    confirm_plan,
    lint_plan,
    render_plan_view,
)
from phzyx.schema import ColumnDef, Field, LogicalType, Manifest, Model, build_manifest


class User(Model):
    id: int = Field(primary_key=True)

    class Meta:
        table = "users"
        register = False


@pytest.mark.unit
def test_lint_blocks_drop_table() -> None:
    plan = SchemaPlan(ops=[SchemaOp(kind="drop_table", table="old")])
    result = lint_plan(plan)
    assert not result.ok
    assert any(f.code == "destructive_drop_table" for f in result.findings)


@pytest.mark.unit
def test_lint_clean_create() -> None:
    desired = build_manifest([User])
    from phzyx.engine import build_plan

    plan = build_plan(desired, Manifest(tables=()))
    assert lint_plan(plan).ok


@pytest.mark.unit
def test_tui_confirm_yes_no() -> None:
    plan = SchemaPlan(
        ops=[
            SchemaOp(
                kind="add_column",
                table="users",
                column=ColumnDef(name="n", logical_type=LogicalType.STR),
            )
        ]
    )
    assert "Phzyx schema plan" in render_plan_view(plan)
    assert confirm_plan(plan, input_stream=io.StringIO("y\n"), output_stream=io.StringIO())
    assert not confirm_plan(plan, input_stream=io.StringIO("n\n"), output_stream=io.StringIO())
