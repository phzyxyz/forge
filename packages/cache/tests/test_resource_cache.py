"""Resource version cache tests (S6.2)."""

from __future__ import annotations

import pytest
from phzyx.cache import MemoryCache, ResourceCache


@pytest.mark.unit
def test_list_cache_invalidate_on_version_bump() -> None:
    cache = ResourceCache(MemoryCache(), ttl=None)
    cache.set_list("users", [{"id": 1}])
    assert cache.get_list("users") == [{"id": 1}]
    cache.invalidate("users")
    assert cache.get_list("users") is None
    cache.set_list("users", [{"id": 2}])
    assert cache.get_list("users") == [{"id": 2}]


@pytest.mark.unit
def test_memory_ttl_expiry() -> None:
    import time

    mem = MemoryCache()
    mem.set("k", "v", ttl=1)
    assert mem.get("k") == "v"
    time.sleep(1.05)
    assert mem.get("k") is None
