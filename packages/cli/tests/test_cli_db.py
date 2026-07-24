"""CLI smoke for db status / push dry-run (SS2.1.6 / SS2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main


@pytest.mark.integration
@pytest.mark.sqlite
def test_cli_db_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "c.db"
    code = main(["db", "status", "--database-url", f"sqlite:///{db}"])
    assert code == 0
    out = capsys.readouterr().out
    assert "sqlite" in out
    assert "capabilities" in out


@pytest.mark.unit
def test_cli_help() -> None:
    # argparse help exits via SystemExit in some versions; we just ensure main([]) ok
    assert main([]) == 0
