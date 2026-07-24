"""Smoke tests for phzyx-cli package layout."""

from __future__ import annotations

import pytest
from phzyx.cli import __version__, main


@pytest.mark.unit
def test_cli_version_string() -> None:
    assert isinstance(__version__, str)
    assert __version__


@pytest.mark.unit
def test_cli_main_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out.lower()
    assert "phzyx" in out
    assert "db" in out or "migrate" in out
