# phzyx-admin-litestar

**Not a separate PyPI project** — ships inside **`phzyx-forge`**. Use `uv add 'phzyx-forge[sqlite]'`.


Mount AdminBoard on **Litestar** (M6).

```python
from litestar import Litestar
from phzyx.admin.litestar import create_admin_router

app = Litestar(route_handlers=[create_admin_router(board_config)])
```

Path: `/python/litestar` on docs. Django: sync Session works; Phzyx is **not** a Django Admin replacement.
