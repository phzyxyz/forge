# phzyx-forge (workspace meta)

**Forge** — Phzyx data product. One install for schema, failsafe migrations, ORM, AdminBoard, and CLI.

## Public install (PyPI)

The **PyPI** distribution is a **fat wheel** built by `scripts/build_pypi_release.py`.  
Its long description is **`packaging/pypi/README.phzyx-forge.md`** (not this file).

```bash
uv add phzyx-forge
```

**Land here after install:** [https://phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started)  
**Docs hub:** [https://phzyx.xyz/forge](https://phzyx.xyz/forge)  
**Product home:** [https://phzyx.xyz](https://phzyx.xyz)

## Monorepo (developers)

In this workspace, `phzyx-forge` is a **meta package**: it depends on split packages
(`phzyx-schema`, `phzyx-engine`, `phzyx-orm`, …) for editable installs and tests.

Do **not** mix a fat wheel into the monorepo `.venv` alongside those split packages.

```python
from phzyx.schema.model import Model
from phzyx.orm import Session
from phzyx.admin.fastapi import AdminBoard
```
