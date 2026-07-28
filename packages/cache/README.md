# Phzyx Cache

**Versioned resource cache** (memory / Redis) for list-style read paths.

```bash
uv add 'phzyx-forge[cache]'
# or
uv add phzyx-cache
uv add 'phzyx-cache[redis]'   # Redis backend
```

---

## Full docs on the website

| | |
|--|--|
| **Cache guide** | [https://phzyx.xyz/forge/cache](https://phzyx.xyz/forge/cache) |
| **Forge docs** | [https://phzyx.xyz/forge](https://phzyx.xyz/forge) |
| **Getting started** | [https://phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started) |
| **Product home** | [https://phzyx.xyz](https://phzyx.xyz) |
| **Source** | [https://github.com/phzyxyz/forge](https://github.com/phzyxyz/forge) |

**After install → [phzyx.xyz/forge/cache](https://phzyx.xyz/forge/cache).**

---

## API (0.1)

```python
from phzyx.cache import MemoryCache, RedisCache, ResourceCache

cache = ResourceCache(MemoryCache(), ttl=60)
cache.set_list("users", [{"id": 1, "email": "a@example.com"}])
rows = cache.get_list("users")       # list[dict] | None
cache.invalidate("users")            # bump version → lists miss
```

| Class | Role |
|-------|------|
| `MemoryCache` | In-process string cache + optional TTL |
| `RedisCache` | Same API via Redis |
| `ResourceCache` | Versioned lists: `phzyx:res:{name}:v{N}:list:{suffix}` |

**You** invalidate on write. Not a SQL query cache. `MemoryCache` is per process.

---

## Related

- Product: [phzyx-forge](https://pypi.org/project/phzyx-forge/)  
- Auth: [phzyx-auth](https://pypi.org/project/phzyx-auth/)  
- Site: [phzyx.xyz](https://phzyx.xyz)

## License

MIT · [phzyx.xyz](https://phzyx.xyz)
