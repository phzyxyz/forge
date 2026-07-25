# phzyx-forge

**Forge** — Phzyx data product meta package (install-all for the Forge line).

```bash
uv add phzyx-forge
# or
pip install phzyx-forge
```

## What you get

| Package | Role |
|---------|------|
| `phzyx-schema` | Pydantic models as schema truth |
| `phzyx-engine` | Introspect, push, migrate |
| `phzyx-orm` | Sessions, queries, FileField keys |
| `phzyx-admin` | AdminBoard headless core |
| `phzyx-admin-fastapi` | FastAPI AdminBoard mount |
| `phzyx-cli` | `phzyx` CLI |

Imports stay under **`phzyx.*`** (e.g. `from phzyx.orm import Session`).

## Related

| Command | Meaning |
|---------|---------|
| `uv add phzyx` | Entire Phzyx ecosystem meta (grows as products publish; today ≈ Forge set) |
| `uv add phzyx-orm` | Single modular package |
| `uv add phzyx-auth` | Optional identity (not included here) |

AdminBoard is a **sub-product of Forge**, not a separate install-all.
