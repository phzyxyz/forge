"""Preset manifests for ``phzyx new``.

Each preset is a plain dict of features and dependency names. Layouts are
selected separately via ``--layout`` (see :mod:`phzyx.cli.new`).
"""

from __future__ import annotations

from typing import Any

# Feature flags + uv dependency names. Auth/admin modules are scaffolded
# when the corresponding flag is true (normal+).

PRESETS: dict[str, dict[str, Any]] = {
    "minimal": {
        "description": "schema + orm + FastAPI hello (learning / libraries)",
        "packages": [
            "phzyx-schema",
            "phzyx-orm",
            "phzyx-engine",
            "fastapi",
            "uvicorn[standard]>=0.32",
        ],
        "auth": False,
        "admin": False,
        "docker": False,
        "env_example": True,
    },
    "normal": {
        "description": "minimal + phzyx-auth cookie session recipe",
        "packages": [
            "phzyx-schema",
            "phzyx-orm",
            "phzyx-engine",
            "phzyx-auth[fastapi]",
            "fastapi",
            "uvicorn[standard]>=0.32",
        ],
        "auth": True,
        "admin": False,
        "docker": False,
        "env_example": True,
    },
    "max": {
        "description": "normal + AdminBoard + production-oriented defaults",
        "packages": [
            "phzyx-schema",
            "phzyx-orm",
            "phzyx-engine",
            "phzyx-auth[fastapi]",
            "phzyx-admin-fastapi",
            "fastapi",
            "uvicorn[standard]>=0.32",
        ],
        "auth": True,
        "admin": True,
        "docker": False,
        "env_example": True,
    },
    "full": {
        "description": "max + docker-compose + .env.example extras",
        "packages": [
            "phzyx-schema",
            "phzyx-orm",
            "phzyx-engine",
            "phzyx-auth[fastapi]",
            "phzyx-admin-fastapi",
            "fastapi",
            "uvicorn[standard]>=0.32",
        ],
        "auth": True,
        "admin": True,
        "docker": True,
        "env_example": True,
    },
}

DEFAULT_PRESET = "normal"
PRESET_NAMES = tuple(PRESETS.keys())

# Layout ids accepted by ``phzyx new --layout``
LAYOUT_NAMES = ("flat", "mvc", "clean", "phzyx-app")
DEFAULT_LAYOUT = "flat"


def get_preset(name: str) -> dict[str, Any]:
    """Return a copy of the named preset or raise ``KeyError``."""
    key = name.lower().strip()
    if key not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; choose one of: {', '.join(PRESET_NAMES)}")
    return dict(PRESETS[key])
