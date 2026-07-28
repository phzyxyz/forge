# Operator launch checklist — Phzyx 0.1.0

Human steps for public release (not fully automated by agents).  
**Product line:** Forge · **Org:** phzyxyz · **Domain:** phzyx.xyz · **Deploy:** Cloudflare  

See also: [MULTI_REPO_SPLIT.md](./MULTI_REPO_SPLIT.md) (M8/S8.6).

## Pre-flight (M8 code track)

- [x] `phzyx-forge` + `phzyx` metas  
- [x] Docs paths `/forge` + `content/forge`  
- [x] AdminBoard branding (title + Powered by Phzyx + Settings)  
- [x] MkDocs archived  
- [ ] Three repos under **phzyxyz** (forge / website / docs) — follow MULTI_REPO_SPLIT  
- [ ] CI green on each repo  

## OPS-gh — Public GitHub (phzyxyz)

- [ ] Org **phzyxyz** exists  
- [ ] Repos **forge**, **website**, **docs** public  
- [ ] Default branch protected; required checks green  
- [ ] `SECURITY.md`, `CODE_OF_CONDUCT.md`, `LICENSE` visible on forge  
- [ ] Topics: `python`, `pydantic`, `fastapi`, `orm`, `admin`, `phzyx`  

## OPS-pypi — Trusted Publishing + tag

- [ ] PyPI names **only:** **`phzyx-forge`**, **`phzyx-auth`**, **`phzyx-cache`** (fat forge via `scripts/build_pypi_release.py`)  
- [ ] GitHub Environment `pypi` + OIDC Trusted Publisher for those three  
- [ ] Tag: `git tag v0.1.0 && git push origin v0.1.0` (from **forge** repo)  
- [ ] Confirm publish job succeeds  
- [ ] Verify:

```bash
uv pip install 'phzyx-forge[sqlite,auth]==0.1.0'
phzyx --help
```

## OPS-dns — Cloudflare

Full steps: **[CLOUDFLARE.md](./CLOUDFLARE.md)** (Workers + `pnpm --filter @phzyx/web run deploy:cf`).

- [ ] Cloudflare account + `wrangler login`  
- [ ] First deploy → `*.workers.dev`  
- [ ] Domain on CF; custom hosts: `phzyx.xyz`, `www`, `docs.phzyx.xyz`, `adminboard.phzyx.xyz`  
- [ ] TLS automatic on Cloudflare  

## Post-tag smoke

```bash
uvx --from phzyx-cli phzyx doctor
uv run python -c "from phzyx.orm import Session; from phzyx.admin.fastapi import AdminBoard"
```

## Notes

- Imports remain `phzyx.*`; product name is **Forge**.  
- Live demo (`examples/adminboard_live`) is for local/OrbStack, not multi-tenant prod.  
- Pulse is a **later** product (`phzyx-pulse`), not part of 0.1 Forge tag.  
