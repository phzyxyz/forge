"""Diamond D2 — live demo API filters, bulk actions, keyset mode."""

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
    mod = _load_main(f"adminboard_live_d2_{tmp_path.name}")
    from starlette.testclient import TestClient

    return TestClient(mod.app)


@pytest.mark.unit
def test_d2_schema_exposes_filterable(client, auth) -> None:
    r = client.get("/admin/api/v1/resources/users", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "active" in body.get("filterable", []) or any(
        c.get("name") == "active" and c.get("filterable") for c in body["columns"]
    )


@pytest.mark.unit
def test_d2_filter_query_param(client, auth) -> None:
    r = client.get(
        "/admin/api/v1/resources/users/records",
        params={"filter.active": "true"},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["filters"].get("active") == "true"
    assert data["total"] >= 1
    assert all(item.get("active") is True for item in data["items"])


@pytest.mark.unit
def test_d2_list_actions_and_bulk_deactivate(client, auth) -> None:
    headers = auth
    acts = client.get("/admin/api/v1/resources/users/actions", headers=headers)
    assert acts.status_code == 200
    names = {a["name"] for a in acts.json()}
    assert "deactivate" in names

    listed = client.get(
        "/admin/api/v1/resources/users/records",
        params={"filter.active": "true", "page_size": 50},
        headers=headers,
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert items
    identities = [i["_identity"] for i in items[:1]]
    bulk = client.post(
        "/admin/api/v1/resources/users/bulk",
        headers=headers,
        json={"action": "deactivate", "identities": identities},
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated"] >= 1

    again = client.get(
        "/admin/api/v1/resources/users/records",
        params={"filter.active": "true"},
        headers=headers,
    )
    remaining = {i["_identity"] for i in again.json()["items"]}
    assert identities[0] not in remaining


@pytest.mark.unit
def test_d2_keyset_pagination_param(client, auth) -> None:
    r = client.get(
        "/admin/api/v1/resources/users/records",
        params={"pagination": "keyset", "page_size": 1},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["pagination"] == "keyset"
    assert len(data["items"]) == 1
    if data.get("has_more") and data.get("next_cursor"):
        r2 = client.get(
            "/admin/api/v1/resources/users/records",
            params={
                "pagination": "keyset",
                "page_size": 1,
                "cursor": data["next_cursor"],
            },
            headers=auth,
        )
        assert r2.status_code == 200
        assert r2.json()["items"][0]["_identity"] != data["items"][0]["_identity"]
