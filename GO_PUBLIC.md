# Make phzyxyz/forge public

## Before toggle

1. **CI green** on `main`
2. Secrets scrub (no tokens in tree)
3. README install is honest (clone now; PyPI after tag)
4. Branch protection + private vulnerability reporting
5. **PyPI surface is 3 packages only** — see `docs/ops/PYPI_PUBLISH.md`

## Public PyPI names

- `phzyx-forge` (fat product wheel)
- `phzyx-auth`
- `phzyx-cache`

Trusted Publishers: owner `phzyxyz`, repo `forge`, workflow `publish.yml`, env `pypi`.

Build locally:

```bash
uv sync --all-packages --group dev
uv run python scripts/build_pypi_release.py --clean
```

## Toggle

GitHub → Settings → Danger Zone → Change visibility → **Public**

## After

Fresh clone smoke + later tag `v0.1.0` for PyPI.
