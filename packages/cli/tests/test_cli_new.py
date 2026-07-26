"""phzyx new + layout scaffold tests (compat)."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main
from phzyx.cli.scaffold.presets import LAYOUT_NAMES, PRESET_NAMES


@pytest.mark.unit
def test_new_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "new",
            "demoapp",
            "--path",
            str(tmp_path),
            "--preset",
            "minimal",
            "--layout",
            "forge",
            "--dry-run",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert "pyproject.toml" in out
    assert "main.py" in out


@pytest.mark.unit
def test_new_writes_max_forge(tmp_path: Path) -> None:
    code = main(
        [
            "new",
            "myapp",
            "--path",
            str(tmp_path),
            "--preset",
            "max",
            "--layout",
            "forge",
            "--yes",
        ]
    )
    assert code == 0
    root = tmp_path / "myapp"
    assert (root / "pyproject.toml").is_file()
    assert (root / "app" / "main.py").is_file()
    assert (root / "app" / "forge" / "auth.py").is_file()
    assert (root / "app" / "forge" / "admin.py").is_file()
    code2 = main(["new", "myapp", "--path", str(tmp_path), "--preset", "max", "--no-input"])
    assert code2 == 2


@pytest.mark.unit
def test_new_layouts_alias_to_forge(tmp_path: Path) -> None:
    for layout in LAYOUT_NAMES:
        code = main(
            [
                "new",
                f"x{layout.replace('-', '')}",
                "--path",
                str(tmp_path),
                "--preset",
                "minimal",
                "--layout",
                layout,
                "--yes",
            ]
        )
        assert code == 0
        name = f"x{layout.replace('-', '')}"
        assert (tmp_path / name / "app" / "forge" / "db.py").is_file()


@pytest.mark.unit
def test_new_full_docker(tmp_path: Path) -> None:
    code = main(
        [
            "new",
            "fullapp",
            "--path",
            str(tmp_path),
            "--preset",
            "full",
            "--yes",
        ]
    )
    assert code == 0
    assert (tmp_path / "fullapp" / "docker-compose.yml").is_file()


@pytest.mark.unit
def test_preset_names_complete() -> None:
    assert set(PRESET_NAMES) == {"minimal", "normal", "max", "full"}
