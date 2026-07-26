"""phzyx new + forge init scaffold tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from phzyx.cli import main


@pytest.mark.unit
def test_new_max_writes_forge_layout(tmp_path: Path) -> None:
    code = main(
        [
            "new",
            "myapp",
            "--path",
            str(tmp_path),
            "--preset",
            "max",
            "--yes",
        ]
    )
    assert code == 0
    root = tmp_path / "myapp"
    assert (root / "app" / "main.py").is_file()
    assert (root / "app" / "forge" / "db.py").is_file()
    assert (root / "app" / "forge" / "registry.py").is_file()
    assert (root / "app" / "forge" / "admin.py").is_file()
    assert (root / "app" / "forge" / "auth.py").is_file()
    assert (root / "app" / "api" / "routes" / "items.py").is_file()
    assert (root / "SECURITY.md").is_file()
    main_txt = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert "async def" not in main_txt or "lifespan" in main_txt
    assert "mount_forge" in main_txt
    assert "def root(" not in main_txt  # no sync hello route
    items = (root / "app" / "api" / "routes" / "items.py").read_text(encoding="utf-8")
    assert "async def" in items
    assert "AsyncSession" in items
    assert "session_sync" not in items
    models = (root / "app" / "forge" / "models.py").read_text(encoding="utf-8")
    assert "int | None" in models
    assert "primary_key=True" in models
    assert "Large apps" in models or "registry" in models.lower()


@pytest.mark.unit
def test_new_invalid_name(tmp_path: Path) -> None:
    code = main(["new", "123bad", "--path", str(tmp_path)])
    assert code == 2


@pytest.mark.unit
def test_new_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["new", "demo", "--path", str(tmp_path), "--preset", "minimal", "--dry-run"])
    assert code == 0
    assert "would write" in capsys.readouterr().out
    assert not (tmp_path / "demo").exists() or not any((tmp_path / "demo").rglob("main.py"))


@pytest.mark.unit
def test_new_nonempty_refuses(tmp_path: Path) -> None:
    dest = tmp_path / "taken"
    dest.mkdir()
    (dest / "code.py").write_text("x", encoding="utf-8")
    code = main(["new", "taken", "--path", str(tmp_path), "--no-input"])
    assert code == 2


@pytest.mark.unit
def test_legacy_layout_still_works(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "new",
            "leg",
            "--path",
            str(tmp_path),
            "--layout",
            "mvc",
            "--preset",
            "minimal",
            "--yes",
        ]
    )
    assert code == 0
    assert (tmp_path / "leg" / "app" / "forge" / "db.py").is_file()


@pytest.mark.unit
def test_forge_init_empty(tmp_path: Path) -> None:
    code = main(["forge", "init", "--path", str(tmp_path), "--name", "demo", "--yes"])
    assert code == 0
    assert (tmp_path / "app" / "forge" / ".phzyx-forge").is_file()


@pytest.mark.unit
def test_forge_init_existing_island(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    code = main(["forge", "init", "--path", str(tmp_path), "--yes", "--preset", "minimal"])
    assert code == 0
    assert (tmp_path / "app" / "forge" / "db.py").is_file()
    # main left alone without patch
    main_txt = (tmp_path / "app" / "main.py").read_text(encoding="utf-8")
    assert "mount_forge" not in main_txt


@pytest.mark.unit
def test_forge_init_already_refuses(tmp_path: Path) -> None:
    main(["forge", "init", "--path", str(tmp_path), "--name", "x", "--yes"])
    code = main(["forge", "init", "--path", str(tmp_path), "--yes", "--no-input"])
    assert code == 2


@pytest.mark.unit
def test_generated_security_markers(tmp_path: Path) -> None:
    main(["new", "sec", "--path", str(tmp_path), "--preset", "max", "--yes"])
    root = tmp_path / "sec"
    db = (root / "app" / "forge" / "db.py").read_text(encoding="utf-8")
    assert "from phzyx.orm import" in db
    assert "session_sync" not in db
    admin = (root / "app" / "forge" / "admin.py").read_text(encoding="utf-8")
    assert "authz_for_admin" in admin
    schemas = (root / "app" / "api" / "schemas" / "items.py").read_text(encoding="utf-8")
    assert "extra" in schemas and "forbid" in schemas
