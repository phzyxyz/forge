"""Diamond D4 — live demo FK autocomplete + relation panel API."""

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
    mod = _load_main(f"adminboard_live_d4_{tmp_path.name}")
    from starlette.testclient import TestClient

    return TestClient(mod.app)


@pytest.mark.unit
def test_d4_posts_fk_schema(client, auth) -> None:
    r = client.get("/admin/api/v1/resources/posts", headers=auth)
    assert r.status_code == 200
    body = r.json()
    cols = {c["name"]: c for c in body["columns"]}
    assert cols["author_id"]["widget"] == "fk"
    assert cols["author_id"]["fk_resource"] == "users"


@pytest.mark.unit
def test_d4_users_relations(client, auth) -> None:
    r = client.get("/admin/api/v1/resources/users", headers=auth)
    assert r.status_code == 200
    rels = {x["name"] for x in r.json().get("relations") or []}
    assert "memberships" in rels
    assert "posts" in rels


@pytest.mark.unit
def test_d4_autocomplete_users(client, auth) -> None:
    r = client.get(
        "/admin/api/v1/resources/users/autocomplete",
        params={"q": "ops"},
        headers=auth,
    )
    assert r.status_code == 200
    opts = r.json()
    assert opts
    assert any("ops" in str(o.get("label", "")).lower() for o in opts)


@pytest.mark.unit
def test_d4_list_user_posts_relation(client, auth) -> None:
    r = client.get(
        "/admin/api/v1/resources/users/records/1/relations/posts",
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert all(item.get("author_id") == 1 for item in data["items"])
