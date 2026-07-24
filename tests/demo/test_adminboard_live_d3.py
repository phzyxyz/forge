"""Diamond D3 — live demo form schema + field-level 422."""

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
    mod = _load_main(f"adminboard_live_d3_{tmp_path.name}")
    from starlette.testclient import TestClient

    return TestClient(mod.app)


@pytest.mark.unit
def test_d3_schema_widgets_fieldsets(client, auth) -> None:
    r = client.get("/admin/api/v1/resources/users", headers=auth)
    assert r.status_code == 200
    body = r.json()
    cols = {c["name"]: c for c in body["columns"]}
    assert cols["active"]["widget"] == "bool"
    assert cols["joined"]["widget"] == "date"
    assert cols["notes"]["widget"] == "textarea"
    assert cols["email"].get("required") is True
    assert body.get("fieldsets")
    assert any(fs["name"] == "identity" for fs in body["fieldsets"])


@pytest.mark.unit
def test_d3_create_422_fields(client, auth) -> None:
    r = client.post(
        "/admin/api/v1/resources/users/records",
        headers=auth,
        json={"id": 999001},  # missing required email/name
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    fields = body["error"]["details"].get("fields") or {}
    assert fields, body
