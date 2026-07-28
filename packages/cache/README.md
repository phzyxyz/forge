# Phzyx Cache

**Versioned resource cache** (memory / Redis) for list-style read paths in Phzyx apps.

Optional battery — install with Forge when you need it:

```bash
uv add 'phzyx-forge[cache]'
# or
uv add phzyx-cache
```

---

## Full docs live on the website

PyPI is the install surface. Architecture notes, production patterns, and product context:

| | |
|--|--|
| **Cache guide** | [https://phzyx.xyz/forge/cache](https://phzyx.xyz/forge/cache) |
| **Forge docs** | [https://phzyx.xyz/forge](https://phzyx.xyz/forge) |
| **Getting started** | [https://phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started) |
| **Product home** | [https://phzyx.xyz](https://phzyx.xyz) |
| **Source** | [https://github.com/phzyxyz/forge](https://github.com/phzyxyz/forge) |

**After install → open [phzyx.xyz/forge/cache](https://phzyx.xyz/forge/cache).**

---

## Install

```bash
uv add phzyx-cache
uv add 'phzyx-cache[redis]'   # Redis backend
# or via Forge
uv add 'phzyx-forge[cache]'
```

---

## Idea

Per-resource **version keys** for list caching. Writes bump the version so stale lists miss cleanly.

```python
from phzyx.cache import MemoryCache, ResourceCache

cache = ResourceCache(MemoryCache())
cache.set_list("users", "v1", [{"id": 1}])  # version auto-managed
cache.invalidate("users")  # on write
```

**Limits:** invalidation follows your Phzyx write path; external DB writers can leave lists stale until TTL / version bump. Not a general SQL query cache.

More detail: **[Cache guide](https://phzyx.xyz/forge/cache)**.

---

## Related

- Product: [phzyx-forge](https://pypi.org/project/phzyx-forge/)  
- Auth battery: [phzyx-auth](https://pypi.org/project/phzyx-auth/)  
- Site: [phzyx.xyz](https://phzyx.xyz)

## License

MIT · [phzyx.xyz](https://phzyx.xyz)
