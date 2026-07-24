"""``phzyx doctor`` — security and environment checks for Phzyx apps."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from enum import StrEnum

# Mirror phzyx.auth.config without requiring auth to be installed.
MIN_SECRET_BYTES = 32
_WEAK_SECRETS = frozenset(
    {
        "",
        "change-me",
        "dev",
        "secret",
        "password",
        "admin",
        "dev-only-insecure-secret-min-32b!!",
    }
)
_WEAK_PASSWORD_ENV_KEYS = (
    "PHZYX_AUTH_PASSWORD",
    "PHZYX_ADMIN_PASSWORD",
    "ADMIN_PASSWORD",
    "DEFAULT_PASSWORD",
)
_WEAK_PASSWORD_VALUES = frozenset(
    {
        "",
        "password",
        "admin",
        "admin123",
        "123456",
        "changeme",
        "change-me",
        "secret",
        "phzyx",
        "test",
    }
)


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class CheckResult:
    """One doctor finding."""

    name: str
    severity: Severity
    message: str


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _is_production() -> bool:
    env = os.environ.get("PHZYX_ENV", "").lower()
    if env in {"prod", "production"}:
        return True
    return _truthy(os.environ.get("PHZYX_AUTH_PRODUCTION"))


def check_auth_secret() -> CheckResult:
    """Validate ``PHZYX_AUTH_SECRET`` length and weakness."""
    secret = os.environ.get("PHZYX_AUTH_SECRET", "")
    prod = _is_production()
    name = "PHZYX_AUTH_SECRET"

    if not secret:
        if prod:
            return CheckResult(
                name,
                Severity.ERROR,
                "missing in production (set PHZYX_AUTH_SECRET ≥32 bytes)",
            )
        return CheckResult(
            name,
            Severity.WARN,
            "unset — auth will use an insecure dev default",
        )

    nbytes = len(secret.encode("utf-8"))
    if nbytes < MIN_SECRET_BYTES:
        return CheckResult(
            name,
            Severity.ERROR,
            f"too short ({nbytes} bytes; need ≥{MIN_SECRET_BYTES})",
        )

    if secret in _WEAK_SECRETS or secret.lower() in _WEAK_SECRETS:
        sev = Severity.ERROR if prod else Severity.WARN
        return CheckResult(
            name,
            sev,
            "weak/placeholder secret — generate with secrets.token_urlsafe(32)",
        )

    return CheckResult(name, Severity.OK, f"set ({nbytes} bytes)")


def check_production_flags() -> CheckResult:
    """Surface production mode and related env flags."""
    prod = _is_production()
    env = os.environ.get("PHZYX_ENV") or "(unset)"
    auth_prod = os.environ.get("PHZYX_AUTH_PRODUCTION") or "(unset)"
    if prod:
        return CheckResult(
            "production",
            Severity.OK,
            f"production mode on (PHZYX_ENV={env}, PHZYX_AUTH_PRODUCTION={auth_prod})",
        )
    return CheckResult(
        "production",
        Severity.OK,
        f"development mode (PHZYX_ENV={env}, PHZYX_AUTH_PRODUCTION={auth_prod})",
    )


def check_cookie_secure() -> CheckResult:
    """In production, cookie Secure flag should be on."""
    name = "cookie_secure"
    prod = _is_production()
    raw = os.environ.get("PHZYX_AUTH_COOKIE_SECURE")
    if raw is None:
        # AuthConfig defaults cookie_secure=production
        if prod:
            return CheckResult(
                name,
                Severity.OK,
                "PHZYX_AUTH_COOKIE_SECURE unset — defaults to secure in production",
            )
        return CheckResult(
            name,
            Severity.OK,
            "PHZYX_AUTH_COOKIE_SECURE unset — defaults to insecure cookies in dev",
        )
    secure = _truthy(raw)
    if prod and not secure:
        return CheckResult(
            name,
            Severity.ERROR,
            "PHZYX_AUTH_COOKIE_SECURE is off in production (session cookies need Secure)",
        )
    if not prod and secure:
        return CheckResult(
            name,
            Severity.WARN,
            "Secure cookies enabled in non-production (HTTPS required)",
        )
    return CheckResult(
        name,
        Severity.OK,
        f"PHZYX_AUTH_COOKIE_SECURE={raw}",
    )


def check_weak_password_env() -> list[CheckResult]:
    """Flag common weak bootstrap password env vars if set."""
    results: list[CheckResult] = []
    for key in _WEAK_PASSWORD_ENV_KEYS:
        val = os.environ.get(key)
        if val is None:
            continue
        if val.lower() in _WEAK_PASSWORD_VALUES or len(val) < 8:
            sev = Severity.ERROR if _is_production() else Severity.WARN
            results.append(
                CheckResult(
                    key,
                    sev,
                    "weak or short password in environment — use a strong secret",
                )
            )
        else:
            results.append(CheckResult(key, Severity.OK, "set (not obviously weak)"))
    if not results:
        results.append(
            CheckResult(
                "weak_password_env",
                Severity.OK,
                "no bootstrap password env vars set",
            )
        )
    return results


def check_package_imports() -> list[CheckResult]:
    """Try importing Forge core and optional batteries."""
    modules = (
        ("phzyx.schema", "phzyx-schema", True),
        ("phzyx.engine", "phzyx-engine", True),
        ("phzyx.orm", "phzyx-orm", True),
        ("phzyx.admin.fastapi", "phzyx-admin-fastapi", False),
        ("phzyx.auth", "phzyx-auth", False),
        ("phzyx.cache", "phzyx-cache", False),
        ("phzyx.cli", "phzyx-cli", False),
    )
    out: list[CheckResult] = []
    for mod, pip_name, required in modules:
        try:
            importlib.import_module(mod)
            out.append(CheckResult(mod, Severity.OK, f"importable ({pip_name})"))
        except ImportError:
            sev = Severity.ERROR if required else Severity.WARN
            out.append(
                CheckResult(
                    mod,
                    sev,
                    f"not importable — install with: uv add {pip_name}",
                )
            )
    return out


def optional_package_tips() -> list[str]:
    """Non-blocking tips for packages not installed (never fails doctor)."""
    tips: list[str] = []
    catalog = (
        ("phzyx.auth", "uv add phzyx-auth", "sessions, JWT, MFA, passkeys"),
        ("phzyx.cache", "uv add phzyx-cache", "list/resource cache helpers"),
        (
            "phzyx.admin.litestar",
            "uv add phzyx-admin-litestar",
            "AdminBoard on Litestar",
        ),
    )
    for mod, install, blurb in catalog:
        try:
            importlib.import_module(mod)
        except ImportError:
            tips.append(f"optional: {install}  # {blurb}")
    tips.append("product line: uv add phzyx-forge  # schema→AdminBoard+cli")
    tips.append("ecosystem:   uv add phzyx         # all published Phzyx products")
    return tips


def run_doctor() -> list[CheckResult]:
    """Run all checks and return results in display order."""
    results: list[CheckResult] = [
        check_auth_secret(),
        check_production_flags(),
        check_cookie_secure(),
    ]
    results.extend(check_weak_password_env())
    results.extend(check_package_imports())
    return results


def doctor_exit_code(results: list[CheckResult]) -> int:
    """0 if no errors; 1 if any ERROR (warnings alone still exit 0)."""
    if any(r.severity == Severity.ERROR for r in results):
        return 1
    return 0


def format_results(results: list[CheckResult]) -> str:
    """Human-readable doctor report."""
    lines = ["phzyx doctor", ""]
    for r in results:
        mark = {
            Severity.OK: "ok  ",
            Severity.WARN: "warn",
            Severity.ERROR: "FAIL",
        }[r.severity]
        lines.append(f"  [{mark}] {r.name}: {r.message}")
    errors = sum(1 for r in results if r.severity == Severity.ERROR)
    warns = sum(1 for r in results if r.severity == Severity.WARN)
    lines.append("")
    lines.append(f"{errors} error(s), {warns} warning(s)")
    tips = optional_package_tips()
    if tips:
        lines.append("")
        lines.append("tips (optional — does not affect exit code):")
        for t in tips:
            lines.append(f"  · {t}")
    return "\n".join(lines)
