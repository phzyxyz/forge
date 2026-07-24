"""Per-resource versioned list cache."""

from __future__ import annotations

from typing import Any

from phzyx.cache.backends import CacheBackend, dumps, loads


class ResourceCache:
    """Cache lists under ``phzyx:res:{name}:v{version}:list:{suffix}``.

    ``invalidate(resource)`` bumps the version so all prior list keys miss.
    """

    def __init__(
        self, backend: CacheBackend, *, prefix: str = "phzyx", ttl: int | None = 60
    ) -> None:
        self.backend = backend
        self.prefix = prefix
        self.ttl = ttl

    def _ver_key(self, resource: str) -> str:
        return f"{self.prefix}:res:{resource}:version"

    def version(self, resource: str) -> int:
        raw = self.backend.get(self._ver_key(resource))
        return int(raw or "1")

    def invalidate(self, resource: str) -> int:
        """Bump resource version; returns new version."""
        v = self.version(resource) + 1
        self.backend.set(self._ver_key(resource), str(v))
        return v

    def _list_key(self, resource: str, suffix: str) -> str:
        return f"{self.prefix}:res:{resource}:v{self.version(resource)}:list:{suffix}"

    def get_list(self, resource: str, suffix: str = "default") -> list[dict[str, Any]] | None:
        raw = self.backend.get(self._list_key(resource, suffix))
        if raw is None:
            return None
        data = loads(raw)
        return data if isinstance(data, list) else None

    def set_list(
        self,
        resource: str,
        rows: list[dict[str, Any]],
        *,
        suffix: str = "default",
    ) -> None:
        self.backend.set(self._list_key(resource, suffix), dumps(rows), ttl=self.ttl)
