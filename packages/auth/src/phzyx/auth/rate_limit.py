"""Rate limiter SPI — memory default; Redis optional extra."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Record a hit. Return True if under limit, False if exceeded."""
        ...


@dataclass
class MemoryRateLimiter:
    """Process-local sliding window counter."""

    _hits: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: Lock = field(default_factory=Lock)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            self._hits[key] = [t for t in bucket if t >= cutoff]
            if len(self._hits[key]) >= limit:
                return False
            self._hits[key].append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


@dataclass
class RedisRateLimiter:
    """Fixed-window counter via Redis INCR + EXPIRE.

    Uses a duck-typed client (``incr`` / ``expire`` / optional ``ttl``) so tests
    can inject a fake without installing redis. Real client: ``redis.Redis``.

    Lazy-imports ``redis`` only when constructed with a URL string.
    """

    client: Any
    key_prefix: str = "phzyx:rl:"

    @classmethod
    def from_url(cls, url: str, *, key_prefix: str = "phzyx:rl:") -> RedisRateLimiter:
        """Build from a Redis URL (requires ``phzyx-auth[redis]`` / ``redis`` package)."""
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "RedisRateLimiter requires the redis package — install phzyx-auth[redis]"
            ) from exc
        return cls(client=redis.Redis.from_url(url, decode_responses=True), key_prefix=key_prefix)

    def _full_key(self, key: str, window_seconds: int) -> str:
        # Fixed window: bucket by wall-clock epoch // window
        bucket = int(time.time()) // max(1, window_seconds)
        return f"{self.key_prefix}{key}:{window_seconds}:{bucket}"

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        rkey = self._full_key(key, window_seconds)
        count = int(self.client.incr(rkey))
        if count == 1:
            # First hit in this window — set TTL slightly past window end
            self.client.expire(rkey, max(1, window_seconds) + 1)
        return count <= limit
