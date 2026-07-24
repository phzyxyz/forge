"""SchemaPolicy — failsafe defaults (archive-first, refuse DROP TABLE)."""

from __future__ import annotations

from dataclasses import dataclass

from phzyx.engine.errors import PolicyError
from phzyx.engine.ops import SchemaOp


@dataclass(frozen=True, slots=True)
class SchemaPolicy:
    """Safety policy for schema plans.

    Defaults match product mandate: never bare DROP COLUMN; archive instead;
    refuse DROP TABLE unless explicitly allowed.
    """

    archive_on_remove: bool = True
    allow_drop_column: bool = False
    allow_drop_table: bool = False
    allow_drop_index: bool = True

    def filter_ops(self, ops: list[SchemaOp]) -> list[SchemaOp]:
        """Rewrite/refuse ops according to policy. Raises PolicyError if refused."""
        out: list[SchemaOp] = []
        for op in ops:
            if op.kind == "drop_column":
                if self.allow_drop_column and not self.archive_on_remove:
                    out.append(op)
                elif self.archive_on_remove:
                    out.append(
                        SchemaOp(
                            kind="archive_column",
                            table=op.table,
                            column_name=op.column_name,
                            reason="default policy archives removed columns",
                        )
                    )
                else:
                    raise PolicyError(
                        f"DROP COLUMN refused by policy for {op.table}.{op.column_name}"
                    )
            elif op.kind == "drop_table":
                if self.allow_drop_table:
                    out.append(op)
                else:
                    raise PolicyError(
                        f"DROP TABLE refused by default policy for {op.table}; "
                        f"set SchemaPolicy(allow_drop_table=True) only with explicit review"
                    )
            elif op.kind == "drop_index":
                if self.allow_drop_index:
                    out.append(op)
                # else skip silently
            else:
                out.append(op)
        return out


DEFAULT_POLICY = SchemaPolicy()
