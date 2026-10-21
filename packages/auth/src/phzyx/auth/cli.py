"""Auth CLI helpers — create-superuser with clean prompts, retries, exit codes."""

from __future__ import annotations

import argparse
import getpass
import importlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
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


def _load_dotenv(root: Path) -> None:
    """Minimal .env loader (KEY=VALUE if unset) — keeps CLI free of python-dotenv."""
    path = root / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _ensure_project_on_sys_path(root: Path) -> None:
    path = str(root.resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


def resolve_project_auth_service(
    *,
    root: Path | None = None,
    error_stream: TextIO | None = None,
) -> AuthService | None:
    """Build the app's ORM-backed AuthService (scaffold: app.forge.auth).

    Returns None if no project wiring is found. Without this, create-superuser
    would only write to an in-memory map that never reaches AdminBoard login.
    """
    err = error_stream or sys.stderr
    project = (root or Path.cwd()).resolve()
    _ensure_project_on_sys_path(project)
    _load_dotenv(project)

    candidates: list[tuple[str, str, str, str]] = [
        ("app.forge.auth", "build_auth_service", "app.forge.db", "get_admin_session"),
        ("app.auth", "build_auth_service", "app.db", "get_session"),
    ]
    for auth_mod, auth_attr, db_mod, db_attr in candidates:
        try:
            am = importlib.import_module(auth_mod)
            dm = importlib.import_module(db_mod)
        except ImportError:
            continue
        builder = getattr(am, auth_attr, None)
        session_factory = getattr(dm, db_attr, None)
        if not callable(builder) or not callable(session_factory):
            continue
        try:
            svc = builder(session_factory)
        except Exception as exc:  # noqa: BLE001
            err.write(f"warning: could not build auth service from {auth_mod}: {exc}\n")
            err.flush()
            continue
        if isinstance(svc, AuthService):
            return svc
    return None


def default_auth_service(
    *,
    root: Path | None = None,
    error_stream: TextIO | None = None,
) -> tuple[AuthService, bool]:
    """Return (service, from_project).

    ``from_project=True`` means users persist via the app ORM (AdminBoard login works).
    """
    err = error_stream or sys.stderr
    project = resolve_project_auth_service(root=root, error_stream=error_stream)
    if project is not None:
        return project, True
    err.write(
        "warning: no app.forge.auth wiring found — creating user in-memory only\n"
        "hint: run from a scaffolded project root (with app/forge/auth.py) so the "
        "superuser is stored in your database for /admin login\n"
    )
    err.flush()
    return AuthService(config=AuthConfig.from_env(production=False)), False


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
    project_root: Path | None = None,
) -> str:
    """Register a staff+superuser. Returns user id.

    Uses the scaffold ORM auth service when available so AdminBoard can log in.
    """
    err = error_stream or sys.stderr
    if service is not None:
        svc = service
        from_project = True
    else:
        svc, from_project = default_auth_service(
            root=project_root,
            error_stream=error_stream,
        )
    inp = input_stream or sys.stdin
    out = output_stream or sys.stdout
    gp = getpass_fn or getpass.getpass
    flags_given = email is not None or password is not None or username is not None
    interactive = _is_interactive(inp) and not flags_given
    hasher = getattr(svc.config, "password", None) or PasswordHasher()
    # Superuser path always enforces placeholders even if test hasher is lax.
    if not hasher.reject_placeholders:
        from dataclasses import replace

        hasher = replace(hasher, reject_placeholders=True)

    def _register(email_n: str, password_n: str, username_n: str | None) -> str:
        try:
            p = svc.register(
                email_n,
                password_n,
                username=username_n,
                is_staff=True,
                is_superuser=True,
                reject_placeholders=True,
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "no such table" in msg.lower() or "does not exist" in msg.lower():
                raise AuthCliError(
                    "auth tables missing — run schema first: "
                    "uv run forge start  (apply schema) or  "
                    "uv run forge db push --models app.forge.registry:ALL_MODELS --yes",
                    exit_code=2,
                ) from exc
            raise
        if from_project:
            # Confirm the row is visible via the same map login will use.
            stored = svc.users.get(email_n)
            if stored is None:
                raise AuthCliError(
                    "user was not persisted — check database URL and auth wiring",
                    exit_code=2,
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
    project_root: Path | None = None,
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
            project_root=project_root,
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
                "usernames (admin/test/root), password ≥8 chars and not common "
                "(password/admin123/…); run from project root so user is saved to DB\n"
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
    out.write("next: open /admin/ and sign in with that email + password\n")
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
