"""Auth CLI helpers — create-superuser (stdlib argparse, called from phzyx-cli later)."""

from __future__ import annotations

import argparse
import getpass
import sys

from phzyx.auth.config import AuthConfig
from phzyx.auth.service import AuthService


def create_superuser(
    email: str | None = None,
    password: str | None = None,
    *,
    service: AuthService | None = None,
) -> str:
    """Register a staff+superuser. Returns user id."""
    svc = service or AuthService(config=AuthConfig.from_env(production=False))
    email = email or input("Email: ").strip()
    password = password or getpass.getpass("Password: ")
    p = svc.register(email, password, is_staff=True, is_superuser=True)
    return p.id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phzyx-auth")
    sub = parser.add_subparsers(dest="cmd")
    su = sub.add_parser("create-superuser", help="Create staff superuser")
    su.add_argument("--email")
    su.add_argument("--password")
    ns = parser.parse_args(argv)
    if ns.cmd == "create-superuser":
        uid = create_superuser(ns.email, ns.password)
        print(f"Created superuser id={uid}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
