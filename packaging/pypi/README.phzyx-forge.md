# Phzyx Forge

**The Phzyx data stack in one install** — Pydantic schema, failsafe migrations, dual sync/async ORM, **AdminBoard**, and the `phzyx` CLI.

> Define once in Pydantic. Push or migrate safely. Ship AdminBoard without bolting on a second product.

---

## Start here (website & docs)

PyPI is only the install surface. **Full guides, tutorials, performance story, and product home live on the Phzyx site:**

| | |
|--|--|
| **Product home** | [https://phzyx.xyz](https://phzyx.xyz) |
| **Docs (Forge)** | [https://phzyx.xyz/forge](https://phzyx.xyz/forge) |
| **Getting started** | [https://phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started) |
| **Quickstart tutorial** | [https://phzyx.xyz/forge/tutorials/quickstart](https://phzyx.xyz/forge/tutorials/quickstart) |
| **AdminBoard** | [https://phzyx.xyz/products/adminboard](https://phzyx.xyz/products/adminboard) |
| **Python / install** | [https://phzyx.xyz/python](https://phzyx.xyz/python) |
| **Performance** | [https://phzyx.xyz/performance](https://phzyx.xyz/performance) |
| **Source** | [https://github.com/phzyxyz/forge](https://github.com/phzyxyz/forge) |
| **Issues** | [https://github.com/phzyxyz/forge/issues](https://github.com/phzyxyz/forge/issues) |

**If you only open one page after install → [phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started).**

---

## Install

```bash
uv add phzyx-forge
# or
pip install phzyx-forge
```

That is the **full product** for local work: schema · engine · ORM · AdminBoard (**FastAPI** + SPA) · CLI · **SQLite** (`aiosqlite` included).

**FastAPI is required** for the default AdminBoard path (included as a dependency). Forge is built to **complete the FastAPI-era feature set** — stay on the API stack you chose instead of switching frameworks only for admin/batteries.

```bash
phzyx --help
# Greenfield: create folder + scaffold
phzyx new myapp --preset max
# Existing FastAPI app: scaffold in this directory
phzyx forge init --yes --preset max
```

| CLI | When |
|-----|------|
| `phzyx new NAME` | New project **directory** |
| `phzyx forge init` | Scaffold **here** |
| `phzyx add auth\|admin` | One wiring file only (not install) |

Full CLI docs: [phzyx.xyz/forge/cli](https://phzyx.xyz/forge/cli).

### Extras (when you need them)

| Extra | Adds |
|-------|------|
| *(core)* | Full Forge + SQLite |
| `postgres` | Postgres drivers |
| `mysql` | MySQL / MariaDB driver |
| `mssql` | SQL Server driver |
| `auth` | [phzyx-auth](https://pypi.org/project/phzyx-auth/) battery |
| `cache` | [phzyx-cache](https://pypi.org/project/phzyx-cache/) battery |
| `litestar` | Litestar Admin adapter |
| **`full`** | Every driver + auth + cache + Litestar |

```bash
uv add 'phzyx-forge[postgres]'
uv add 'phzyx-forge[auth]'
uv add 'phzyx-forge[full]'
```

Already installed Forge? Same commands **merge** extras — nothing to uninstall.

---

## Quick taste

```python
from phzyx.schema.model import Model
from phzyx.orm import Session
from phzyx.admin.fastapi import AdminBoard

# Prefer the full walkthrough:
# https://phzyx.xyz/forge/getting-started
```

Imports stay under **`phzyx.*`** — one brand, one mental model.

---

## What you get

- **Schema** — Pydantic models as source of truth  
- **Engine** — push / migrate with failsafe-minded workflow  
- **ORM** — dual sync + async sessions  
- **AdminBoard** — intentional admin API + SPA (not a bolt-on afterthought)  
- **CLI** — `phzyx new`, `phzyx db push`, doctor, presets  

Pre-**1.0**: APIs may evolve. Prefer a lockfile (`uv.lock`); read the site for the current story.

---

## Where to go next

1. **[Getting started](https://phzyx.xyz/forge/getting-started)** — first app path  
2. **[Forge docs hub](https://phzyx.xyz/forge)** — guides & reference  
3. **[AdminBoard](https://phzyx.xyz/products/adminboard)** — operator UI  
4. **[GitHub forge](https://github.com/phzyxyz/forge)** — source, issues, releases  

---

## License

MIT · Athul Nandaswaroop · [phzyx.xyz](https://phzyx.xyz)
