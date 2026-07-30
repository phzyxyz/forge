"""phzyx start helpers."""

from __future__ import annotations

from pathlib import Path

from phzyx.cli.start import ensure_dotenv, load_dotenv


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
