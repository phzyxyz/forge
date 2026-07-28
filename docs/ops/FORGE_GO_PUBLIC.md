# Forge go-public (operator monorepo)

Public product repo: **`github.com/phzyxyz/forge`**.  
Local extract: **`../phzyx-split/forge`**.  
This monorepo may stay **private** as the full operator lab.

## Sync before public

Prefer one of:

```bash
# From monorepo after meaningful package/docs changes for forge:
# (your usual resync path into phzyx-split/forge — filter-repo or manual rsync of packages/*)
cd ../phzyx-split/forge
git status
# ensure README / CONTRIBUTING / publish.yml / scripts/build_pypi_release.py match
git push origin main
```

Public-facing files live primarily in **`phzyx-split/forge`** (and on GitHub).  
Keep monorepo `packages/*` as the code source of truth when you develop here.

## Checklist

See **`../phzyx-split/forge/GO_PUBLIC.md`** for the full GitHub toggle list.

Minimum:

1. CI green on `phzyxyz/forge` `main`
2. Secrets scrub
3. Honest README install (clone works; PyPI only if true)
4. Branch protection + security advisories
5. Visibility → **Public**
6. Fresh clone smoke test
7. Tag + PyPI when ready — see **`docs/ops/PYPI_PUBLISH.md`**

## Publish workflow

`.github/workflows/publish.yml` runs `scripts/build_pypi_release.py` on tags `v*`.

**Public PyPI only:**

- **`phzyx-forge`** (fat wheel)
- **`phzyx-auth`**
- **`phzyx-cache`**

Trusted Publishers (3): owner/repo **`phzyxyz/forge`**, workflow `publish.yml`, environment `pypi`.

Do **not** publish split monorepo packages (`phzyx-schema`, `phzyx-orm`, …) or `phzyx-plugin-hello`.
