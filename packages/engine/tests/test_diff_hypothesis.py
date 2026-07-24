"""Hypothesis property tests on diff safety (S6.6.1)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from phzyx.engine import DEFAULT_POLICY, diff_manifests
from phzyx.schema import ColumnDef, LogicalType, Manifest, TableDef


def _table(name: str, cols: list[str]) -> TableDef:
    columns = [
        ColumnDef(
            name=c,
            logical_type=LogicalType.INT if c == "id" else LogicalType.STR,
            primary_key=(c == "id"),
            nullable=(c != "id"),
        )
        for c in cols
    ]
    return TableDef(name=name, columns=tuple(columns), primary_key=("id",))


@given(
    extra=st.lists(
        st.sampled_from(["a", "b", "c", "d", "e"]),
        min_size=0,
        max_size=4,
        unique=True,
    )
)
@settings(max_examples=30)
def test_removing_columns_never_emits_drop_column(extra: list[str]) -> None:
    live_cols = ["id", *extra, "gone"]
    desired_cols = ["id", *extra]
    live = Manifest(tables=(_table("t", live_cols),))
    desired = Manifest(tables=(_table("t", desired_cols),))
    ops = diff_manifests(desired, live, policy=DEFAULT_POLICY)
    assert not any(o.kind == "drop_column" for o in ops)
    if "gone" in live_cols and "gone" not in desired_cols:
        assert any(o.kind == "archive_column" for o in ops)


@pytest.mark.unit
def test_hypothesis_module_importable() -> None:
    assert True
