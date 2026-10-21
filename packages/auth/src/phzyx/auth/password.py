"""Password hashing — Argon2id by default (OWASP)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_HASHER = _Argon2(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


@dataclass(frozen=True, slots=True)
class PasswordHasher:
    """Configurable Argon2id hasher (inject for tests)."""

    min_length: int = 8
    # Reject common / placeholder passwords (disable only in unit tests).
    reject_placeholders: bool = True

    def hash(
        self,
        password: str,
        *,
        email: str | None = None,
        username: str | None = None,
    ) -> str:
        self.validate_policy(password, email=email, username=username)
        return _HASHER.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return _HASHER.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return _HASHER.check_needs_rehash(password_hash)
        except Exception:
            return True

    def validate_policy(
        self,
        password: str,
        *,
        email: str | None = None,
        username: str | None = None,
    ) -> None:
        from phzyx.auth.policy import validate_password_value

        validate_password_value(
            password,
            min_length=self.min_length,
            email=email,
            username=username,
            reject_placeholders=self.reject_placeholders,
        )


_default = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _default.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify password against Argon2 hash."""
    return _default.verify(password_hash, password)


def generate_token(nbytes: int = 32) -> str:
    """High-entropy URL-safe token (sessions, reset, API key raw)."""
    return secrets.token_urlsafe(nbytes)
