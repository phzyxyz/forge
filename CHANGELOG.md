# Changelog

All notable changes to the Phzyx Forge packages are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versions follow [Semantic Versioning](https://semver.org/).

**Note:** `0.x` means the public API may still change. Prefer pinning
`phzyx-forge` via your lockfile until 1.0; docs install without forcing `==`.

**Public PyPI (0.1):** `phzyx-forge` (fat wheel) · `phzyx-auth` · `phzyx-cache`.  
Monorepo still splits schema/engine/orm/admin/cli for development; those modules ship **inside** fat forge on PyPI.

---

## [Unreleased]

## [0.1.4] — 2026-07-30

### Fixed

- **`forge start` / model load: `ModuleNotFoundError: No module named 'app'`** after
  `forge new` + `uv sync`. Scaffolded apps use `[tool.uv] package = false` (plain
  `app/` layout). Console-script entry points do not put the project root on
  `sys.path`, so `import app.forge.registry` failed during schema preview.
  **0.1.4** inserts the project root before loading models and before uvicorn.

### Upgrade

```bash
# in the project (recommended)
uv add phzyx-forge==0.1.4
# or reinstall the tool + refresh lock
uv tool install phzyx-forge --reinstall
uv lock --upgrade-package phzyx-forge && uv sync
```

## [0.1.3] — 2026-07-30

### Fixed

- **First-run breakage for users:** PyPI 0.1.2 only exposed `phzyx`, while docs said `forge` → `command not found`. **0.1.3 ships both `forge` and `phzyx`**.
- **`uvicorn` missing for `start`:** fat wheel now depends on `uvicorn[standard]`.
- Scaffold README / post-steps: **always `uv run`** (any OS); warn against bare Homebrew/global `uvicorn`.

### Added

- **`forge` CLI** (primary) + **`phzyx`** alias (same entrypoint).
- **`forge start`**: dev server **:9898**; prompts if schema/migrations pending (never silent apply).
- **`forge init`**: top-level scaffold-in-place.


### Added (prior unreleased)


- **Public packaging (first impression):** fat **`phzyx-forge`** wheel + optional **`phzyx-auth`** / **`phzyx-cache`** only. Release via `scripts/build_pypi_release.py`. Internal monorepo packages are not separate PyPI projects.
- **API Board (`/apiboard/`):** standalone Forge API Client (same SPA mount as AdminBoard). Live OpenAPI collection, card grid + request console, sample bodies, environments with `{{vars}}`, platform-bound `baseUrl`, sandbox (`sessionStorage`) vs workspace (`localStorage`) JSON (`phzyx.forge.client` v1), history/saved responses, export/import. Docs: `/forge/apiboard`.
- **Website:** hub hero mini **stack-press** card (realistic 250k-row median RPS) + full table on `/stats#benchmarks` from committed `bench.snapshot.json`.
- **CLI v1 scaffold:** `phzyx new` / `phzyx forge init` emit async FastAPI + `app/forge/` (dual session, registry, Item CRUD, Admin+auth on max, SECURITY.md). Legacy layouts alias to forge.
- **phzyx-forge extras:** `sqlite`, `postgres`, `mysql`, `mssql`, `auth`, `cache`, `litestar`, `full`.
- **Docs / website:** forge-first install everywhere; package map reflects 3 public PyPI names.
- **Diamond D4.5 — M2M multi-select:** auto-detect through tables (composite PK of two FKs), bidirectional `kind: m2m` relations, `GET/PUT …/m2m/{relation}`, SPA chip multi-select on create/edit, demo `Tag` / `PostTag`.

---

## [0.1.0] — 2026-07-19

First public pre-1.0 release of the Forge stack.

### Added

#### Product (`phzyx-forge` fat wheel — includes schema · engine · ORM · AdminBoard · CLI)

- Pydantic v2 `Field` / `Model` with DB metadata (`ColumnMeta`, `TableInfo`)
- Composite primary keys, unique, index, simple FK
- `Manifest` IR (`manifest_version = 1`) and CREATE TABLE DDL (Postgres + SQLite)
- Introspect, version-aware capabilities, sans-I/O diff/plan
- `db push` with archive-first safety (no silent DROP COLUMN)
- Versioned migrate create/apply + history table
- Sync + async sessions over best-in-class drivers
- Headless `AdminService` + FastAPI `AdminBoard` mount (+ Litestar adapter code)
- Themes: Magical White, Stellar Dark, System Ambient
- CLI `phzyx` (`db`, `migrate`, `new`, …)

#### Batteries

- **`phzyx-auth`** — identity battery (depends on forge)
- **`phzyx-cache`** — versioned resource cache
- Docs site, hub shells, `llms.txt` / `llms-full.txt`
- SECURITY.md, CODE_OF_CONDUCT.md, publish workflow (3 packages)

### Security

- Default libraryion warnings for `AllowAll` authz
- Upload key sanitization helpers

### Notes

- **0.1.0 is not a stability promise** — APIs may change before 1.0
- Rust acceleration deferred (bench-gated; pure Python for 0.1)
- Algomax / ODM / OGM intentionally not in 0.1

---

## [Unreleased]

Nothing yet.
