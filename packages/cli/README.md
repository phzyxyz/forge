# phzyx-cli

Phzyx command-line interface: project scaffold, schema push/migrate, doctor.

Part of [Phzyx Forge](https://phzyx.xyz/forge). Install via `uv add phzyx-forge` or `uv add phzyx-cli`.

## Scaffold a new app (recommended)

```bash
uv add phzyx-forge[sqlite,auth]
phzyx new myapp --preset max
cd myapp
uv sync
cp .env.example .env
uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes
uv run uvicorn app.main:app --reload
```

Creates a modern async FastAPI app with `app/forge/` (db, models, registry, admin, auth).

### Presets

| Preset | Features |
|--------|----------|
| `minimal` | Async API + ORM sample |
| `normal` | + auth |
| `max` (default) | + AdminBoard with staff authz |
| `full` | max + docker-compose |

### Existing project

```bash
cd my-fastapi-app
phzyx forge init --yes --preset max
# wires app/forge/ without clobbering main.py
```

### Flags

- `--force` — overwrite scaffold-owned files  
- `--yes` / `-y` — non-interactive defaults  
- `--no-input` — never prompt (fail if a decision is required)  
- `--dry-run` — print plan only  
- `--db sqlite|postgres` — env templates  

## Other commands

```bash
phzyx add admin          # → app/forge/admin.py
phzyx add auth           # → app/forge/auth.py
phzyx doctor
phzyx db push --models app.forge.registry:ALL_MODELS --yes
phzyx migrate status|create|apply
phzyx auth create-superuser
```

## Docs

- Getting started: https://phzyx.xyz/forge/getting-started  
- CLI reference: https://phzyx.xyz/forge/cli  
