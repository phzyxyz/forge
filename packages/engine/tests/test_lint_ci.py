"""Migration lint CI helpers."""

from __future__ import annotations

import pytest
from phzyx.engine.lint import assert_lint_clean, lint_exit_code, lint_plan
from phzyx.engine.ops import SchemaOp
from phzyx.engine.plan import SchemaPlan


@pytest.mark.unit
def test_lint_blocks_drop_and_exit_code() -> None:
    plan = SchemaPlan(
        ops=[
            SchemaOp(kind="drop_table", table="users"),
            SchemaOp(kind="drop_column", table="users", column_name="email"),
        ]
    )
    r = lint_plan(plan)
    assert not r.ok
    assert lint_exit_code(r) == 1
    with pytest.raises(RuntimeError):
        assert_lint_clean(r)

    clean = lint_plan(SchemaPlan(ops=[SchemaOp(kind="add_index", table="users")]))
    assert clean.ok
    assert lint_exit_code(clean) == 0
