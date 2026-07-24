"""Diamond D1 — live demo reliability invariants."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = ROOT / "examples" / "adminboard_live" / "main.py"


def _load_main(module_name: str = "adminboard_live_main_d1"):
    """Load demo main.py as a fresh module (paths from env already set)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, MAIN_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def demo_mod(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    media = tmp_path / "media"
    monkeypatch.setenv("PHZYX_DEMO_DB", str(db))
    monkeypatch.setenv("PHZYX_DEMO_MEDIA", str(media))
    monkeypatch.setenv("PHZYX_ADMIN_USER", "admin")
    monkeypatch.setenv("PHZYX_ADMIN_PASSWORD", "phzyx")
    return _load_main(f"adminboard_live_{tmp_path.name}")


@pytest.fixture
def client(demo_mod):
    from starlette.testclient import TestClient

    return TestClient(demo_mod.app)


@pytest.mark.unit
def test_d1_401_has_no_www_authenticate(client) -> None:
    """SS-D1.1: SPA-owned login — never challenge with Basic realm."""
    r = client.get("/admin/api/v1/meta")
    assert r.status_code == 401
    headers = {k.lower(): v for k, v in r.headers.items()}
    assert "www-authenticate" not in headers
    assert r.headers.get("content-type", "").startswith("application/json")
    body = r.json()
    assert body.get("error", {}).get("code") == "unauthorized"


@pytest.mark.unit
def test_d1_401_invalid_password_no_www_authenticate(client) -> None:
    r = client.post(
        "/auth/login",
        json={"email": "admin", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert "www-authenticate" not in {k.lower() for k in r.headers}
    r2 = client.get("/admin/api/v1/meta")
    assert r2.status_code == 401


@pytest.mark.unit
def test_d1_auth_ok_meta(client, auth) -> None:
    headers = auth
    r = client.get("/admin/api/v1/meta", headers=headers)
    assert r.status_code == 200
    assert "version" in r.json()


@pytest.mark.unit
def test_d1_seed_media_files_exist(demo_mod, tmp_path) -> None:
    """SS-D1.2: every seeded asset key has bytes on disk."""
    media = Path(demo_mod.app.state.phzyx_demo_media)
    for key in demo_mod.SEED_ASSET_KEYS:
        path = media / key
        assert path.is_file(), f"missing seed media: {key}"
        assert path.stat().st_size > 0


@pytest.mark.unit
def test_d1_seed_asset_rows_match_files(client, demo_mod, auth) -> None:
    headers = auth
    r = client.get("/admin/api/v1/resources/assets/records", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    media = Path(demo_mod.app.state.phzyx_demo_media)
    assert len(items) >= 1
    for row in items:
        key = str(row.get("path") or "")
        assert key, row
        assert (media / key).is_file(), f"DB key without file: {key}"


@pytest.mark.unit
def test_d1_download_seed_logo(client, auth) -> None:
    headers = auth
    r = client.get(
        "/admin/api/v1/files/download",
        params={"key": "brand/logo.svg"},
        headers=headers,
    )
    assert r.status_code == 200
    assert b"<svg" in r.content


@pytest.mark.unit
def test_d1_health_public(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.unit
def test_d1_write_seed_media_idempotent(tmp_path, demo_mod) -> None:
    media = Path(demo_mod.app.state.phzyx_demo_media)
    first = demo_mod.write_seed_media(media)
    second = demo_mod.write_seed_media(media)
    assert {p.name for p in first} == {p.name for p in second}
    for p in second:
        assert p.is_file()
