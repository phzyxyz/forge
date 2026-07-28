# Contributing to Forge

Thanks for helping build Phzyx Forge. Product voice: **positive** — no dunking on Django/SQLAlchemy peers.

## Setup

```bash
# Python ≥ 3.11 and uv
uv sync --all-packages --group dev

# Optional task runners
make sync && make check
# or: just sync && just check
```

| Task | Command |
|------|---------|
| Tests | `uv run pytest -q` / `make test` |
| Lint | `uv run ruff check packages tests` |
| Format | `uv run ruff format packages tests` |
| Types | `uv run pyright` |
| Coverage | `make cov` (fail-under 74% on product packages; ratchet to 75+) |
| Hello app | `make hello` |

AdminBoard SPA (when you touch `packages/admin/web`):

```bash
cd packages/admin/web
pnpm install --frozen-lockfile
pnpm check
```

## Package naming

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
| `packages/meta-forge` | `phzyx-forge` | install-all (Forge) |
| `packages/meta` | `phzyx` | ecosystem install-all |

Workspace root package **`phzyx-workspace`** is never published.

## PEP 420 (hard)

```text
✅  packages/<name>/src/phzyx/<leaf>/__init__.py
❌  packages/*/src/phzyx/__init__.py     # breaks multi-package merge
```

## Git workflow

- Trunk: **`main`** only (short PRs; not Git Flow multi-stable).
- PRs need green **CI** (see `.github/workflows/ci.yml`).
- Clean commit messages; **never** add `Co-Authored-By` or AI/tool trailers.
- One focused change per PR when possible.

## Tests

- Prefer `packages/*/tests/` for unit/behavior.
- Thin cross-package checks under `tests/packaging` and `tests/integration`.
- Demo invariants: `tests/demo` (AdminBoard live shape).

## Security

Do **not** open public issues for vulnerabilities. See [SECURITY.md](./SECURITY.md).

## License

MIT. By contributing, you agree your contributions are licensed under the same terms.
