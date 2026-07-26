# Changelog

All notable changes to the Phzyx Python flagship packages are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versions follow [Semantic Versioning](https://semver.org/).

**Note:** `0.x` means the public API may still change. Prefer pinning
`phzyx==0.1.0` (or individual `phzyx-*` pins) until 1.0.

Packages in this monorepo share a coordinated version for the 0.1 line:

`phzyx`, `phzyx-schema`, `phzyx-engine`, `phzyx-orm`, `phzyx-admin`,
`phzyx-admin-fastapi`, `phzyx-admin-litestar`, `phzyx-cli`, `phzyx-cache`.

---

## [Unreleased]

### Added

- **CLI v1 scaffold:** `phzyx new` / `phzyx forge init` emit async FastAPI + `app/forge/` (dual session, registry, Item CRUD, Admin+auth on max, SECURITY.md). Legacy layouts alias to forge.
- **phzyx-forge extras:** `sqlite`, `postgres`, `mysql`, `mssql`, `auth`, `full`.
- **Docs:** `/forge/getting-started` (small→medium FastAPI), guides (layout, dual-session, registry, push-vs-migrate), security, expanded CLI/tutorials/compare.
- **Website:** Get started → getting-started; hub Why Forge copy; install stays `phzyx-forge`.
- **Diamond D4.5 — M2M multi-select:** auto-detect through tables (composite PK of two FKs), bidirectional `kind: m2m` relations, `GET/PUT …/m2m/{relation}`, SPA chip multi-select on create/edit, demo `Tag` / `PostTag`.

---

## [0.1.0] — 2026-07-19

First public pre-1.0 release of the Python flagship stack.

### Added

#### Schema (`phzyx-schema`)

- Pydantic v2 `Field` / `Model` with DB metadata (`ColumnMeta`, `TableInfo`)
- Composite primary keys, unique, index, simple FK
- `Manifest` IR (`manifest_version = 1`) and CREATE TABLE DDL (Postgres + SQLite)
- Model registry

#### Engine (`phzyx-engine`)

- Introspect, version-aware capabilities, sans-I/O diff/plan
- `db push` with archive-first safety (no silent DROP COLUMN)
- Versioned migrate create/apply + history table
- Plan lint for CI destructive guards
- Optional TUI approval for push

#### ORM (`phzyx-orm`)

- Sync + async sessions over best-in-class drivers
- Filters, bulk insert, FileField keys
- Keyset pagination and streaming iterators

#### AdminBoard (`phzyx-admin`, adapters)

- Headless `AdminService` + FastAPI `AdminBoard` mount
- Litestar adapter
- Themes: Magical White, Stellar Dark, System Ambient
- Export CSV / JSON / Excel; stream CSV/JSONL
- Multi-cloud storage backends (S3-compatible, Azure, GCS shapes)
- Audit log hooks, CSP headers, mass-assignment guards

#### Other

- CLI `phzyx` (`db`, `migrate`)
- Versioned resource cache (`phzyx-cache`)
- Meta install-all package `phzyx==0.1.0`
- Docs site (MkDocs), hub shells, `llms.txt` / `llms-full.txt`
- SECURITY.md, CODE_OF_CONDUCT.md, publish workflow

### Security

- Default production warnings for `AllowAll` authz
- Upload key sanitization helpers

### Notes

- **0.1.0 is not a stability promise** — APIs may change before 1.0
- Rust acceleration deferred (bench-gated; pure Python for 0.1)
- Algomax / ODM / OGM intentionally not in 0.1

---

## [Unreleased]

Nothing yet.
