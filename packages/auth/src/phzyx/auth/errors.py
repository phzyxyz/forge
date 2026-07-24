"""Auth errors — stable codes for HTTP mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthError(Exception):
    code: str
    message: str
    status: int = 400
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class UnauthorizedError(AuthError):
    def __init__(self, message: str = "Authentication required", **details: Any) -> None:
        super().__init__(code="unauthorized", message=message, status=401, details=details)


class ForbiddenError(AuthError):
    def __init__(self, message: str = "Forbidden", **details: Any) -> None:
        super().__init__(code="forbidden", message=message, status=403, details=details)


class InvalidCredentialsError(AuthError):
    def __init__(self, message: str = "Invalid credentials", **details: Any) -> None:
        super().__init__(code="invalid_credentials", message=message, status=401, details=details)


class LockedError(AuthError):
    def __init__(self, message: str = "Account locked", **details: Any) -> None:
        super().__init__(code="account_locked", message=message, status=403, details=details)


class ValidationAuthError(AuthError):
    def __init__(self, message: str = "Validation failed", **details: Any) -> None:
        super().__init__(code="validation_error", message=message, status=422, details=details)


class MfaRequiredError(AuthError):
    """Password ok but MFA challenge required (optional raise path)."""

    def __init__(
        self,
        message: str = "MFA required",
        *,
        mfa_challenge_id: str | None = None,
        **details: Any,
    ) -> None:
        d = dict(details)
        if mfa_challenge_id is not None:
            d["mfa_challenge_id"] = mfa_challenge_id
        super().__init__(code="mfa_required", message=message, status=401, details=d)
