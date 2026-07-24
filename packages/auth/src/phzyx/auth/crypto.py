"""Hashing helpers for opaque tokens and API keys."""

from __future__ import annotations

import hashlib
import hmac


def hash_token(raw: str, *, secret: str = "") -> str:
    """SHA-256 of token; optional HMAC with app secret for peppering."""
    if secret:
        return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:32]
