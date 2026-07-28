"""Diamond D6 — media library list + upload."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = ROOT / "examples" / "adminboard_live" / "main.py"


def _load_main(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, MAIN_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    media = tmp_path / "media"
    monkeypatch.setenv("PHZYX_DEMO_DB", str(db))
    monkeypatch.setenv("PHZYX_DEMO_MEDIA", str(media))
    monkeypatch.setenv("PHZYX_ADMIN_USER", "admin")
    monkeypatch.setenv("PHZYX_ADMIN_PASSWORD", "phzyx")
    mod = _load_main(f"adminboard_live_d6_{tmp_path.name}")
    from starlette.testclient import TestClient

    return TestClient(mod.app)


@pytest.mark.unit
def test_d6_library_lists_seed_media(client, auth) -> None:
    r = client.get("/admin/api/v1/files/library", headers=auth)
    assert r.status_code == 200
    body = r.json()
    keys = {i["key"] for i in body["items"]}
    assert "brand/logo.svg" in keys
    # Seed writes site/hero.svg (see examples/adminboard_live/main.py write_seed_media)
    assert "site/hero.svg" in keys
    logo = next(i for i in body["items"] if i["key"] == "brand/logo.svg")
    assert logo["mode"] == "image"


@pytest.mark.unit
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_d6_upload_and_list(client, auth) -> None:
    # multipart SpooledTemporaryFile cleanup can warn under filterwarnings=error
    r = client.post(
        "/admin/api/v1/files/upload",
        data={"key": "uploads/note.txt"},
        files={"file": ("note.txt", b"hello diamond d6", "text/plain")},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["key"] == "uploads/note.txt"
    lib = client.get(
        "/admin/api/v1/files/library",
        params={"folder": "uploads"},
        headers=auth,
    )
    assert lib.status_code == 200
    keys = {i["key"] for i in lib.json()["items"]}
    assert "uploads/note.txt" in keys
