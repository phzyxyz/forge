"""AdminBoard structured errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdminError(Exception):
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


class NotFoundError(AdminError):
    def __init__(self, message: str = "Resource not found", **details: Any) -> None:
        super().__init__(code="not_found", message=message, status=404, details=details)


class ForbiddenError(AdminError):
    def __init__(self, message: str = "Forbidden", **details: Any) -> None:
        super().__init__(code="forbidden", message=message, status=403, details=details)


class ValidationAdminError(AdminError):
    def __init__(self, message: str = "Validation failed", **details: Any) -> None:
        super().__init__(code="validation_error", message=message, status=422, details=details)


class UnauthorizedError(AdminError):
    def __init__(self, message: str = "Unauthorized", **details: Any) -> None:
        super().__init__(code="unauthorized", message=message, status=401, details=details)


class ConflictError(AdminError):
    """HTTP 409 — optimistic concurrency / version conflict."""

    def __init__(self, message: str = "Conflict", **details: Any) -> None:
        super().__init__(code="conflict", message=message, status=409, details=details)
