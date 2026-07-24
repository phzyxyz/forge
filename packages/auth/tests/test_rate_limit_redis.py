"""RedisRateLimiter unit tests with a fake client (no redis required)."""

from __future__ import annotations

from typing import Any

import pytest
from phzyx.auth.rate_limit import MemoryRateLimiter, RedisRateLimiter


class FakeRedis:
    """Minimal INCR/EXPIRE client for unit tests."""

    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True


@pytest.mark.unit
def test_memory_rate_limiter_blocks() -> None:
    lim = MemoryRateLimiter()
    assert lim.hit("k", limit=2, window_seconds=60)
    assert lim.hit("k", limit=2, window_seconds=60)
    assert not lim.hit("k", limit=2, window_seconds=60)


@pytest.mark.unit
def test_redis_rate_limiter_fixed_window() -> None:
    client = FakeRedis()
    lim = RedisRateLimiter(client=client, key_prefix="t:")
    assert lim.hit("login", limit=3, window_seconds=60)
    assert lim.hit("login", limit=3, window_seconds=60)
    assert lim.hit("login", limit=3, window_seconds=60)
    assert not lim.hit("login", limit=3, window_seconds=60)
    # first hit set expire
    assert any(v >= 60 for v in client.ttls.values())


@pytest.mark.unit
def test_redis_rate_limiter_separate_keys() -> None:
    lim = RedisRateLimiter(client=FakeRedis())
    assert lim.hit("a", limit=1, window_seconds=30)
    assert not lim.hit("a", limit=1, window_seconds=30)
    assert lim.hit("b", limit=1, window_seconds=30)


@pytest.mark.unit
def test_redis_from_url_import_error_or_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """from_url either builds with redis or raises ImportError cleanly."""

    class _FakeMod:
        class Redis:
            @staticmethod
            def from_url(url: str, decode_responses: bool = False) -> Any:
                return FakeRedis()

    import sys

    monkeypatch.setitem(sys.modules, "redis", _FakeMod())  # type: ignore[arg-type]
    lim = RedisRateLimiter.from_url("redis://localhost:6379/0")
    assert lim.hit("x", limit=1, window_seconds=10)
    assert not lim.hit("x", limit=1, window_seconds=10)
