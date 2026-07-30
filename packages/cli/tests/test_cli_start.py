"""forge start helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from phzyx.cli.start import ensure_dotenv, load_dotenv, _prompt_yes_no


def test_ensure_dotenv_copies_example(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(
        "PHZYX_DATABASE_URL=sqlite:///./dev.db\nPHZYX_AUTH_SECRET=\n",
        encoding="utf-8",
    )
    assert ensure_dotenv(tmp_path) is True
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "PHZYX_DATABASE_URL=sqlite" in env
    assert "PHZYX_AUTH_SECRET=" in env
    # second call no-op
    assert ensure_dotenv(tmp_path) is False


def test_load_dotenv_sets_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PHZYX_TEST_ONLY", raising=False)
    (tmp_path / ".env").write_text("PHZYX_TEST_ONLY=hello\n", encoding="utf-8")
    load_dotenv(tmp_path)
    import os

    assert os.environ.get("PHZYX_TEST_ONLY") == "hello"


def test_prompt_yes_no_default_false(monkeypatch) -> None:
    import io

    assert (
        _prompt_yes_no(
            "Apply?",
            default=False,
            input_stream=io.StringIO("\n"),
            output_stream=io.StringIO(),
        )
        is False
    )
    assert (
        _prompt_yes_no(
            "Apply?",
            default=False,
            input_stream=io.StringIO("y\n"),
            output_stream=io.StringIO(),
        )
        is True
    )


def test_prompt_yes_no_non_tty_empty_is_no() -> None:
    import io

    # StringIO is not a TTY + empty answer → never default-yes
    out = io.StringIO()
    assert (
        _prompt_yes_no(
            "Apply?",
            default=True,
            input_stream=io.StringIO("\n"),
            output_stream=out,
        )
        is False
    )
    assert "non-interactive" in out.getvalue()


def test_prompt_yes_no_piped_yes() -> None:
    import io

    assert (
        _prompt_yes_no(
            "Apply?",
            default=False,
            input_stream=io.StringIO("yes\n"),
            output_stream=io.StringIO(),
        )
        is True
    )


def _write_minimal_app_package(root: Path) -> None:
    """Mirror a ``package = false`` scaffold: plain app/ tree, not installed."""
    (root / "app").mkdir()
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "forge").mkdir()
    (root / "app" / "forge" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "forge" / "models.py").write_text(
        "from phzyx.schema import Field, Model\n\n"
        "class Item(Model):\n"
        "    id: int | None = Field(default=None, primary_key=True)\n"
        "    name: str = Field(default='')\n\n"
        "    class Meta:\n"
        "        table = 'items'\n",
        encoding="utf-8",
    )
    (root / "app" / "forge" / "registry.py").write_text(
        "from app.forge.models import Item\n\nALL_MODELS = [Item]\n",
        encoding="utf-8",
    )


@pytest.mark.unit
def test_load_models_works_without_installed_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: console scripts don't put cwd on sys.path (0.1.3 ModuleNotFoundError)."""
    from phzyx.cli import _load_models, ensure_project_on_sys_path

    _write_minimal_app_package(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Simulate entry-point process: no project root / empty-string cwd entry.
    root_s = str(tmp_path.resolve())
    cleaned = [p for p in sys.path if p not in {"", root_s} and Path(p).resolve() != tmp_path.resolve()]
    monkeypatch.setattr(sys, "path", cleaned)

    with pytest.raises(ModuleNotFoundError):
        import importlib

        importlib.import_module("app.forge.registry")

    ensure_project_on_sys_path(tmp_path)
    models = _load_models("app.forge.registry:ALL_MODELS")
    assert len(models) == 1
    assert models[0].__name__ == "Item"


@pytest.mark.unit
def test_start_schema_preview_loads_app_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """forge start schema path must import app.forge.registry after chdir."""
    import io

    from phzyx.cli.start import start_app

    _write_minimal_app_package(tmp_path)
    (tmp_path / ".env").write_text(
        f"PHZYX_DATABASE_URL=sqlite:///{tmp_path / 'dev.db'}\nPHZYX_ENV=development\n",
        encoding="utf-8",
    )

    # Drop project root from path like a real console-script process.
    root_s = str(tmp_path.resolve())
    cleaned = [p for p in sys.path if p not in {"", root_s} and Path(p).resolve() != tmp_path.resolve()]
    monkeypatch.setattr(sys, "path", cleaned)
    monkeypatch.chdir(tmp_path.parent)  # start_app chdirs to root

    # Skip uvicorn: fail after schema handling by monkeypatching subprocess.
    def _no_server(cmd, **kwargs):  # noqa: ANN001
        return 0

    monkeypatch.setattr("phzyx.cli.start.subprocess.call", _no_server)

    # Non-interactive: empty schema or "start without apply" both OK for fresh db.
    code = start_app(
        root=tmp_path,
        check_schema=True,
        check_migrate=False,
        reload=False,
        input_stream=io.StringIO("y\n"),  # apply schema if prompted
        output_stream=io.StringIO(),
    )
    assert code == 0
