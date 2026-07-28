# phzyx CLI

**Not a separate PyPI project** — ships inside **`phzyx-forge`**.

```bash
uv add phzyx-forge
```

**FastAPI** is the default product path (AdminBoard adapter included). Full docs: [phzyx.xyz/forge/cli](https://phzyx.xyz/forge/cli).

## Which command?

| Command | When |
|---------|------|
| **`phzyx new NAME`** | Greenfield — **creates** `./NAME` then scaffolds |
| **`phzyx forge init`** | Scaffold **here** (existing FastAPI app or empty dir) |
| **`phzyx add auth\|admin`** | Drop **one** wiring module only (does **not** install packages) |

Same scaffold engine for `new` and `forge init`; only the target path differs.

## Greenfield

```bash
uv add phzyx-forge
phzyx new myapp --preset max
cd myapp
uv sync
cp .env.example .env
uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes
uv run uvicorn app.main:app --reload
```

### Presets

| Preset | Features |
|--------|----------|
| `minimal` | Async API + ORM sample |
| `normal` | + auth |
| `max` (default) | + AdminBoard with staff authz |
| `full` | max + docker-compose |

## Existing project

```bash
cd my-fastapi-app
uv add phzyx-forge
phzyx forge init --yes --preset max
# wires app/forge/ without clobbering main.py by default
```

## Add batteries (wiring only)

```bash
uv add 'phzyx-forge[auth]'   # install package yourself
phzyx add auth               # → app/forge/auth.py
phzyx add admin              # → app/forge/admin.py
```

## Other commands

```bash
phzyx doctor
phzyx db push --models app.forge.registry:ALL_MODELS --yes
phzyx migrate status|create|apply
phzyx auth create-superuser
```

## Docs

- Getting started: https://phzyx.xyz/forge/getting-started  
- CLI: https://phzyx.xyz/forge/cli  
