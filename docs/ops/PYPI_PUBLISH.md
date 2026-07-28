# Publish Forge to PyPI (uv + Trusted Publishing)

**Repo:** `phzyxyz/forge`  
**Workflow:** `.github/workflows/publish.yml`  
**Builder:** `scripts/build_pypi_release.py`  
**Tag:** `v0.1.0` (must match package versions `0.1.0`)

## Public surface (only these three)

| PyPI name | Role |
|-----------|------|
| **`phzyx-forge`** | **Hero product** — fat wheel: schema, engine, ORM, AdminBoard (+ SPA), CLI |
| **`phzyx-auth`** | Optional auth battery (`depends on phzyx-forge`) |
| **`phzyx-cache`** | Optional cache battery |

**Not published** (monorepo-only modules; shipped *inside* fat forge):  
`phzyx-schema`, `phzyx-engine`, `phzyx-orm`, `phzyx-admin`, `phzyx-admin-fastapi`, `phzyx-admin-litestar`, `phzyx-cli`, meta `phzyx`, `phzyx-plugin-hello`.

Users install (no forced pin — lockfile tracks the resolved version):

```bash
uv add phzyx-forge
```

---

## 0. Prerequisites

- [ ] PyPI account with **2FA**
- [ ] Access to **phzyxyz/forge**
- [ ] CI green on `main`
- [ ] Versions coordinated at **0.1.0**
- [ ] AdminBoard SPA built: `packages/admin/web/dist/index.html` present
- [ ] uv installed locally (optional dry-run)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

---

## 1. GitHub Environment `pypi`

On https://github.com/phzyxyz/forge :

1. **Settings → Environments → New environment**
2. Name exactly: **`pypi`**
3. Optional: require your review on deploys

No long-lived API token — OIDC Trusted Publishing only.

---

## 2. Trusted Publishers (**3** projects)

https://pypi.org/manage/account/publishing/

For **each** of: `phzyx-forge`, `phzyx-auth`, `phzyx-cache`:

| Field | Value |
|--------|--------|
| PyPI Project Name | `phzyx-forge` / `phzyx-auth` / `phzyx-cache` |
| Owner | **`phzyxyz`** (GitHub org) |
| Repository name | `forge` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

If you previously registered the old 11-package list, only these three are used now.

---

## 3. Dry-run build (no upload)

**GitHub:** Actions → **Publish** → Run workflow (builds artifacts; upload is tag-only).

**Local (monorepo or forge clone):**

```bash
uv sync --all-packages --group dev
uv run python scripts/build_pypi_release.py --clean
ls dist
# expect only phzyx_forge / phzyx_auth / phzyx_cache wheels+sdists
```

The script stages a **fat** forge wheel, builds auth + cache, asserts no internal packages leak into `dist/`, and runs a clean-venv smoke (imports + SPA path + `phzyx --help`).

---

## 4. Tag and publish

```bash
cd /path/to/phzyx-split/forge   # public product repo
git checkout main && git pull
git status   # clean; CI green

git tag -a v0.1.0 -m "Forge 0.1.0 — first public pre-1.0"
git push origin v0.1.0
```

Watch Actions: **build public wheels** → **publish to PyPI**.

---

## 5. Verify after upload

```bash
curl -sS https://pypi.org/pypi/phzyx-forge/json | head -c 200

uv venv /tmp/phzyx-smoke && source /tmp/phzyx-smoke/bin/activate
uv pip install 'phzyx-forge==0.1.0'
python -c "from phzyx.orm import Session; from phzyx.admin.fastapi import AdminBoard; print('ok')"
phzyx --help
```

---

## 6. User install (uv)

```bash
uv add phzyx-forge
uv add phzyx-cache          # optional
uvx --from 'phzyx-forge' phzyx doctor
```

Apps should rely on **`uv.lock`** (or equivalent) for reproducible installs.  
Exact `==0.1.0` is only for release smoke (step 5), not day-to-day docs.

---

## Dev note

Monorepo `packages/meta-forge` remains a **meta** package for editable workspaces.  
**Never** upload that empty wheel; always use `scripts/build_pypi_release.py`.
