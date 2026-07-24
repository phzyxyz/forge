"""Security helpers — CSP, mass-assignment, production checks."""

from __future__ import annotations

import os
from typing import Any

from phzyx.admin.errors import ValidationAdminError
from phzyx.admin.resource import ResourceConfig

DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


def csp_headers(*, report_only: bool = False) -> dict[str, str]:
    key = "Content-Security-Policy-Report-Only" if report_only else "Content-Security-Policy"
    return {key: DEFAULT_CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY"}


def is_production_like() -> bool:
    env = (os.environ.get("PHZYX_ENV") or os.environ.get("ENV") or "").lower()
    return env in {"prod", "production"} or os.environ.get("PHZYX_PRODUCTION", "").lower() in {
        "1",
        "true",
        "yes",
    }


def assert_no_mass_assignment(
    resource: ResourceConfig,
    data: dict[str, Any],
    *,
    partial: bool = False,
) -> dict[str, Any]:
    """Strip unknown / secret / readonly fields; raise if secrets were attempted."""
    secret_names = {c.name for c in resource.columns if c.secret}
    attempted_secrets = sorted(set(data) & secret_names)
    if attempted_secrets:
        raise ValidationAdminError(
            "mass assignment of excluded fields denied",
            fields=attempted_secrets,
        )
    allowed = {
        c.name
        for c in resource.columns
        if not c.secret and not c.hidden and (not c.readonly or not partial)
    }
    if not partial:
        for pk in resource.primary_key:
            allowed.add(pk)
    return {k: v for k, v in data.items() if k in allowed}


def csrf_cookie_notes() -> str:
    return (
        "Prefer Bearer/API key for SPA→API. If using cookies: SameSite=Lax/Strict, "
        "CSRF double-submit or synchronizer token on mutations, secure cookies on HTTPS."
    )
