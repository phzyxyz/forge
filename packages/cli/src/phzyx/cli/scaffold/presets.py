"""Preset resolution for forge scaffold."""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "minimal": {
        "description": "schema + orm + async FastAPI sample (no auth/admin)",
        "auth": False,
        "admin": False,
        "docker": False,
        "use_forge_meta": False,
    },
    "normal": {
        "description": "async app + phzyx-auth",
        "auth": True,
        "admin": False,
        "docker": False,
        "use_forge_meta": True,
    },
    "max": {
        "description": "async app + auth + AdminBoard (authz wired)",
        "auth": True,
        "admin": True,
        "docker": False,
        "use_forge_meta": True,
    },
    "full": {
        "description": "max + docker-compose",
        "auth": True,
        "admin": True,
        "docker": True,
        "use_forge_meta": True,
    },
}

DEFAULT_PRESET = "max"
PRESET_NAMES = tuple(PRESETS.keys())

# Only forge is real; others alias with a warning.
LAYOUT_NAMES = ("forge", "flat", "mvc", "clean", "phzyx-app")
DEFAULT_LAYOUT = "forge"
LEGACY_LAYOUTS = frozenset({"flat", "mvc", "clean", "phzyx-app"})


def get_preset(name: str) -> dict[str, Any]:
    key = name.lower().strip()
    if key not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; choose one of: {', '.join(PRESET_NAMES)}")
    return dict(PRESETS[key])


def resolve_features(
    preset: str,
    *,
    auth: bool | None = None,
    admin: bool | None = None,
    docker: bool | None = None,
) -> dict[str, bool]:
    spec = get_preset(preset)
    a = bool(spec["auth"]) if auth is None else auth
    ad = bool(spec["admin"]) if admin is None else admin
    # max/full always want auth when admin is on (security lock).
    if ad and not a:
        # Caller may force --no-auth with admin; allow but mark.
        pass
    d = bool(spec["docker"]) if docker is None else docker
    return {
        "auth": a,
        "admin": ad,
        "docker": d,
        "use_forge_meta": bool(spec.get("use_forge_meta")),
    }


def normalize_layout(layout: str) -> tuple[str, str | None]:
    """Return (canonical_layout, warning_or_none)."""
    key = layout.lower().strip()
    if key not in LAYOUT_NAMES:
        raise ValueError(f"unknown layout {layout!r}; choose one of: {', '.join(LAYOUT_NAMES)}")
    if key in LEGACY_LAYOUTS:
        return (
            "forge",
            f"layout {key!r} is deprecated; using forge layout (async FastAPI + app/forge)",
        )
    return "forge", None
