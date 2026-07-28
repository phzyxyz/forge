# phzyx-forge

**Forge** — Phzyx data product. One install for schema, failsafe migrations, ORM, AdminBoard, and CLI.

## Install (PyPI)

```bash
uv add phzyx-forge                 # full product + SQLite
```

The **PyPI** distribution is a **fat wheel** (all core modules + AdminBoard SPA).  
Built by `scripts/build_pypi_release.py` — not this empty meta package.

Optional:

```bash
uv add 'phzyx-forge[auth]'     # or: uv add phzyx-auth
uv add 'phzyx-forge[cache]'    # or: uv add phzyx-cache
uv add 'phzyx-forge[postgres]' # etc.
uv add 'phzyx-forge[full]'     # all drivers + auth + cache + litestar
```

## Monorepo (developers)

In this workspace, `phzyx-forge` is a **meta package**: it depends on split packages
(`phzyx-schema`, `phzyx-engine`, `phzyx-orm`, …) for fast editable installs and tests.

Do **not** mix a fat wheel install into the monorepo `.venv` alongside those split packages.

## Imports

```python
from phzyx.schema.model import Model
from phzyx.orm import Session
from phzyx.admin.fastapi import AdminBoard
```

```bash
phzyx --help
```
