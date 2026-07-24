"""phzyx add admin scaffold tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main


@pytest.mark.unit
def test_add_admin_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["add", "admin", "--path", str(tmp_path), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert not (tmp_path / "admin_board.py").exists()


@pytest.mark.unit
def test_add_admin_writes_files(tmp_path: Path) -> None:
    code = main(["add", "admin", "--path", str(tmp_path)])
    assert code == 0
    admin = tmp_path / "admin_board.py"
    readme = tmp_path / "ADMIN.md"
    assert admin.is_file()
    assert "mount_admin" in admin.read_text()
    assert "AdminBoard" in admin.read_text()
    assert readme.is_file()
    code2 = main(["add", "admin", "--path", str(tmp_path)])
    assert code2 == 2
    code3 = main(["add", "admin", "--path", str(tmp_path), "--force"])
    assert code3 == 0
