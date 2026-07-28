# Phzyx

**Athul Nandaswaroop’s open-source ecosystem** — modular libraries under one brand tag, TanStack-shaped and polyglot by design.

**Brand:** Phzyx · **Flagship product:** **Forge** — Pydantic-native **schema · failsafe migrations · ORM · AdminBoard** for FastAPI-era backends.  
**Next product (later):** **Pulse** (background tasks). Imports stay `phzyx.*`.

> Define once in Pydantic. Use the best async drivers. Schema that won’t eat your data. Admin that feels intentional.

| | |
|--|--|
| **Brand hub** | [phzyx.xyz](https://phzyx.xyz) |
| **License** | MIT |
| **Python** | ≥ 3.11 (CI: 3.11–3.14) |
| **Tooling** | [uv](https://github.com/astral-sh/uv) workspace |
| **Status** | **M0–M7 done** · **M8 Forge restructure in progress** · **0.1.0 (pre-1.0)** |
| **GitHub** | **phzyxyz** · [`forge`](https://github.com/phzyxyz/forge) (product) · [`website`](https://github.com/phzyxyz/website) · [`docs`](https://github.com/phzyxyz/docs) |

---

## AdminBoard (sub-product of Forge)

**AdminBoard** is the operator UI for Forge models: headless admin + intentional SPA.

| Horizon | Reality |
|---------|---------|
| **Now / v1** | Python FastAPI (`phzyx.admin.fastapi` via `phzyx-forge`); Magical White + Stellar Dark |
| **Host** | `adminboard.phzyx.xyz` product pitch (website); docs under Forge |
| **Not claimed** | No fake non-Python releases |

See [ROADMAP.md](./ROADMAP.md) (M8).

---

## Install

```bash
# Product (fat wheel on PyPI: schema + engine + ORM + AdminBoard + CLI)
uv add 'phzyx-forge[sqlite,auth]'
# pip install 'phzyx-forge[sqlite,auth]'

# Optional batteries
uv add 'phzyx-auth'    # also: phzyx-forge[auth]
uv add 'phzyx-cache'   # also: phzyx-forge[cache]
```

**0.x contract:** public APIs may still change before 1.0. Pin versions in apps.

**Public PyPI names (only three):** `phzyx-forge` · `phzyx-auth` · `phzyx-cache`.  
Internal monorepo packages (`schema`, `orm`, …) ship **inside** the fat forge wheel — they are not separate PyPI projects.

Until packages are on PyPI, develop with `uv sync --all-packages --group dev` (this monorepo) or clone [`phzyxyz/forge`](https://github.com/phzyxyz/forge).  
**PyPI publish:** [`docs/ops/PYPI_PUBLISH.md`](./docs/ops/PYPI_PUBLISH.md) · **Make forge public:** [`docs/ops/FORGE_GO_PUBLIC.md`](./docs/ops/FORGE_GO_PUBLIC.md).  
Docs (MDX): [`content/forge/`](./content/forge/) · site routes `/forge/*` · Agents: [`llms.txt`](./llms.txt) · Security: [`SECURITY.md`](./SECURITY.md) · Changelog: [`CHANGELOG.md`](./CHANGELOG.md) · Ops: [`docs/ops/`](./docs/ops/)

---

## Packages

### Public (PyPI)

| PyPI | Role |
|------|------|
| **`phzyx-forge`** | Hero product (fat wheel on PyPI) |
| **`phzyx-auth`** | Auth battery |
| **`phzyx-cache`** | Cache battery |

### Monorepo layout (dev; modules ship inside forge on PyPI)

| Folder | Import / role |
|--------|----------------|
| `packages/schema` | `phzyx.schema` (internal) |
| `packages/engine` | `phzyx.engine` (internal) |
| `packages/orm` | `phzyx.orm` (internal) |
| `packages/admin` | `phzyx.admin` (internal) |
| `packages/admin-fastapi` | `phzyx.admin.fastapi` (internal) |
| `packages/admin-litestar` | `phzyx.admin.litestar` (internal, optional) |
| `packages/cli` | CLI `phzyx` (internal) |
| `packages/auth` | `phzyx.auth` → **PyPI** |
| `packages/cache` | `phzyx.cache` → **PyPI** |
| `packages/meta-forge` | workspace meta for `phzyx-forge` |

Namespace packages use **PEP 420** (`phzyx` has no root `__init__.py`). See [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## North-star DX (target)

```python
from phzyx.orm import Model, Field
from phzyx.admin.fastapi import AdminBoard
from fastapi import FastAPI

class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field(unique=True, index=True)

app = FastAPI()
AdminBoard(app, models=[User], theme="magical-white")
# primary themes: magical-white | stellar-dark
```

```bash
# phzyx db push              # local desired-state (safe defaults)
# phzyx migrate create -m "" # versioned SQL for teams/prod
# phzyx migrate apply
```

**M1 shipped in-tree:** define models with `phzyx.schema.Model` / `Field`, build a Manifest,
and emit CREATE TABLE for Postgres/SQLite. Walkthrough: site `/forge/schema` (MDX).
Push/migrate: `phzyx db push`, `phzyx migrate` — site `/forge/engine`.

---

## Develop

```bash
uv sync --all-packages --group dev
uv run pytest
uv run ruff check packages tests
uv run pyright
make cov       # line coverage ≥ 75% over packages (CI gate; ratchet to 80+)
uv run phzyx
```

CI required checks (once GitHub remote + branch protection): see `.github/workflows/ci.yml`.

- **Roadmap:** [ROADMAP.md](./ROADMAP.md) · interactive [PHZYX_ROADMAP.html](./PHZYX_ROADMAP.html)
- **Contributing craft:** [CODING_STANDARDS.md](./CODING_STANDARDS.md) · [CONTRIBUTING.md](./CONTRIBUTING.md)
- **Public agent map (packages):** [llms.txt](./llms.txt) · [llms-full.txt](./llms-full.txt)
- **Tasks:** `make check` / `just check` · hello example: `make hello`
- **Brand:** [brand/](./brand/)
---

## Themes (AdminBoard)

| Theme | Role |
|-------|------|
| **Magical White** | Primary light — enterprise daytime |
| **Stellar Dark** | Primary dark — enterprise ops / demos |
| **System Ambient** | Secondary — follows OS → maps to the two primaries |

---

## What ships later (not v1 critical path)

- ODM / OGM product lines  
- Rust as a **serving language** (separate from optional Python PyO3 accelerators)  
- AdminBoard ports beyond Python (same product name; idiomatic per language)  
- Algomax and other dream products  

Subdomains = dream products (`adminboard.phzyx.xyz`). Languages = **paths** only (`/python`, `/rust`).

## Hub & ops docs

| Doc | Role |
|-----|------|
| [sites/hub/](./sites/hub/) | Minimal brand hub page |
| [docs/ops/LAUNCH_0.1.0.md](./docs/ops/LAUNCH_0.1.0.md) | Launch / DNS / PyPI operator steps |
| [archive/mkdocs/](./archive/mkdocs/) | Legacy MkDocs (not public truth) |
---

## Steward

**Athul Nandaswaroop** — author and steward of Phzyx.
