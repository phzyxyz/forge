# Make `phzyxyz/forge` public — operator checklist

Do these **on GitHub** after this tree is clean and CI is green.  
Dev monorepo (`phzyx/`) can stay private forever.

## Before the toggle

- [ ] `main` is what you want the world to see (no WIP secret branches as default)
- [ ] CI green on latest `main` (Actions → CI)
- [ ] No secrets in tree: `.env*`, keys, private DSNs, tokens  
      (`git grep -iE 'api_key|secret|password|BEGIN PRIVATE|ghp_|sk_live' -- ':!*.md' ':!uv.lock'` local smoke)
- [ ] [README.md](./README.md) install path is honest (repo clone works; PyPI only if published)
- [ ] [LICENSE](./LICENSE) MIT present
- [ ] [SECURITY.md](./SECURITY.md) contact is real (`security@phzyx.xyz` or update)
- [ ] [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) + [CONTRIBUTING.md](./CONTRIBUTING.md)
- [ ] [publish.yml](./.github/workflows/publish.yml) Trusted Publisher will use **`phzyxyz/forge`** (not old names)
- [ ] Optional: tag **after** public if you want the release commit visible; or tag then public same day

## GitHub settings (forge repo)

1. **Settings → General → Danger Zone → Change visibility → Public**
2. **Settings → Branches → Branch protection on `main`**
   - Require PR before merge (recommended)
   - Require status checks: `lint`, `typecheck`, `test (py3.12)`, `coverage`, `packaging` (at minimum)
3. **Settings → Code security**
   - Enable **Dependabot** alerts
   - Enable **Private vulnerability reporting** / Security advisories
4. **Settings → General**
   - Features: Issues, Discussions (optional)
   - Pull requests: allow squash merge; consider disable force-push to `main` via protection
5. **About** (repo sidebar)
   - Description: e.g. `Forge — Pydantic schema, failsafe migrations, ORM, AdminBoard for FastAPI-era apps`
   - Website: `https://phzyx.xyz/forge`
   - Topics: `python`, `fastapi`, `orm`, `pydantic`, `admin`, `migrations`, `phzyx`

## After public (same day or next)

- [ ] Open `https://github.com/phzyxyz/forge` in a private window — README renders, license shows
- [ ] Clone fresh: `git clone https://github.com/phzyxyz/forge.git && cd forge && uv sync --all-packages --group dev && uv run pytest -q packages/schema packages/orm -q`
- [ ] PyPI Trusted Publishing: create/publish projects when ready; OIDC **owner/repo = `phzyxyz/forge`**, workflow `publish.yml`, environment `pypi`
- [ ] Tag `v0.1.0` only when wheels are ready to ship (or document git-only until then)
- [ ] Tweet / post only after install path works for a stranger

## Do **not** make public yet if

- CI is red on `main`
- README claims PyPI install but packages are not on PyPI **and** clone path is broken
- History still contains secrets (rotate + purge before public)

## Related

- Monorepo ops: `docs/ops/FORGE_GO_PUBLIC.md` (operator monorepo)
- Launch: monorepo `docs/launch-checklist.md`
