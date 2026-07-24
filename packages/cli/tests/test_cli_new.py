"""phzyx new + layout scaffold tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main
from phzyx.cli.new import plan_new
from phzyx.cli.presets import LAYOUT_NAMES, PRESET_NAMES


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
            "flat",
            "--dry-run",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert "pyproject.toml" in out
    assert "main.py" in out
    assert not (tmp_path / "demoapp").exists()


@pytest.mark.unit
def test_new_writes_flat_normal(tmp_path: Path) -> None:
    code = main(
        [
            "new",
            "myapp",
            "--path",
            str(tmp_path),
            "--preset",
            "normal",
            "--layout",
            "flat",
        ]
    )
    assert code == 0
    root = tmp_path / "myapp"
    assert (root / "pyproject.toml").is_file()
    assert (root / "README.md").is_file()
    assert (root / "app" / "main.py").is_file()
    assert (root / "app" / "auth.py").is_file()
    assert "install_auth" in (root / "app" / "auth.py").read_text()
    assert "phzyx-auth" in (root / "pyproject.toml").read_text()
    # refuse second create without force
    code2 = main(
        ["new", "myapp", "--path", str(tmp_path), "--preset", "normal", "--layout", "flat"]
    )
    assert code2 == 2


@pytest.mark.unit
def test_new_layouts_plan_paths(tmp_path: Path) -> None:
    for layout in LAYOUT_NAMES:
        planned = plan_new("x", preset="minimal", layout=layout, parent=tmp_path)
        rels = {str(p.relative_to(tmp_path / "x")) for p, _ in planned}
        assert "pyproject.toml" in rels
        assert "README.md" in rels
        if layout == "flat":
            assert "app/main.py" in rels
        elif layout == "mvc":
            assert "app/models/__init__.py" in rels
            assert "app/views/__init__.py" in rels
            assert "app/controllers/__init__.py" in rels
        elif layout == "clean":
            assert "domain/__init__.py" in rels
            assert "application/__init__.py" in rels
            assert "infrastructure/__init__.py" in rels
            assert "app/main.py" in rels
        elif layout == "phzyx-app":
            assert "packages/README.md" in rels
            assert "app/main.py" in rels


@pytest.mark.unit
def test_new_max_includes_admin(tmp_path: Path) -> None:
    code = main(
        [
            "new",
            "maxapp",
            "--path",
            str(tmp_path),
            "--preset",
            "max",
            "--layout",
            "flat",
        ]
    )
    assert code == 0
    root = tmp_path / "maxapp"
    assert (root / "app" / "admin_board.py").is_file()
    assert (root / "ADMIN.md").is_file()
    assert "mount_admin" in (root / "app" / "admin_board.py").read_text()


@pytest.mark.unit
def test_new_full_docker(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "new",
            "fullapp",
            "--path",
            str(tmp_path),
            "--preset",
            "full",
            "--layout",
            "phzyx-app",
            "--dry-run",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "docker-compose.yml" in out
    planned = plan_new("fullapp", preset="full", layout="phzyx-app", parent=tmp_path)
    names = [p.name for p, _ in planned]
    assert "docker-compose.yml" in names


@pytest.mark.unit
def test_preset_names_complete() -> None:
    assert set(PRESET_NAMES) == {"minimal", "normal", "max", "full"}
