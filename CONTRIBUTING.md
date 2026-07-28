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

| Folder | Notes | Import |
|--------|-------|--------|
| `packages/schema` | ships in fat `phzyx-forge` | `phzyx.schema` |
| `packages/engine` | internal (in forge wheel) | `phzyx.engine` |
| `packages/orm` | internal (in forge wheel) | `phzyx.orm` |
| `packages/admin` | internal (in forge wheel) | `phzyx.admin` |
| `packages/admin-fastapi` | internal (in forge wheel) | `phzyx.admin.fastapi` |
| `packages/admin-litestar` | internal (in forge wheel) | `phzyx.admin.litestar` |
| `packages/auth` | **PyPI** | `phzyx.auth` |
| `packages/cli` | internal (in forge wheel) | CLI `phzyx` |
| `packages/cache` | **PyPI** | `phzyx.cache` |
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
