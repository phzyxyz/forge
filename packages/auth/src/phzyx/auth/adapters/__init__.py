"""Framework adapters (FastAPI, Litestar, …)."""

from __future__ import annotations

from typing import Any

__all__ = ["mount_auth", "mount_auth_litestar"]


def __getattr__(name: str) -> Any:
    if name == "mount_auth":
        from phzyx.auth.adapters.fastapi import mount_auth

        return mount_auth
    if name == "mount_auth_litestar":
        from phzyx.auth.adapters.litestar import mount_auth_litestar

        return mount_auth_litestar
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
