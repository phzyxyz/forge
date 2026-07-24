"""TOTP (RFC 6238) — minimal pure-Python; optional pyotp if installed."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass


def _b32_encode_secret(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _b32_decode_secret(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    # pad to multiple of 8 for stdlib
    pad = (-len(s)) % 8
    return base64.b32decode(s + ("=" * pad), casefold=True)


def generate_totp_secret(*, nbytes: int = 20) -> str:
    """Return a base32-encoded shared secret (no padding)."""
    return _b32_encode_secret(secrets.token_bytes(nbytes))


def totp_at(
    secret: str,
    *,
    for_time: int | None = None,
    step: int = 30,
    digits: int = 6,
    digest: str = "sha1",
) -> str:
    """Compute TOTP code for ``for_time`` (unix seconds; default now)."""
    try:
        import pyotp  # type: ignore[import-untyped]

        return pyotp.TOTP(secret, digits=digits, interval=step, digest=getattr(hashlib, digest)).at(
            for_time if for_time is not None else int(time.time())
        )
    except ImportError:
        pass

    counter = int((for_time if for_time is not None else time.time()) // step)
    key = _b32_decode_secret(secret)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, getattr(hashlib, digest)).digest()
    offset = h[-1] & 0x0F
    code_int = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10**digits)
    return str(code).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    for_time: int | None = None,
    step: int = 30,
    digits: int = 6,
    window: int = 1,
) -> bool:
    """Verify a TOTP code with ±window steps skew tolerance."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != digits:
        return False
    now = int(for_time if for_time is not None else time.time())
    try:
        import pyotp  # type: ignore[import-untyped]

        totp = pyotp.TOTP(secret, digits=digits, interval=step)
        return bool(totp.verify(code, for_time=now, valid_window=window))
    except ImportError:
        pass

    for skew in range(-window, window + 1):
        expected = totp_at(secret, for_time=now + skew * step, step=step, digits=digits)
        if hmac.compare_digest(expected, code):
            return True
    return False


def provisioning_uri(
    secret: str,
    *,
    account_name: str,
    issuer: str = "Phzyx",
) -> str:
    """otpauth:// URI for authenticator apps (QR encoding left to the app)."""
    from urllib.parse import quote

    label = quote(f"{issuer}:{account_name}")
    iss = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={iss}&algorithm=SHA1&digits=6&period=30"


@dataclass(frozen=True, slots=True)
class TotpSetup:
    """Pending TOTP enrollment payload (secret shown once)."""

    secret: str
    provisioning_uri: str
