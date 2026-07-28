# Forge

**Phzyx Forge** — open-source Python stack for FastAPI-era backends:

**Pydantic schema · failsafe migrations · dual sync/async ORM · AdminBoard · CLI · API Board**

| | |
|--|--|
| **Brand** | [Phzyx](https://phzyx.xyz) |
| **Docs** | [Getting started](https://phzyx.xyz/forge/getting-started) · [full map](https://phzyx.xyz/forge) |
| **Agents** | [`llms.txt`](./llms.txt) · [site llms.txt](https://phzyx.xyz/llms.txt) |
| **License** | [MIT](./LICENSE) |
| **Python** | ≥ 3.11 (CI: 3.11–3.14) |
| **Status** | **0.1.0** pre-1.0 — APIs may still change; **pin versions** |
| **Org** | [github.com/phzyxyz](https://github.com/phzyxyz) |

Imports are always **`phzyx.*`** (product name ≠ import path).

---

## Install

```bash
# Product (fat wheel on PyPI)
uv add 'phzyx-forge[sqlite,auth]==0.1.0'

# Optional batteries
uv add 'phzyx-auth==0.1.0'
uv add 'phzyx-cache==0.1.0'
```

**Public PyPI names only:** `phzyx-forge` · `phzyx-auth` · `phzyx-cache`.  
Internal packages (`schema`, `orm`, …) ship inside the fat forge wheel.

Until PyPI: `uv sync --all-packages --group dev` from this repo.


## Packages

### Public (PyPI)

| PyPI | Role |
|------|------|
| **`phzyx-forge`** | Full product (fat wheel: schema, engine, ORM, AdminBoard, CLI) |
| **`phzyx-auth`** | Auth battery |
| **`phzyx-cache`** | Cache battery |

### Repo layout (dev modules; core ships inside forge on PyPI)

| Folder | Import |
|--------|--------|
| `packages/schema` | `phzyx.schema` |
| `packages/engine` | `phzyx.engine` |
| `packages/orm` | `phzyx.orm` |
| `packages/admin` | `phzyx.admin` |
| `packages/admin-fastapi` | `phzyx.admin.fastapi` |
| `packages/admin-litestar` | `phzyx.admin.litestar` |
| `packages/cli` | CLI `phzyx` |
| `packages/auth` | `phzyx.auth` |
| `packages/cache` | `phzyx.cache` |
| `packages/meta-forge` | workspace meta for `phzyx-forge` |

Release build: `uv run python scripts/build_pypi_release.py` · see `docs/ops/PYPI_PUBLISH.md`.

Namespace layout is **PEP 420** — there is **no** `phzyx/__init__.py` at the namespace root.

---

## Quick shape

```python
from fastapi import FastAPI
from phzyx.orm import Model, Field
from phzyx.admin.fastapi import AdminBoard

class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field(unique=True, index=True)

app = FastAPI()
AdminBoard(app, models=[User], theme="magical-white")
# themes: magical-white | stellar-dark | system-ambient
```

```bash
phzyx db push --models app.forge.registry:ALL_MODELS --yes   # local desired-state
# phzyx migrate create / apply                              # versioned SQL for teams
```

---

## Develop

```bash
uv sync --all-packages --group dev
uv run ruff check packages tests
uv run pyright
uv run pytest -q
make cov    # coverage gate (≥ 74% on product packages; ratchet toward 75+)
```

| Path | Purpose |
|------|---------|
| `packages/*` | Library code + package tests |
| `examples/hello` | Minimal FastAPI wiring check |
| `examples/adminboard_live` | Full AdminBoard + API Board demo |
| `tests/packaging` | Install / import split gates |
| `benchmarks/stack_press` | Capacity / stack-press benches |

CI: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) (lint, types, tests 3.11–3.14, coverage, packaging, AdminBoard demo + e2e).

---

## Docs & community

- Humans: [phzyx.xyz/forge](https://phzyx.xyz/forge)
- Performance: [phzyx.xyz/performance](https://phzyx.xyz/performance)
- Security: [SECURITY.md](./SECURITY.md) — **security@phzyx.xyz** (no public issues for vulns)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)
- Contributing: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Conduct: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)

Website and docs live in sibling repos (`phzyxyz/website`, `phzyxyz/docs`). This repo is **Forge (Python packages + AdminBoard SPA + examples)**.

---

## License

[MIT](./LICENSE) · © Athul Nandaswaroop
