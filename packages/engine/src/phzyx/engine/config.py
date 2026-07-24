"""Load engine config from env / optional phzyx.toml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EngineConfig:
    database_url: str | None = None
    models: str | None = None  # dotted path or module:attr
    migrations_dir: str = "migrations"


def load_config(*, cwd: str | Path | None = None) -> EngineConfig:
    """Resolve config: env overrides file."""
    base = Path(cwd or Path.cwd())
    file_url = None
    file_models = None
    file_migrations = "migrations"
    toml_path = base / "phzyx.toml"
    if toml_path.is_file():
        data = _parse_simple_toml(toml_path.read_text(encoding="utf-8"))
        db = data.get("database") or {}
        file_url = db.get("url")
        file_models = db.get("models")
        file_migrations = db.get("migrations_dir") or data.get("migrations_dir") or "migrations"

    return EngineConfig(
        database_url=os.environ.get("PHZYX_DATABASE_URL") or file_url,
        models=os.environ.get("PHZYX_MODELS") or file_models,
        migrations_dir=os.environ.get("PHZYX_MIGRATIONS_DIR") or file_migrations,
    )


def _parse_simple_toml(text: str) -> dict:
    """Minimal TOML subset for phzyx.toml without extra deps."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    return tomllib.loads(text)
