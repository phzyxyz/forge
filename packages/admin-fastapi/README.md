# phzyx-admin-fastapi

```python
from phzyx.admin.fastapi import AdminBoard

AdminBoard(
    app,
    models=[User, Order],
    session_factory=get_session,
    theme="magical-white",  # or stellar-dark
)
```

API under `/admin/api/v1`. SPA under `/admin/` when `packages/admin/web/dist` exists.

See [docs/adminboard-quickstart.md](../../docs/adminboard-quickstart.md).
