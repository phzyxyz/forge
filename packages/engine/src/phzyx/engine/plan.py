"""Schema plan: ordered ops + human summary."""

from __future__ import annotations

from dataclasses import dataclass, field

from phzyx.engine.diff import diff_manifests
from phzyx.engine.ops import SchemaOp
from phzyx.engine.policy import DEFAULT_POLICY, SchemaPolicy
from phzyx.schema.manifest import Manifest


@dataclass
class SchemaPlan:
    ops: list[SchemaOp] = field(default_factory=list)
    policy: SchemaPolicy = DEFAULT_POLICY

    @property
    def empty(self) -> bool:
        return not self.ops

    def summary(self) -> str:
        if not self.ops:
            return "No schema changes (empty plan)."
        lines = [f"Schema plan ({len(self.ops)} operation(s)):"]
        for i, op in enumerate(self.ops, 1):
            extra = f" — {op.reason}" if op.reason else ""
            lines.append(f"  {i}. {op.describe()}{extra}")
        return "\n".join(lines)

    def has_kind(self, kind: str) -> bool:
        return any(op.kind == kind for op in self.ops)


def build_plan(
    desired: Manifest,
    live: Manifest,
    *,
    policy: SchemaPolicy = DEFAULT_POLICY,
) -> SchemaPlan:
    ops = diff_manifests(desired, live, policy=policy)
    return SchemaPlan(ops=ops, policy=policy)
