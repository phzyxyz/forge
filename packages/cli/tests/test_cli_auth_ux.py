"""CLI auth UX — no stack traces on validation failures."""

from __future__ import annotations

from phzyx.cli import main


def test_auth_create_superuser_short_password_exit_clean(capsys) -> None:
    code = main(
        [
            "auth",
            "create-superuser",
            "--email",
            "admin@example.com",
            "--password",
            "short",
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "error:" in err
    assert "at least" in err.lower() or "password" in err.lower()
    assert "Traceback" not in err
    assert "hint:" in err


def test_auth_create_superuser_bad_email_exit_clean(capsys) -> None:
    code = main(
        [
            "auth",
            "create-superuser",
            "--email",
            "admin",
            "--password",
            "longenoughpassword",
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "error:" in err
    assert "email" in err.lower()
    assert "Traceback" not in err


def test_auth_missing_subcommand(capsys) -> None:
    code = main(["auth"])
    assert code == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "Traceback" not in err
