"""phzyx add auth scaffold tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main


@pytest.mark.unit
def test_add_auth_dry_run(tmp_path: Path, capsys) -> None:
    code = main(["add", "auth", "--path", str(tmp_path), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert not (tmp_path / "app" / "forge" / "auth.py").exists()


@pytest.mark.unit
def test_add_auth_writes_files(tmp_path: Path) -> None:
    code = main(["add", "auth", "--path", str(tmp_path)])
    assert code == 0
    auth = tmp_path / "app" / "forge" / "auth.py"
    readme = tmp_path / "AUTH.md"
    assert auth.is_file()
    text = auth.read_text()
    assert "install_auth" in text
    assert "durable_auth_service" in text
    assert readme.is_file()
    code2 = main(["add", "auth", "--path", str(tmp_path)])
    assert code2 == 2
    code3 = main(["add", "auth", "--path", str(tmp_path), "--force"])
    assert code3 == 0
