"""Schema plan operations (Sans-I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from phzyx.schema.manifest import ColumnDef, IndexDef, TableDef

OpKind = Literal[
    "create_table",
    "add_column",
    "rename_column",
    "archive_column",
    "drop_column",
    "add_index",
    "drop_index",
    "add_foreign_key",
    "drop_table",
]


@dataclass(frozen=True, slots=True)
class SchemaOp:
    kind: OpKind
    table: str
    # optional payloads
    column: ColumnDef | None = None
    column_name: str | None = None
    new_column_name: str | None = None
    index: IndexDef | None = None
    table_def: TableDef | None = None
    reason: str = ""

    def describe(self) -> str:
        if self.kind == "create_table":
            return f"Create table {self.table}"
        if self.kind == "add_column":
            return f"Add column {self.table}.{self.column.name if self.column else '?'}"
        if self.kind == "rename_column":
            return f"Rename column {self.table}.{self.column_name} → {self.new_column_name}"
        if self.kind == "archive_column":
            return (
                f"Archive column {self.table}.{self.column_name} "
                f"(rename to safe archive name; no DROP)"
            )
        if self.kind == "drop_column":
            return f"Drop column {self.table}.{self.column_name}"
        if self.kind == "add_index":
            return f"Add index {self.index.name if self.index else '?'} on {self.table}"
        if self.kind == "drop_index":
            return f"Drop index {self.index.name if self.index else '?'} on {self.table}"
        if self.kind == "drop_table":
            return f"Drop table {self.table}"
        if self.kind == "add_foreign_key":
            return f"Add foreign key on {self.table}"
        return self.kind
