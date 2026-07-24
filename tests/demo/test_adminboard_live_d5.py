"""Diamond D5 — action catalog + run API on live demo."""

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
    mod = _load_main(f"adminboard_live_d5_{tmp_path.name}")
    from starlette.testclient import TestClient

    return TestClient(mod.app)


@pytest.mark.unit
def test_d5_action_catalog_has_export_and_scopes(client, auth) -> None:
    r = client.get("/admin/api/v1/resources/users/actions", headers=auth)
    assert r.status_code == 200
    acts = r.json()
    names = {a["name"] for a in acts}
    assert "export_csv" in names
    assert "deactivate" in names
    scopes = {a["scope"] for a in acts}
    assert "global" in scopes and "bulk" in scopes and "row" in scopes
    globals_ = [a for a in acts if a["scope"] == "global"]
    assert all(a.get("client") for a in globals_)


@pytest.mark.unit
def test_d5_run_action_deactivate(client, auth) -> None:
    headers = auth
    listed = client.get(
        "/admin/api/v1/resources/users/records",
        params={"filter.active": "true", "page_size": 5},
        headers=headers,
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert items
    ident = items[0]["_identity"]
    run = client.post(
        "/admin/api/v1/resources/users/actions/run",
        headers=headers,
        json={"action": "deactivate", "identities": [ident]},
    )
    assert run.status_code == 200
    assert run.json()["updated"] >= 1
