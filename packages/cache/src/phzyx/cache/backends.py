"""Cache backends — memory and optional Redis."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, *, ttl: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass
class MemoryCache:
    """Process-local cache with optional TTL."""

    _data: dict[str, tuple[str, float | None]] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and time.time() > expires:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, *, ttl: int | None = None) -> None:
        exp = time.time() + ttl if ttl else None
        self._data[key] = (value, exp)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class RedisCache:
    """Redis string cache (optional redis package)."""

    def __init__(self, client: Any | None = None, *, url: str = "redis://localhost:6379/0") -> None:
        if client is not None:
            self._client = client
        else:
            try:
                import redis  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover
                raise ImportError("uv add 'phzyx-cache[redis]'") from exc
            self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> str | None:
        val = self._client.get(key)
        return None if val is None else str(val)

    def set(self, key: str, value: str, *, ttl: int | None = None) -> None:
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def loads(raw: str) -> Any:
    return json.loads(raw)
