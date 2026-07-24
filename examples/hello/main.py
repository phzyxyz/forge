"""Minimal FastAPI app wired to Phzyx packages (M0 stub).

When AdminBoard ships (M4), mount it here:

    from phzyx.admin.fastapi import AdminBoard
    AdminBoard(app, models=[...], theme="magical-white")
"""

from __future__ import annotations

from importlib import import_module

import phzyx.schema as schema
from fastapi import FastAPI

_admin_fastapi = import_module("phzyx.admin.fastapi")

app = FastAPI(
    title="Phzyx hello",
    description="Example FastAPI app using the Phzyx monorepo packages.",
    version="0.0.0",
)


@app.get("/")
def root() -> dict[str, str]:
    """Health-style greeting with package versions for wiring proof."""
    return {
        "message": "hello from phzyx",
        "phzyx_schema": schema.__version__,
        "phzyx_admin_fastapi": _admin_fastapi.__version__,
        "status": "scaffold",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
