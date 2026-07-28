# Phzyx Forge 0.1.0

**First public pre-1.0 release** of Athul Nandaswaroop’s Python flagship — schema, failsafe migrations, ORM, and AdminBoard for FastAPI-era backends.

> **0.x contract:** APIs may still change. Pin `phzyx-forge==0.1.0`. A future **1.0** will mean a stronger stability promise.

## Install

```bash
uv add 'phzyx-forge[sqlite,auth]==0.1.0'
```

Optional batteries:

```bash
uv add 'phzyx-auth==0.1.0'
uv add 'phzyx-cache==0.1.0'
```

## Highlights

- **One model** — Pydantic is the schema truth (`phzyx.schema`)
- **Failsafe engine** — archive-first push; migrate for shared/prod (`phzyx.engine`)
- **ORM** — sync/async sessions, keyset pagination, FileField keys (`phzyx.orm`)
- **AdminBoard** — FastAPI mount (`phzyx.admin.fastapi`); Magical White / Stellar Dark / Ambient
- **CLI** — `phzyx new` / `phzyx forge init` / `phzyx db push`
- **Export** — CSV, JSON, Excel; streaming CSV/JSONL
- **Files** — keys in DB; multi-cloud storage backends
- **Agent-ready** — `llms.txt`, honest docs

## Public packages (0.1.0)

| PyPI | Role |
|------|------|
| **`phzyx-forge`** | Full product (fat wheel) |
| **`phzyx-auth`** | Auth battery |
| **`phzyx-cache`** | Cache battery |

Internal monorepo modules ship **inside** `phzyx-forge` on PyPI (not separate projects).

## Docs

- Hub: https://phzyx.xyz  
- Docs: https://phzyx.xyz/forge  
- Changelog: [CHANGELOG.md](../CHANGELOG.md)  
- Security: [SECURITY.md](../SECURITY.md)  
- Publish ops: [docs/ops/PYPI_PUBLISH.md](../docs/ops/PYPI_PUBLISH.md)

## Not in 0.1

- Semver 1.0 stability freeze
- Rust acceleration
- Algomax product code
