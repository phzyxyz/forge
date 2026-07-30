"""TUI / interactive push plan approval (no heavy TUI dep required)."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any, TextIO

from phzyx.engine.plan import SchemaPlan
from phzyx.engine.push import PushResult, push_schema
from phzyx.schema.model import Model


def render_plan_view(plan: SchemaPlan) -> str:
    """Human plan view for TUI / terminal."""
    lines = [
        "┌─ Phzyx schema plan ─────────────────────────────",
        f"│ operations: {len(plan.ops)}",
        "├─────────────────────────────────────────────────",
    ]
    if plan.empty:
        lines.append("│ (empty — no changes)")
    else:
        for i, op in enumerate(plan.ops, 1):
            lines.append(f"│ {i:2}. {op.describe()}")
            if op.reason:
                lines.append(f"│     reason: {op.reason}")
    lines.append("└─────────────────────────────────────────────────")
    return "\n".join(lines)


def confirm_plan(
    plan: SchemaPlan,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> bool:
    """Keyboard confirm/abort. Returns True if user approves apply."""
    inp = input_stream or sys.stdin
    out = output_stream or sys.stdout
    out.write(render_plan_view(plan) + "\n")
    if plan.empty:
        out.write("Nothing to apply.\n")
        return False
    out.write("Apply this plan? [y/N] ")
    out.flush()
    try:
        answer = inp.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        out.write("\nAborted.\n")
        out.flush()
        return False
    if answer == "" and not getattr(inp, "isatty", lambda: False)():
        # Non-interactive empty → safe no
        return False
    return answer in {"y", "yes"}


def push_with_tui(
    models: Sequence[type[Model]],
    connection: Any,
    adapter: Any,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    allow_production: bool = False,
) -> PushResult:
    """Dry-run plan, prompt, then apply if confirmed."""
    preview = push_schema(
        models,
        connection,
        adapter,
        dry_run=True,
        yes=False,
        allow_production=allow_production,
    )
    if not confirm_plan(preview.plan, input_stream=input_stream, output_stream=output_stream):
        out = output_stream or sys.stdout
        out.write("Aborted.\n")
        return PushResult(
            plan=preview.plan,
            applied=False,
            statements=[],
            production_warning=preview.production_warning,
        )
    return push_schema(
        models,
        connection,
        adapter,
        dry_run=False,
        yes=True,
        allow_production=allow_production,
    )
