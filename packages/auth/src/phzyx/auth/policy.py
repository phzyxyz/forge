"""Identity / credential policy — reject empty, weak, and placeholder values.

Used by password hashing, register, and ``auth create-superuser`` so the CLI
and the API share the same rules.
"""

from __future__ import annotations

import re

from phzyx.auth.errors import ValidationAuthError

# Common throwaway / tutorial credentials (lowercased match).
WEAK_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password12",
        "password123",
        "password1234",
        "passw0rd",
        "admin",
        "admin123",
        "admin1234",
        "administrator",
        "root",
        "root1234",
        "secret",
        "secret123",
        "changeme",
        "change-me",
        "change_me",
        "letmein",
        "welcome",
        "welcome1",
        "qwerty",
        "qwerty123",
        "1234567890",
        "0123456789",
        "1111111111",
        "0000000000",
        "abcdefghij",
        "test",
        "test1234",
        "testing",
        "testing123",
        "default",
        "default1",
        "pass",
        "pass1234",
        "p@ssw0rd",
        "p@ssword",
        "superuser",
        "superuser1",
        "phzyx",
        "phzyx1234",
        "forge",
        "forge1234",
    }
)

# Full emails that docs / scaffolds often show as examples.
PLACEHOLDER_EMAILS: frozenset[str] = frozenset(
    {
        "admin@example.com",
        "user@example.com",
        "test@example.com",
        "demo@example.com",
        "admin@test.com",
        "user@test.com",
        "test@test.com",
        "admin@localhost",
        "test@localhost",
        "admin@admin.com",
        "root@localhost",
        "you@example.com",
        "me@example.com",
        "name@example.com",
        "email@example.com",
        "foo@bar.com",
        "a@b.com",
    }
)

PLACEHOLDER_EMAIL_LOCALS: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "test",
        "testing",
        "user",
        "demo",
        "guest",
        "superuser",
        "example",
        "sample",
        "placeholder",
        "changeme",
        "yourname",
        "you",
        "me",
        "foo",
        "bar",
        "asdf",
    }
)

PLACEHOLDER_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "test.org",
        "localhost",
        "local",
        "invalid",
        "email.com",
        "domain.com",
        "yourdomain.com",
        "company.com",
    }
)

PLACEHOLDER_USERNAMES: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "test",
        "testing",
        "user",
        "demo",
        "guest",
        "superuser",
        "super",
        "owner",
        "changeme",
        "placeholder",
        "null",
        "none",
        "undefined",
        "asdf",
        "foo",
        "bar",
    }
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,62}$")


def _is_repeated_char(value: str) -> bool:
    return len(value) >= 3 and len(set(value)) == 1


def _is_trivial_sequence(value: str) -> bool:
    """Reject long pure digit/letter runs that are just keyboard spam."""
    lower = value.lower()
    if lower.isdigit() and len(set(lower)) <= 2:
        return True
    # abcdefghij / qwertyuiop style
    sequences = (
        "abcdefghijklmnopqrstuvwxyz",
        "qwertyuiopasdfghjklzxcvbnm",
        "0123456789",
    )
    return any(lower in seq or lower in seq[::-1] for seq in sequences)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(
    email: str,
    *,
    reject_placeholders: bool = True,
) -> str:
    """Normalize + validate email; optionally reject tutorial placeholders."""
    value = normalize_email(email)
    if not value:
        raise ValidationAuthError("email is required", field="email")
    if not _EMAIL_RE.match(value):
        raise ValidationAuthError(
            "email must look like user@example.com",
            field="email",
        )
    if not reject_placeholders:
        return value

    if value in PLACEHOLDER_EMAILS:
        raise ValidationAuthError(
            f"{value!r} looks like a placeholder email — use a real address",
            field="email",
        )
    local, _, domain = value.partition("@")
    if local in PLACEHOLDER_EMAIL_LOCALS and domain in PLACEHOLDER_EMAIL_DOMAINS:
        raise ValidationAuthError(
            f"{value!r} looks like a placeholder email — use a real address",
            field="email",
        )
    if domain in {"example.com", "example.org", "example.net", "test.com", "localhost"}:
        # Any address on classic doc domains (including admin@example.com already covered)
        raise ValidationAuthError(
            f"domain {domain!r} is reserved for examples — use a real email domain",
            field="email",
        )
    return value


def validate_username(
    username: str | None,
    *,
    required: bool = False,
    reject_placeholders: bool = True,
    soft: bool = False,
) -> str | None:
    """Validate optional username; reject empty / weak placeholders when set.

    ``soft=True`` (OAuth display names): invalid shapes become ``None`` or a
    simple slug instead of raising — so provider profile names do not break signup.
    """
    if username is None:
        if required:
            raise ValidationAuthError("username is required", field="username")
        return None
    value = username.strip()
    if not value:
        if required:
            raise ValidationAuthError("username is required", field="username")
        return None
    if len(value) < 2:
        if soft:
            return None
        raise ValidationAuthError(
            "username must be at least 2 characters",
            field="username",
        )
    if not _USERNAME_RE.match(value):
        if soft:
            slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-_.")
            if len(slug) >= 2 and _USERNAME_RE.match(slug):
                value = slug
            else:
                return None
        else:
            raise ValidationAuthError(
                "username may only use letters, digits, ., _, - (start with alnum)",
                field="username",
            )
    if reject_placeholders and value.lower() in PLACEHOLDER_USERNAMES:
        if soft:
            return None
        raise ValidationAuthError(
            f"username {value!r} is a reserved/placeholder name — choose another",
            field="username",
        )
    if reject_placeholders and _is_repeated_char(value.lower()):
        if soft:
            return None
        raise ValidationAuthError(
            "username looks like a placeholder (repeated characters)",
            field="username",
        )
    return value


def validate_password_value(
    password: str,
    *,
    min_length: int = 8,
    email: str | None = None,
    username: str | None = None,
    reject_placeholders: bool = True,
) -> str:
    """Password length + weak/placeholder + must not equal email/username."""
    if not password or len(password) < min_length:
        raise ValidationAuthError(
            f"password must be at least {min_length} characters",
            field="password",
        )
    if not reject_placeholders:
        return password

    lower = password.lower()
    if lower in WEAK_PASSWORDS:
        raise ValidationAuthError(
            "password is too common or a placeholder — choose a stronger one",
            field="password",
        )
    if _is_repeated_char(lower):
        raise ValidationAuthError(
            "password cannot be a single repeated character",
            field="password",
        )
    if _is_trivial_sequence(password):
        raise ValidationAuthError(
            "password is too simple (sequence or low variety)",
            field="password",
        )
    if email:
        email_n = normalize_email(email)
        local = email_n.split("@", 1)[0] if "@" in email_n else email_n
        if lower in (email_n, local):
            raise ValidationAuthError(
                "password must not be the same as your email",
                field="password",
            )
    if username and lower == username.strip().lower():
        raise ValidationAuthError(
            "password must not be the same as your username",
            field="password",
        )
    return password
