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

### From PyPI (when published)

```bash
uv add 'phzyx-forge[sqlite,auth]'
# or: pip install 'phzyx-forge[sqlite,auth]'
```

Pin for apps: `phzyx-forge==0.1.0` (and the same pin for modular packages if you install them separately).

### From this repo (today / contributors)

```bash
git clone https://github.com/phzyxyz/forge.git
cd forge
uv sync --all-packages --group dev
```

Editable workspace packages are then available via `uv run`. Scaffold:

```bash
uv run phzyx new myapp --preset max
cd myapp
uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes
uv run uvicorn app.main:app --reload
```

**0.x contract:** public APIs may change before 1.0. Prefer pins and the docs site over blog posts.

---

## Packages

| Folder | PyPI | Import |
|--------|------|--------|
| `packages/schema` | `phzyx-schema` | `phzyx.schema` |
| `packages/engine` | `phzyx-engine` | `phzyx.engine` |
| `packages/orm` | `phzyx-orm` | `phzyx.orm` |
| `packages/admin` | `phzyx-admin` | `phzyx.admin` |
| `packages/admin-fastapi` | `phzyx-admin-fastapi` | `phzyx.admin.fastapi` |
| `packages/admin-litestar` | `phzyx-admin-litestar` | `phzyx.admin.litestar` |
| `packages/auth` | `phzyx-auth` | `phzyx.auth` |
| `packages/cli` | `phzyx-cli` | CLI `phzyx` |
| `packages/cache` | `phzyx-cache` | `phzyx.cache` |
| `packages/meta-forge` | **`phzyx-forge`** | Forge install-all |
| `packages/meta` | **`phzyx`** | ecosystem install-all |

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
make cov    # coverage gate (≥ 75% on product packages)
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
