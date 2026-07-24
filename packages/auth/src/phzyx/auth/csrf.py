"""Double-submit CSRF for cookie SPA sessions (SameSite=Lax + header check)."""

from __future__ import annotations

import hmac
from typing import Any

from phzyx.auth.password import generate_token


def issue_csrf_token() -> str:
    """Opaque CSRF token (store in readable cookie; client echoes in header)."""
    return generate_token(24)


def csrf_valid(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def should_check_csrf(
    method: str,
    *,
    has_session_cookie: bool,
    csrf_protect: bool,
) -> bool:
    """CSRF only for cookie-authenticated mutating requests."""
    if not csrf_protect:
        return False
    if method.upper() in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return False
    return has_session_cookie


def extract_csrf(
    request: Any, *, cookie_name: str, header_name: str
) -> tuple[str | None, str | None]:
    cookies = getattr(request, "cookies", {}) or {}
    headers = getattr(request, "headers", {}) or {}
    cookie = cookies.get(cookie_name) if hasattr(cookies, "get") else None
    header = None
    if hasattr(headers, "get"):
        header = headers.get(header_name) or headers.get(header_name.title())
    return cookie, header
