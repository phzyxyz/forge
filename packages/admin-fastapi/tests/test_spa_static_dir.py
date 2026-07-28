"""AdminBoard SPA resolution for fat-wheel and monorepo layouts."""

from __future__ import annotations

from pathlib import Path

from phzyx.admin.fastapi.board import _spa_static_dir


def test_spa_static_dir_finds_monorepo_or_packaged() -> None:
    """Dev checkout should resolve packages/admin/web/dist when present."""
    found = _spa_static_dir()
    # In CI monorepo the SPA dist is committed/built under packages/admin/web/dist.
    assert found is not None, "SPA dist not found — build packages/admin/web"
    assert (found / "index.html").is_file()


def test_spa_static_dir_prefers_admin_web_dist(tmp_path: Path, monkeypatch) -> None:
    """Simulated fat-wheel layout: phzyx/admin/web/dist next to admin package."""
    import phzyx.admin.fastapi.board as board_mod

    admin_root = tmp_path / "phzyx" / "admin"
    fastapi_dir = admin_root / "fastapi"
    fastapi_dir.mkdir(parents=True)
    fake_board = fastapi_dir / "board.py"
    fake_board.write_text("# stub\n", encoding="utf-8")
    spa = admin_root / "web" / "dist"
    spa.mkdir(parents=True)
    (spa / "index.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(
        board_mod,
        "__file__",
        str(fake_board),
    )
    # Re-import path logic uses Path(__file__) inside function — call after patch.
    # board module's _spa_static_dir reads board_mod.__file__? It uses __file__ from
    # the function's global. Patch the module __file__.
    found = board_mod._spa_static_dir()
    assert found is not None
    assert found.resolve() == spa.resolve()
