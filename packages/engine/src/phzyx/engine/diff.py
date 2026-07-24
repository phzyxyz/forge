"""Sans-I/O schema diff: desired Manifest vs live Manifest → ops."""

from __future__ import annotations

from phzyx.engine.ops import SchemaOp
from phzyx.engine.policy import DEFAULT_POLICY, SchemaPolicy
from phzyx.schema.manifest import ColumnDef, Manifest, TableDef


def diff_manifests(
    desired: Manifest,
    live: Manifest,
    *,
    policy: SchemaPolicy = DEFAULT_POLICY,
) -> list[SchemaOp]:
    """Compute schema operations to move live → desired under policy."""
    desired_tables = {t.qualified_name: t for t in desired.tables}
    live_tables = {t.qualified_name: t for t in live.tables}

    ops: list[SchemaOp] = []

    # Tables to create
    for qname, table in desired_tables.items():
        if qname not in live_tables:
            ops.append(SchemaOp(kind="create_table", table=table.name, table_def=table))

    # Tables only in live → drop (policy may refuse)
    for qname, table in live_tables.items():
        if qname not in desired_tables:
            ops.append(SchemaOp(kind="drop_table", table=table.name))

    # Column-level for tables in both
    for qname, d_table in desired_tables.items():
        if qname not in live_tables:
            continue
        l_table = live_tables[qname]
        ops.extend(_diff_table(d_table, l_table))

    return policy.filter_ops(_order_ops(ops))


def _diff_table(desired: TableDef, live: TableDef) -> list[SchemaOp]:
    ops: list[SchemaOp] = []
    d_cols = {c.name: c for c in desired.columns}
    l_cols = {c.name: c for c in live.columns}

    # renamed_from: desired has new name with renamed_from=old, live has old not new
    renames: dict[str, str] = {}  # old -> new
    for name, col in d_cols.items():
        if col.renamed_from and col.renamed_from in l_cols and name not in l_cols:
            renames[col.renamed_from] = name
            ops.append(
                SchemaOp(
                    kind="rename_column",
                    table=desired.name,
                    column_name=col.renamed_from,
                    new_column_name=name,
                    column=col,
                    reason="Field(renamed_from=...)",
                )
            )

    for name, col in d_cols.items():
        if name in renames.values():
            continue
        if name not in l_cols:
            # not a rename target that already handled
            if any(new == name for new in renames.values()):
                continue
            ops.append(SchemaOp(kind="add_column", table=desired.name, column=col))

    for name in l_cols:
        if name in renames:
            continue  # old name handled by rename
        if name not in d_cols:
            ops.append(
                SchemaOp(
                    kind="drop_column",
                    table=desired.name,
                    column_name=name,
                    column=l_cols[name],
                )
            )

    # indexes: add missing desired indexes by name+columns
    live_idx = {(i.name, i.columns, i.unique) for i in live.indexes}
    for idx in desired.indexes:
        key = (idx.name, idx.columns, idx.unique)
        if key not in live_idx and not any(
            i.columns == idx.columns and i.unique == idx.unique for i in live.indexes
        ):
            ops.append(SchemaOp(kind="add_index", table=desired.name, index=idx))

    return ops


def _order_ops(ops: list[SchemaOp]) -> list[SchemaOp]:
    """FK-safe-ish ordering: create tables, add columns, renames, archives, indexes, drops."""
    priority = {
        "create_table": 10,
        "add_column": 20,
        "rename_column": 30,
        "add_foreign_key": 40,
        "add_index": 50,
        "archive_column": 60,
        "drop_index": 70,
        "drop_column": 80,
        "drop_table": 90,
    }
    return sorted(ops, key=lambda o: (priority.get(o.kind, 50), o.table, o.kind))


def columns_equal_for_diff(a: ColumnDef, b: ColumnDef) -> bool:
    """Compare columns ignoring admin-only fields."""
    return (
        a.name == b.name
        and a.logical_type == b.logical_type
        and a.nullable == b.nullable
        and a.primary_key == b.primary_key
    )
