"""db push: desired models → diff → apply (local safety defaults)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from phzyx.engine.apply_ops import apply_plan
from phzyx.engine.plan import SchemaPlan, build_plan
from phzyx.engine.policy import DEFAULT_POLICY, SchemaPolicy
from phzyx.schema.manifest import Manifest, build_manifest
from phzyx.schema.model import Model


@dataclass
class PushResult:
    plan: SchemaPlan
    applied: bool
    statements: list[str]
    production_warning: bool = False


def is_production_like_env() -> bool:
    """Heuristic: warn/block push in production-like environments."""
    env = (
        os.environ.get("PHZYX_ENV") or os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or ""
    ).lower()
    if env in {"prod", "production", "staging"}:
        return True
    return os.environ.get("PHZYX_PRODUCTION", "").lower() in {"1", "true", "yes"}


def push_schema(
    models: Sequence[type[Model]],
    connection: Any,
    adapter: Any,
    *,
    dry_run: bool = False,
    yes: bool = False,
    policy: SchemaPolicy = DEFAULT_POLICY,
    allow_production: bool = False,
) -> PushResult:
    """Diff models against live DB and optionally apply.

    Parameters
    ----------
    dry_run:
        Compute plan only; never apply.
    yes:
        Apply without interactive confirm (CLI uses this for non-interactive).
    allow_production:
        If false, production-like env refuses apply (still allows dry-run).
    """
    desired = build_manifest(models)
    live = adapter.introspect(connection)
    plan = build_plan(desired, live, policy=policy)
    prod = is_production_like_env()

    if dry_run or plan.empty:
        return PushResult(plan=plan, applied=False, statements=[], production_warning=prod)

    if prod and not allow_production:
        return PushResult(plan=plan, applied=False, statements=[], production_warning=True)

    if not yes and not dry_run:
        # Library API requires yes=True to apply (CLI prompts then passes yes).
        return PushResult(plan=plan, applied=False, statements=[], production_warning=prod)

    dialect = adapter.dialect
    statements = apply_plan(plan, connection, dialect=dialect)
    return PushResult(plan=plan, applied=True, statements=statements, production_warning=prod)


def plan_from_manifests(
    desired: Manifest,
    live: Manifest,
    *,
    policy: SchemaPolicy = DEFAULT_POLICY,
) -> SchemaPlan:
    return build_plan(desired, live, policy=policy)
