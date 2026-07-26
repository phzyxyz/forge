"""Scaffold detect edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli.scaffold.detect import detect, is_effectively_empty
from phzyx.cli.scaffold.types import ScaffoldMode


@pytest.mark.unit
def test_missing_dir_is_empty(tmp_path: Path) -> None:
    root = tmp_path / "nope"
    assert is_effectively_empty(root)
    d = detect(root)
    assert d.mode is ScaffoldMode.FRESH
    assert d.is_empty


@pytest.mark.unit
def test_only_git_is_empty(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert is_effectively_empty(tmp_path)
    assert detect(tmp_path).mode is ScaffoldMode.FRESH


@pytest.mark.unit
def test_readme_only_is_emptyish(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    assert is_effectively_empty(tmp_path)
    assert detect(tmp_path).mode is ScaffoldMode.FRESH


@pytest.mark.unit
def test_code_is_existing(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("x", encoding="utf-8")
    assert not is_effectively_empty(tmp_path)
    assert detect(tmp_path).mode is ScaffoldMode.EXISTING_ISLAND


@pytest.mark.unit
def test_already_init(tmp_path: Path) -> None:
    forge = tmp_path / "app" / "forge"
    forge.mkdir(parents=True)
    (forge / ".phzyx-forge").write_text("v1\n", encoding="utf-8")
    (forge / "db.py").write_text("x", encoding="utf-8")
    (forge / "models.py").write_text("x", encoding="utf-8")
    (forge / "registry.py").write_text("x", encoding="utf-8")
    (forge / "__init__.py").write_text("def mount_forge(app): ...\n", encoding="utf-8")
    assert detect(tmp_path).mode is ScaffoldMode.ALREADY_INIT


@pytest.mark.unit
def test_file_path_raises(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("a", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        detect(f)
