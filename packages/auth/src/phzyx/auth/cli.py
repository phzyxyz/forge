"""Auth CLI helpers — create-superuser with clean prompts, retries, exit codes."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable
from typing import TextIO

from phzyx.auth.config import AuthConfig
from phzyx.auth.errors import AuthError, ValidationAuthError
from phzyx.auth.password import PasswordHasher
from phzyx.auth.policy import validate_email, validate_password_value, validate_username
from phzyx.auth.service import AuthService


class AuthCliError(Exception):
    """User-facing CLI abort (EOF, cancel, too many attempts). No traceback."""

    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def validate_password(
    password: str,
    *,
    hasher: PasswordHasher | None = None,
    email: str | None = None,
    username: str | None = None,
) -> str:
    """Validate password policy (length, placeholders, not equal to identity)."""
    ph = hasher or PasswordHasher()
    try:
        return validate_password_value(
            password,
            min_length=ph.min_length,
            email=email,
            username=username,
            reject_placeholders=ph.reject_placeholders,
        )
    except AuthError:
        raise
    except ValueError as exc:
        raise ValidationAuthError(str(exc), field="password") from exc


def _is_interactive(stream: TextIO) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)())


def _read_line(
    prompt: str,
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> str:
    output_stream.write(prompt)
    output_stream.flush()
    line = input_stream.readline()
    if line == "":
        raise AuthCliError("aborted (EOF)", exit_code=1)
    return line.strip()


def _read_password(
    prompt: str,
    *,
    output_stream: TextIO,
    getpass_fn: Callable[[str], str],
    interactive: bool,
    input_stream: TextIO,
) -> str:
    if interactive:
        try:
            return getpass_fn(prompt)
        except (EOFError, KeyboardInterrupt) as exc:
            raise AuthCliError("aborted", exit_code=1) from exc
    return _read_line(prompt, input_stream=input_stream, output_stream=output_stream)


def _print_error(message: str, *, output_stream: TextIO) -> None:
    output_stream.write(f"error: {message}\n")
    output_stream.flush()


def create_superuser(
    email: str | None = None,
    password: str | None = None,
    *,
    username: str | None = None,
    service: AuthService | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    error_stream: TextIO | None = None,
    getpass_fn: Callable[[str], str] | None = None,
    max_attempts: int = 5,
    confirm_password: bool = True,
    prompt_username: bool = False,
) -> str:
    """Register a staff+superuser. Returns user id.

    Interactive (TTY and no flags): re-prompts on validation errors instead of
    dumping a traceback. Rejects placeholder emails/usernames and weak passwords.
    """
    svc = service or AuthService(config=AuthConfig.from_env(production=False))
    inp = input_stream or sys.stdin
    out = output_stream or sys.stdout
    err = error_stream or sys.stderr
    gp = getpass_fn or getpass.getpass
    flags_given = email is not None or password is not None or username is not None
    interactive = _is_interactive(inp) and not flags_given
    hasher = getattr(svc.config, "password", None) or PasswordHasher()
    # Superuser path always enforces placeholders even if test hasher is lax.
    if not hasher.reject_placeholders:
        from dataclasses import replace

        hasher = replace(hasher, reject_placeholders=True)

    def _register(email_n: str, password_n: str, username_n: str | None) -> str:
        p = svc.register(
            email_n,
            password_n,
            username=username_n,
            is_staff=True,
            is_superuser=True,
            reject_placeholders=True,
        )
        return str(p.id)

    if not interactive:
        email_n = validate_email(
            email
            if email is not None
            else _read_line("Email: ", input_stream=inp, output_stream=out),
            reject_placeholders=True,
        )
        username_n = validate_username(
            username
            if username is not None
            else (
                _read_line(
                    "Username (optional, Enter to skip): ",
                    input_stream=inp,
                    output_stream=out,
                )
                if prompt_username
                else None
            ),
            reject_placeholders=True,
        )
        if password is None:
            password = _read_password(
                "Password: ",
                output_stream=out,
                getpass_fn=gp,
                interactive=_is_interactive(inp),
                input_stream=inp,
            )
        password_n = validate_password(
            password,
            hasher=hasher,
            email=email_n,
            username=username_n,
        )
        return _register(email_n, password_n, username_n)

    # Interactive: retry until success or max attempts
    email_n: str | None = None
    username_n: str | None = None
    username_done = not prompt_username
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        try:
            if email_n is None:
                raw = _read_line("Email: ", input_stream=inp, output_stream=out)
                if not raw:
                    _print_error("email is required", output_stream=err)
                    continue
                email_n = validate_email(raw, reject_placeholders=True)

            if not username_done:
                raw_u = _read_line(
                    "Username (optional, Enter to skip): ",
                    input_stream=inp,
                    output_stream=out,
                )
                username_n = validate_username(
                    raw_u or None,
                    reject_placeholders=True,
                )
                username_done = True

            pwd = _read_password(
                "Password: ",
                output_stream=out,
                getpass_fn=gp,
                interactive=True,
                input_stream=inp,
            )
            password_n = validate_password(
                pwd,
                hasher=hasher,
                email=email_n,
                username=username_n,
            )

            if confirm_password:
                again = _read_password(
                    "Confirm password: ",
                    output_stream=out,
                    getpass_fn=gp,
                    interactive=True,
                    input_stream=inp,
                )
                if again != password_n:
                    raise ValidationAuthError(
                        "passwords do not match",
                        field="password",
                    )

            return _register(email_n, password_n, username_n)
        except ValidationAuthError as exc:
            field = (exc.details or {}).get("field")
            _print_error(exc.message, output_stream=err)
            if field == "email":
                email_n = None
            elif field == "username":
                username_done = False
                username_n = None
            continue
        except AuthError as exc:
            _print_error(exc.message, output_stream=err)
            email_n = None
            username_done = not prompt_username
            username_n = None
            continue
        except AuthCliError:
            raise
        except ValueError as exc:
            _print_error(str(exc), output_stream=err)
            continue

    raise AuthCliError(
        f"too many failed attempts ({max_attempts}); aborting",
        exit_code=1,
    )


def run_create_superuser(
    email: str | None = None,
    password: str | None = None,
    *,
    username: str | None = None,
    service: AuthService | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    error_stream: TextIO | None = None,
    getpass_fn: Callable[[str], str] | None = None,
    prompt_username: bool = False,
) -> int:
    """CLI entry: create superuser; never prints a traceback for user errors."""
    out = output_stream or sys.stdout
    err = error_stream or sys.stderr
    try:
        uid = create_superuser(
            email,
            password,
            username=username,
            service=service,
            input_stream=input_stream,
            output_stream=output_stream,
            error_stream=error_stream,
            getpass_fn=getpass_fn,
            prompt_username=prompt_username,
        )
    except AuthCliError as exc:
        err.write(f"error: {exc.message}\n")
        err.flush()
        return int(exc.exit_code)
    except AuthError as exc:
        err.write(f"error: {exc.message}\n")
        if email is not None or password is not None or username is not None:
            err.write(
                "hint: use a real email (not @example.com), avoid placeholder "
                "usernames (admin/test/root), password ≥10 chars and not common "
                "(password/admin123/…); or omit flags for interactive retries\n"
            )
        err.flush()
        return 2
    except ValueError as exc:
        err.write(f"error: {exc}\n")
        err.flush()
        return 2
    except KeyboardInterrupt:
        err.write("\naborted\n")
        err.flush()
        return 130
    out.write(f"Created superuser id={uid}\n")
    out.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phzyx-auth")
    sub = parser.add_subparsers(dest="cmd")
    su = sub.add_parser("create-superuser", help="Create staff superuser")
    su.add_argument("--email")
    su.add_argument("--password")
    su.add_argument("--username", default=None, help="optional username")
    su.add_argument(
        "--prompt-username",
        action="store_true",
        help="ask for username interactively (optional field)",
    )
    ns = parser.parse_args(argv)
    if ns.cmd == "create-superuser":
        return run_create_superuser(
            ns.email,
            ns.password,
            username=ns.username,
            prompt_username=bool(ns.prompt_username),
        )
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
