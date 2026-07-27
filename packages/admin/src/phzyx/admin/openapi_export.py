"""OpenAPI helpers + portable client-collection export (no third-party deps).

Collection shape follows the common open collection JSON format used by many
API clients (schema URL retained for interoperability). Product UI never brands
third-party tools.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin


def filter_openapi_paths(
    spec: dict[str, Any],
    *,
    path_prefix: str | None = None,
    exclude_prefix: str | None = None,
) -> dict[str, Any]:
    """Return a shallow-copied OpenAPI doc with optional path filters."""
    out = dict(spec)
    paths = dict(spec.get("paths") or {})
    if path_prefix:
        pref = path_prefix if path_prefix.startswith("/") else f"/{path_prefix}"
        paths = {p: v for p, v in paths.items() if p.startswith(pref)}
    if exclude_prefix:
        excl = exclude_prefix if exclude_prefix.startswith("/") else f"/{exclude_prefix}"
        paths = {p: v for p, v in paths.items() if not p.startswith(excl)}
    out["paths"] = paths
    return out


def _example_from_schema(schema: dict[str, Any] | None) -> Any:
    if not schema or not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "examples" in schema and isinstance(schema["examples"], list) and schema["examples"]:
        return schema["examples"][0]
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties") or {}
        return {k: _example_from_schema(v) for k, v in list(props.items())[:12]}
    if t == "array":
        item = _example_from_schema(
            schema.get("items") if isinstance(schema.get("items"), dict) else None
        )
        return [item] if item is not None else []
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return True
    if t == "string":
        return "string"
    return None


def _postman_url(base: str, path: str, query_params: list[dict[str, Any]]) -> dict[str, Any]:
    # path may include {id} style params — Postman uses :id or {{id}}; keep {id} raw in raw URL
    raw_path = path if path.startswith("/") else f"/{path}"
    raw = urljoin(base.rstrip("/") + "/", raw_path.lstrip("/"))
    if not base.endswith("/") and raw_path.startswith("/"):
        raw = base.rstrip("/") + raw_path
    query = []
    for p in query_params:
        query.append(
            {
                "key": p.get("name") or "",
                "value": "" if p.get("example") is None else str(p.get("example")),
                "description": (p.get("description") or "")[:500],
                "disabled": not p.get("required", False),
            }
        )
    host = base.replace("https://", "").replace("http://", "").split("/")[0]
    protocol = "https" if base.startswith("https") else "http"
    path_parts = [seg for seg in raw_path.strip("/").split("/") if seg]
    return {
        "raw": raw + (("?" + "&".join(f"{q['key']}=" for q in query)) if query else ""),
        "protocol": protocol,
        "host": host.split("."),
        "path": path_parts,
        "query": query,
    }


def openapi_to_postman_collection(
    spec: dict[str, Any],
    *,
    base_url: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Convert OpenAPI 3.x dict → portable client collection JSON.

    Interoperable with tools that import the standard collection schema.
    Cookie/session auth is browser-only; collection auth uses bearer/apikey when present.
    """
    info = spec.get("info") or {}
    title = name or info.get("title") or "API"
    servers = spec.get("servers") or []
    if base_url:
        origin = base_url.rstrip("/")
    elif servers and isinstance(servers[0], dict) and servers[0].get("url"):
        origin = str(servers[0]["url"]).rstrip("/")
    else:
        origin = "{{baseUrl}}"

    # Group by first tag
    folders: dict[str, list[dict[str, Any]]] = {}
    paths = spec.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.startswith("x-") or method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue
            if not isinstance(op, dict):
                continue
            tags = op.get("tags") or ["default"]
            tag = str(tags[0]) if tags else "default"
            params = list(path_item.get("parameters") or []) + list(op.get("parameters") or [])
            query_params = [p for p in params if isinstance(p, dict) and p.get("in") == "query"]
            header_params = [p for p in params if isinstance(p, dict) and p.get("in") == "header"]
            summary = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"

            body: dict[str, Any] | None = None
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                content = rb.get("content") or {}
                app_json = content.get("application/json") or next(iter(content.values()), None)
                if isinstance(app_json, dict):
                    ex = app_json.get("example")
                    if ex is None and isinstance(app_json.get("examples"), dict):
                        first = next(iter(app_json["examples"].values()), None)
                        if isinstance(first, dict):
                            ex = first.get("value")
                    if ex is None:
                        ex = _example_from_schema(
                            app_json.get("schema")
                            if isinstance(app_json.get("schema"), dict)
                            else None
                        )
                    import json

                    body = {
                        "mode": "raw",
                        "raw": json.dumps(ex, indent=2) if ex is not None else "{}",
                        "options": {"raw": {"language": "json"}},
                    }

            headers = []
            for hp in header_params:
                headers.append(
                    {
                        "key": hp.get("name") or "",
                        "value": "",
                        "description": (hp.get("description") or "")[:300],
                    }
                )
            if body:
                headers.append({"key": "Content-Type", "value": "application/json"})

            item = {
                "name": summary,
                "request": {
                    "method": method.upper(),
                    "header": headers,
                    "url": _postman_url(
                        origin if origin != "{{baseUrl}}" else "http://localhost",
                        path,
                        query_params,
                    ),
                    "description": (op.get("description") or "")[:2000],
                },
                "response": [],
            }
            if body:
                item["request"]["body"] = body
            # Fix url raw when using placeholder
            if origin == "{{baseUrl}}":
                item["request"]["url"] = {
                    "raw": "{{baseUrl}}" + (path if path.startswith("/") else f"/{path}"),
                    "host": ["{{baseUrl}}"],
                    "path": [seg for seg in path.strip("/").split("/") if seg],
                    "query": item["request"]["url"].get("query") or [],
                }

            folders.setdefault(tag, []).append(item)

    collection_items: list[dict[str, Any]] = []
    for tag, items in sorted(folders.items(), key=lambda x: x[0].lower()):
        collection_items.append({"name": tag, "item": items})

    # Collection-level auth hint from components
    auth: dict[str, Any] | None = None
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    if isinstance(schemes, dict):
        for _name, scheme in schemes.items():
            if not isinstance(scheme, dict):
                continue
            st = scheme.get("type")
            if st == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
                auth = {
                    "type": "bearer",
                    "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
                }
                break
            if st == "apiKey":
                loc = scheme.get("in") or "header"
                key = scheme.get("name") or "X-API-Key"
                if loc == "header":
                    auth = {
                        "type": "apikey",
                        "apikey": [
                            {"key": "key", "value": key, "type": "string"},
                            {"key": "value", "value": "{{apiKey}}", "type": "string"},
                            {"key": "in", "value": "header", "type": "string"},
                        ],
                    }
                    break

    coll: dict[str, Any] = {
        "info": {
            "name": title,
            "description": (info.get("description") or "")[:4000]
            + "\n\nExported from Phzyx AdminBoard API docs. "
            "Browser cookie/session auth is not embedded; "
            "set bearer/apiKey variables in your client if needed.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": collection_items,
        "variable": [
            {
                "key": "baseUrl",
                "value": origin if origin != "{{baseUrl}}" else "http://127.0.0.1:8000",
            },
            {"key": "token", "value": ""},
            {"key": "apiKey", "value": ""},
        ],
    }
    if auth:
        coll["auth"] = auth
    return coll


def count_operations(spec: dict[str, Any]) -> int:
    n = 0
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in path_item:
            if method in {"get", "post", "put", "patch", "delete", "head", "options"}:
                n += 1
    return n
