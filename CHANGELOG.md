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

## [0.1.8] — unreleased

### Fixed

- **Downgrade SQL.** `create_migration` writes reverse DDL for create table,
  add column, add index, and rename column, in the opposite order. A drop
  stays a comment. The forward plan does not keep the definition that was
  thrown away, so the file does not pretend to undo it.
- **Durable auth.** `durable_auth_service(session_factory, secret=...)` is
  the wiring. Sessions, users, refresh tokens, API keys, password resets,
  and rate limits are database rows. The scaffold and `phzyx add auth` call
  it. `AuthService(config)` with no stores is still the in-memory stand-in
  used by tests. Production mode refuses that stand-in; it does not open a
  database by itself.
- **Refresh-Request-Id.** The same id returns the pair from the first call.
  A different id, or no id, on a consumed token revokes the family. The
  30-second window from 0.1.7 is gone.
- **`phzyx.engine`** re-exports `create_engine`, `create_sync_engine`,
  `create_async_engine`, `create_session`, and `create_async_session`.
  The implementation stays in `phzyx.orm`.

### Unchanged

- Cache stays an optional extra and is still `phzyx-cache` 0.1.6. It is off
  unless the application turns it on.
- Pulse is not part of the Forge production set. PostgreSQL `job_ledger` is
  the job authority.

## [0.1.7] — 2026-10-21

### Fixed

- **Async PostgreSQL transactions.** `AsyncSession.commit` / `rollback` open
  and finish an asyncpg transaction, including when the caller does not use
  `async with`. `create_async_engine("postgresql+asyncpg://…")` borrows from
  a pool and `dispose()` closes it. The scaffold uses that session and
  disposes the engine on shutdown.
- **Migrations.** `migrate_apply` no longer splits on semicolons inside
  strings, quoted identifiers, comments, or dollar-quoted function bodies.
  Downgrade files stay hand-written stubs.
- **Auth ids.** ORM stores no longer allocate `max+1` over a 10,000-row
  scan. Integer primary keys are database identity. Refresh families are
  UUID v7 and stay one family across rotation.
- **Refresh receipts.** Retrying the same refresh token within 30 seconds
  returns the pair already issued. A later retry revokes the family.
- **Passkeys.** A missing `webauthn` extra no longer falls back to HMAC.
  Production refuses an HMAC passkey backend.
- **Production auth** refuses in-memory sessions, users, API keys, rate
  limits, password-reset tokens, and refresh tokens. The scaffold wires the
  ORM stores, including the rate-limit table.
- **AdminBoard** refuses `AllowAll` when `PHZYX_ENV=production` (or
  `PHZYX_PRODUCTION=1`) instead of only warning.
- Internal module versions that shipped inside the 0.1.6 wheel as `0.1.1`
  now report `0.1.7`.

## [0.1.6] — 2026-07-30

### Added

- **Auth policy:** reject placeholder / weak credentials on register and
  `create-superuser` — emails on `example.com` / `test.com` / `localhost`,
  reserved usernames (`admin`, `root`, `test`, …), common passwords
  (`password123`, `admin123`, …), password equal to email/username.
  Interactive CLI still retries with clear `error:` lines (no traceback).

## [0.1.5] — 2026-07-30

### Fixed

- **CLI UX:** `forge auth create-superuser` no longer dumps a traceback for short
  passwords / bad emails. Interactive mode **retries** with `error:` lines;
  flag mode exits **2** with a clear message + hint. Top-level CLI catches
  `KeyboardInterrupt` / missing modules instead of raw stack traces.

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
