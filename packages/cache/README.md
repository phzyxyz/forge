# phzyx-cache

Per-resource **version keys** for list caching. Writes bump the version so stale lists miss.

```python
from phzyx.cache import MemoryCache, ResourceCache

cache = ResourceCache(MemoryCache())
cache.set_list("users", "v1", [{"id": 1}])  # version auto-managed
cache.invalidate("users")  # on write
```

Redis:

```bash
uv add 'phzyx-cache[redis]'
```

**Limits:** only Phzyx write path invalidates; external DB writers can serve stale lists until TTL/version bump. Not a query cache for arbitrary SQL.
