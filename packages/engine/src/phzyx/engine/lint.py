"""Migration / plan lint — Atlas-like destructive guards for CI."""

from __future__ import annotations

from dataclasses import dataclass

from phzyx.engine.ops import SchemaOp
from phzyx.engine.plan import SchemaPlan


@dataclass(frozen=True, slots=True)
class LintFinding:
    severity: str  # error | warning
    code: str
    message: str
    op_kind: str | None = None


@dataclass
class LintResult:
    findings: list[LintFinding]

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def summary(self) -> str:
        if not self.findings:
            return "lint: clean"
        lines = [f"lint: {len(self.findings)} finding(s)"]
        for f in self.findings:
            lines.append(f"  [{f.severity}] {f.code}: {f.message}")
        return "\n".join(lines)


def lint_plan(
    plan: SchemaPlan,
    *,
    allow_drop_column: bool = False,
    allow_drop_table: bool = False,
    allow_archive: bool = True,
) -> LintResult:
    """CI-friendly destructive policy checks on a SchemaPlan."""
    findings: list[LintFinding] = []
    for op in plan.ops:
        findings.extend(
            _lint_op(
                op,
                allow_drop_column=allow_drop_column,
                allow_drop_table=allow_drop_table,
                allow_archive=allow_archive,
            )
        )
    return LintResult(findings=findings)


def _lint_op(
    op: SchemaOp,
    *,
    allow_drop_column: bool,
    allow_drop_table: bool,
    allow_archive: bool,
) -> list[LintFinding]:
    out: list[LintFinding] = []
    if op.kind == "drop_column" and not allow_drop_column:
        out.append(
            LintFinding(
                "error",
                "destructive_drop_column",
                f"DROP COLUMN on {op.table}.{op.column_name} is blocked by lint",
                op.kind,
            )
        )
    if op.kind == "drop_table" and not allow_drop_table:
        out.append(
            LintFinding(
                "error",
                "destructive_drop_table",
                f"DROP TABLE {op.table} is blocked by lint",
                op.kind,
            )
        )
    if op.kind == "archive_column" and not allow_archive:
        out.append(
            LintFinding(
                "warning",
                "archive_column",
                f"archive column {op.table}.{op.column_name}",
                op.kind,
            )
        )
    if op.kind == "drop_table":
        out.append(
            LintFinding(
                "warning",
                "review_drop_table",
                f"manual review recommended for drop table {op.table}",
                op.kind,
            )
        )
    if op.kind == "rename_column":
        out.append(
            LintFinding(
                "warning",
                "review_rename_column",
                f"review rename {op.table}.{op.column_name} → {op.new_column_name}",
                op.kind,
            )
        )
    return out


def lint_exit_code(result: LintResult) -> int:
    """Process exit code for CI (0 clean, 1 errors)."""
    return 0 if result.ok else 1


def assert_lint_clean(result: LintResult) -> None:
    """Raise PolicyError-like RuntimeError if lint has errors (CI helper)."""
    if not result.ok:
        raise RuntimeError(result.summary())
