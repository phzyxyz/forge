# phzyx

**Ecosystem install-all** meta package for the Phzyx brand.

```bash
uv add phzyx
# or
pip install phzyx
```

Pulls every **published** Phzyx product pin in this release line.  
Today that is the **Forge** stack (schema, engine, orm, admin, admin-fastapi, cli). When **Pulse** and other products publish, they are added here.

## Prefer a single product line?

```bash
uv add phzyx-forge   # Forge only
```

## Modular

```bash
uv add phzyx-orm
uv add phzyx-admin-fastapi
uv add phzyx-auth    # optional battery
```

Imports: `phzyx.schema`, `phzyx.orm`, `phzyx.admin.fastapi`, …
