"""phzyx doctor checks."""

from __future__ import annotations

import pytest
from phzyx.cli import main
from phzyx.cli.doctor import (
    Severity,
    check_auth_secret,
    check_cookie_secure,
    doctor_exit_code,
    run_doctor,
)


@pytest.mark.unit
def test_doctor_runs(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHZYX_AUTH_SECRET", raising=False)
    monkeypatch.delenv("PHZYX_AUTH_PRODUCTION", raising=False)
    monkeypatch.delenv("PHZYX_ENV", raising=False)
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert "phzyx doctor" in out
    assert "PHZYX_AUTH_SECRET" in out
    # missing secret is warn in dev → exit 0 unless package errors
    assert code in (0, 1)


@pytest.mark.unit
def test_secret_short_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_AUTH_SECRET", "tooshort")
    monkeypatch.delenv("PHZYX_AUTH_PRODUCTION", raising=False)
    monkeypatch.setenv("PHZYX_ENV", "development")
    r = check_auth_secret()
    assert r.severity == Severity.ERROR
    assert "too short" in r.message


@pytest.mark.unit
def test_secret_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_AUTH_SECRET", "x" * 32)
    r = check_auth_secret()
    assert r.severity == Severity.OK


@pytest.mark.unit
def test_weak_secret_prod_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_AUTH_SECRET", "dev-only-insecure-secret-min-32b!!")
    monkeypatch.setenv("PHZYX_AUTH_PRODUCTION", "1")
    r = check_auth_secret()
    assert r.severity == Severity.ERROR


@pytest.mark.unit
def test_cookie_secure_off_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_AUTH_PRODUCTION", "1")
    monkeypatch.setenv("PHZYX_AUTH_COOKIE_SECURE", "0")
    r = check_cookie_secure()
    assert r.severity == Severity.ERROR


@pytest.mark.unit
def test_doctor_exit_code_errors() -> None:
    from phzyx.cli.doctor import CheckResult

    ok = [CheckResult("a", Severity.OK, "fine")]
    assert doctor_exit_code(ok) == 0
    bad = [CheckResult("a", Severity.ERROR, "bad")]
    assert doctor_exit_code(bad) == 1
    warn = [CheckResult("a", Severity.WARN, "meh")]
    assert doctor_exit_code(warn) == 0


@pytest.mark.unit
def test_run_doctor_includes_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHZYX_AUTH_SECRET", "a" * 40)
    monkeypatch.delenv("PHZYX_AUTH_PRODUCTION", raising=False)
    results = run_doctor()
    names = {r.name for r in results}
    assert "phzyx.schema" in names
    assert "PHZYX_AUTH_SECRET" in names
