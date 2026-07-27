"""OpenAPI → portable client collection export smoke tests."""

from __future__ import annotations

from phzyx.admin.openapi_export import (
    count_operations,
    filter_openapi_paths,
    openapi_to_postman_collection,
)

MINI_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Demo", "version": "1.0.0"},
    "servers": [{"url": "http://127.0.0.1:9100"}],
    "paths": {
        "/admin/api/v1/meta": {
            "get": {
                "tags": ["adminboard"],
                "summary": "Meta",
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/api/items": {
            "get": {
                "tags": ["items"],
                "summary": "List items",
                "parameters": [
                    {
                        "name": "page",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "tags": ["items"],
                "summary": "Create item",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                            "example": {"name": "x"},
                        }
                    }
                },
                "responses": {"201": {"description": "created"}},
            },
        },
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer"},
        }
    },
}


def test_count_and_filter() -> None:
    assert count_operations(MINI_SPEC) == 3
    only_api = filter_openapi_paths(MINI_SPEC, path_prefix="/api")
    assert list(only_api["paths"].keys()) == ["/api/items"]
    assert count_operations(only_api) == 2


def test_postman_collection_shape() -> None:
    coll = openapi_to_postman_collection(MINI_SPEC, base_url="http://127.0.0.1:9100")
    assert coll["info"]["schema"].endswith("collection.json")
    assert coll["info"]["name"] == "Demo"
    assert isinstance(coll["item"], list)
    assert len(coll["item"]) >= 1
    # folders by tag
    names = {f["name"] for f in coll["item"]}
    assert "items" in names
    assert coll.get("auth", {}).get("type") == "bearer"
    assert any(v["key"] == "baseUrl" for v in coll["variable"])
